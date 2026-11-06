from core.fechas import limites_fechas
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from pedidos.models import Pedido
from .bloqueos import bloquear_jornada


class Pago(models.Model):
    class Metodo(models.TextChoices):
        EFECTIVO = 'EFECTIVO', 'Efectivo'
        TARJETA = 'TARJETA', 'Tarjeta'
        YAPE = 'YAPE', 'Yape'
        PLIN = 'PLIN', 'Plin'

    pedido = models.OneToOneField(
        Pedido,
        on_delete=models.PROTECT,
        related_name='pago',
    )
    cajero = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='pagos_registrados',
    )
    metodo = models.CharField(max_length=20, choices=Metodo.choices)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    monto_recibido = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    vuelto = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, editable=False
    )
    referencia = models.CharField(max_length=100, blank=True)
    observacion = models.TextField(blank=True)
    fecha_pago = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_pago']
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'

    def __str__(self):
        return f'Pago {self.id} - Pedido {self.pedido_id}'

    def clean(self):
        if self.pk is None and CierreCaja.objects.filter(
            fecha_operacion=timezone.localdate()
        ).exists():
            raise ValidationError(
                'La caja del día ya fue cerrada y no admite nuevos pagos.'
            )
        if self.pedido_id is None:
            return
        if self.pk:
            original = Pago.objects.get(pk=self.pk)
            campos_cobro = (
                'pedido_id', 'cajero_id', 'metodo', 'monto',
                'monto_recibido', 'vuelto',
            )
            if any(getattr(original, campo) != getattr(self, campo)
                   for campo in campos_cobro):
                raise ValidationError(
                    'No se pueden modificar los datos de un cobro registrado.'
                )
        estado_esperado = (
            Pedido.Estado.PAGADO if self.pk else Pedido.Estado.ENTREGADO
        )
        if self.pedido.estado != estado_esperado:
            raise ValidationError(
                'Solo se pueden registrar pagos para pedidos entregados; '
                'los pagos existentes deben conservar su pedido pagado.'
            )
        if self.pedido.total != self.monto:
            raise ValidationError(
                'El monto del pago debe coincidir con el total del pedido.'
            )
        if Pago.objects.filter(pedido=self.pedido).exclude(pk=self.pk).exists():
            raise ValidationError(
                'Este pedido ya tiene un pago registrado.'
            )
        if self.metodo == self.Metodo.EFECTIVO:
            if self.monto_recibido is None:
                raise ValidationError(
                    'En pagos en efectivo es obligatorio indicar el monto recibido.'
                )
            if self.monto_recibido < self.monto:
                raise ValidationError(
                    'El monto recibido debe ser mayor o igual al total del pedido.'
                )
        elif self.monto_recibido not in (None, Decimal('0'), self.monto):
            raise ValidationError(
                'Para este método de pago el vuelto debe ser cero.'
            )

    def save(self, *args, **kwargs):
        with transaction.atomic():
            bloquear_jornada(timezone.localdate())
            self.pedido = Pedido.objects.select_for_update().get(
                pk=self.pedido_id
            )
            self.clean()
            if self.metodo == self.Metodo.EFECTIVO:
                self.vuelto = self.monto_recibido - self.monto
            else:
                self.vuelto = Decimal('0')
            super().save(*args, **kwargs)
            pedido = self.pedido
            pedido.estado = Pedido.Estado.PAGADO
            pedido.save()


class CierreCaja(models.Model):
    fecha_operacion = models.DateField(
        default=timezone.localdate,
        unique=True,
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='cierres_caja',
    )
    monto_inicial = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    efectivo_ventas = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, editable=False
    )
    efectivo_esperado = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, editable=False
    )
    efectivo_contado = models.DecimalField(
        max_digits=10, decimal_places=2
    )
    diferencia = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, editable=False
    )
    total_tarjeta = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, editable=False
    )
    total_yape = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, editable=False
    )
    total_plin = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, editable=False
    )
    total_ventas = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, editable=False
    )
    cantidad_pagos = models.PositiveIntegerField(default=0, editable=False)
    observacion = models.TextField(blank=True)
    fecha_cierre = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_operacion']
        verbose_name = 'Cierre de caja'
        verbose_name_plural = 'Cierres de caja'

    def __str__(self):
        return f'Cierre de caja - {self.fecha_operacion}'

    def _pagos_de_la_fecha(self):
        inicio, fin = limites_fechas(self.fecha_operacion, self.fecha_operacion)
        return Pago.objects.filter(fecha_pago__range=(inicio, fin))

    def pagos_del_dia(self):
        return self._pagos_de_la_fecha().select_related(
            'pedido__mesa', 'cajero'
        )

    def clean(self):
        if self.monto_inicial is not None and self.monto_inicial < 0:
            raise ValidationError({
                'monto_inicial': 'El monto inicial no puede ser negativo.'
            })
        if self.efectivo_contado is not None and self.efectivo_contado < 0:
            raise ValidationError({
                'efectivo_contado': 'El efectivo contado no puede ser negativo.'
            })

    def save(self, *args, **kwargs):
        with transaction.atomic():
            bloquear_jornada(self.fecha_operacion)
            if self.pk is None and CierreCaja.objects.filter(
                fecha_operacion=self.fecha_operacion
            ).exists():
                raise ValidationError('La caja de esta fecha ya fue cerrada.')
            if self.pk is None:
                pagos = self._pagos_de_la_fecha()
                totales = pagos.aggregate(
                    total=Coalesce(Sum('monto'), Decimal('0')),
                    efectivo=Coalesce(
                        Sum(
                            'monto',
                            filter=Q(metodo=Pago.Metodo.EFECTIVO),
                        ),
                        Decimal('0'),
                    ),
                    tarjeta=Coalesce(
                        Sum(
                            'monto',
                            filter=Q(metodo=Pago.Metodo.TARJETA),
                        ),
                        Decimal('0'),
                    ),
                    yape=Coalesce(
                        Sum('monto', filter=Q(metodo=Pago.Metodo.YAPE)),
                        Decimal('0'),
                    ),
                    plin=Coalesce(
                        Sum('monto', filter=Q(metodo=Pago.Metodo.PLIN)),
                        Decimal('0'),
                    ),
                )
                self.efectivo_ventas = totales['efectivo']
                self.efectivo_esperado = self.monto_inicial + self.efectivo_ventas
                self.total_tarjeta = totales['tarjeta']
                self.total_yape = totales['yape']
                self.total_plin = totales['plin']
                self.total_ventas = totales['total']
                self.cantidad_pagos = pagos.count()
            self.full_clean()
            self.diferencia = self.efectivo_contado - self.efectivo_esperado
            super().save(*args, **kwargs)
