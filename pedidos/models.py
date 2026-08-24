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
                mesa_anterior_id = Pedido.objects.values_list(
                    'mesa_id', flat=True
                ).get(pk=self.pk)

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

    def save(self, *args, **kwargs):
        if self._state.adding:
            if not self.producto.disponible:
                raise ValidationError(
                    f'El producto "{self.producto.nombre}" no está disponible.'
                )
            self.precio_unitario = self.producto.precio
        super().save(*args, **kwargs)
