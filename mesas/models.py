from django.core.exceptions import ValidationError
from django.db import models


class Mesa(models.Model):
    class Estado(models.TextChoices):
        LIBRE = 'LIBRE', 'Libre'
        OCUPADA = 'OCUPADA', 'Ocupada'
        RESERVADA = 'RESERVADA', 'Reservada'
        FUERA_SERVICIO = 'FUERA_SERVICIO', 'Fuera de servicio'

    numero = models.PositiveIntegerField(unique=True)
    capacidad = models.PositiveSmallIntegerField()
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.LIBRE,
    )
    ubicacion = models.CharField(max_length=100, blank=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['numero']
        verbose_name = 'Mesa'
        verbose_name_plural = 'Mesas'

    def __str__(self):
        return f'Mesa {self.numero} - {self.get_estado_display()}'

    def clean(self):
        super().clean()
        if not self.pk:
            return
        from pedidos.models import Pedido

        if Pedido.objects.filter(
            mesa_id=self.pk, estado__in=Pedido.ESTADOS_ACTIVOS
        ).exists():
            errores = {}
            if not self.activo:
                errores['activo'] = (
                    'No puedes desactivar una mesa con un pedido activo.'
                )
            if self.estado != self.Estado.OCUPADA:
                errores['estado'] = (
                    'Una mesa con un pedido activo debe permanecer ocupada.'
                )
            if errores:
                raise ValidationError(errores)
