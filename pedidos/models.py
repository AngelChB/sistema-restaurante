from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction

from mesas.models import Mesa


class Pedido(models.Model):
    class Estado(models.TextChoices):
        ABIERTO = 'ABIERTO', 'Abierto'
        EN_PREPARACION = 'EN_PREPARACION', 'En preparación'
        LISTO = 'LISTO', 'Listo'
        ENTREGADO = 'ENTREGADO', 'Entregado'
        PAGADO = 'PAGADO', 'Pagado'
        CANCELADO = 'CANCELADO', 'Cancelado'

    ESTADOS_ACTIVOS = [
        Estado.ABIERTO,
        Estado.EN_PREPARACION,
        Estado.LISTO,
        Estado.ENTREGADO,
    ]

    mesa = models.ForeignKey(
        'mesas.Mesa',
        on_delete=models.PROTECT,
        related_name='pedidos',
    )
    mesero = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='pedidos_registrados',
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ABIERTO,
    )
    observacion = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'

    def __str__(self):
        return f'Pedido {self.id} - Mesa {self.mesa.numero}'

    @property
    def total(self):
        return sum(d.subtotal for d in self.detalles.all())

    def clean(self):
        self.validate()

    def validate(self):
        from caja.models import Pago
        pago = Pago.objects.filter(pedido_id=self.pk).first() if self.pk else None
        if self.estado == self.Estado.PAGADO and (
            pago is None or pago.monto != self.total
        ):
            raise ValidationError('Un pedido solo puede figurar pagado con un cobro válido por su total.')
        if pago is not None and self.estado != self.Estado.PAGADO:
            raise ValidationError('Un pedido con un cobro registrado debe conservar el estado pagado.')
        if self.pk and self.estado == self.Estado.ABIERTO:
            anterior = Pedido.objects.get(pk=self.pk)
            if anterior.estado != self.Estado.ABIERTO:
                raise ValidationError('Un pedido que ya salió de abierto no puede reabrirse para editar sus productos.')
        if self.estado not in self.ESTADOS_ACTIVOS:
            return
        if not self.mesa.activo:
            raise ValidationError(
                'No se puede tener un pedido activo en una mesa inactiva.'
            )
        if self.mesa.estado == Mesa.Estado.FUERA_SERVICIO:
            raise ValidationError(
                'No se puede tener un pedido activo en una mesa fuera de servicio.'
            )
        pedidos_activos = Pedido.objects.filter(
            mesa=self.mesa,
            estado__in=self.ESTADOS_ACTIVOS,
        )
        if self.pk:
            pedidos_activos = pedidos_activos.exclude(pk=self.pk)
        if pedidos_activos.exists():
            raise ValidationError(
                'Ya existe un pedido activo en esta mesa.'
            )

    def _tiene_otros_pedidos_activos(self, mesa_id):
        pedidos_activos = Pedido.objects.filter(
            mesa_id=mesa_id,
            estado__in=self.ESTADOS_ACTIVOS,
        )
        if self.pk:
            pedidos_activos = pedidos_activos.exclude(pk=self.pk)
        return pedidos_activos.exists()

    def save(self, *args, **kwargs):
        with transaction.atomic():
            mesa_anterior_id = None
            if self.pk:
                mesa_anterior_id = Pedido.objects.select_for_update().values_list(
                    'mesa_id', flat=True
                ).get(pk=self.pk)

            mesas_ids = {self.mesa_id}
            if mesa_anterior_id:
                mesas_ids.add(mesa_anterior_id)
            mesas = {m.pk: m for m in Mesa.objects.select_for_update().filter(
                pk__in=mesas_ids
            ).order_by('pk')}
            self.mesa = mesas[self.mesa_id]
            self.validate()
            super().save(*args, **kwargs)

            if self.estado in self.ESTADOS_ACTIVOS:
                if self.mesa.estado != Mesa.Estado.OCUPADA:
                    self.mesa.estado = Mesa.Estado.OCUPADA
                    self.mesa.save(update_fields=['estado'])
            else:
                if not self._tiene_otros_pedidos_activos(self.mesa_id):
                    if self.mesa.estado != Mesa.Estado.LIBRE:
                        self.mesa.estado = Mesa.Estado.LIBRE
                        self.mesa.save(update_fields=['estado'])

            if mesa_anterior_id and mesa_anterior_id != self.mesa_id:
                if not self._tiene_otros_pedidos_activos(mesa_anterior_id):
                    mesa_anterior = Mesa.objects.get(pk=mesa_anterior_id)
                    if mesa_anterior.estado != Mesa.Estado.LIBRE:
                        mesa_anterior.estado = Mesa.Estado.LIBRE
                        mesa_anterior.save(update_fields=['estado'])

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            mesa_id = self.mesa_id
            resultado = super().delete(*args, **kwargs)
            if not Pedido.objects.filter(
                mesa_id=mesa_id,
                estado__in=self.ESTADOS_ACTIVOS,
            ).exists():
                mesa = Mesa.objects.get(pk=mesa_id)
                if mesa.estado != Mesa.Estado.LIBRE:
                    mesa.estado = Mesa.Estado.LIBRE
                    mesa.save(update_fields=['estado'])
            return resultado


class DetallePedido(models.Model):
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name='detalles',
    )
    producto = models.ForeignKey(
        'catalogo.Producto',
        on_delete=models.PROTECT,
    )
    cantidad = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False,
    )
    observacion = models.CharField(max_length=255, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Detalle del pedido'
        verbose_name_plural = 'Detalles del pedido'

    def __str__(self):
        return f'{self.cantidad} x {self.producto.nombre}'

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def _validar_detalles_editables(self):
        pedidos_ids = {self.pedido_id}
        if self.pk:
            pedidos_ids.add(
                DetallePedido.objects.values_list('pedido_id', flat=True).get(pk=self.pk)
            )
        pedidos = list(Pedido.objects.select_for_update().filter(
            pk__in=pedidos_ids
        ).order_by('pk'))
        if any(p.estado != Pedido.Estado.ABIERTO or hasattr(p, 'pago')
               for p in pedidos):
            raise ValidationError('Solo se pueden cambiar productos y cantidades mientras el pedido está abierto.')

    def save(self, *args, **kwargs):
        with transaction.atomic():
            self._validar_detalles_editables()
            self._guardar_detalle(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            self._validar_detalles_editables()
            return super().delete(*args, **kwargs)

    def _guardar_detalle(self, *args, **kwargs):
        if self._state.adding:
            if not self.producto.disponible:
                raise ValidationError(
                    f'El producto "{self.producto.nombre}" no está disponible.'
                )
            self.precio_unitario = self.producto.precio
        super().save(*args, **kwargs)
