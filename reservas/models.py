from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from mesas.models import Mesa


class Cliente(models.Model):
    nombres = models.CharField(max_length=150)
    apellidos = models.CharField(max_length=150, blank=True)
    documento = models.CharField(
        max_length=15,
        blank=True,
        unique=True,
        null=True,
    )
    telefono = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    observacion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombres', 'apellidos']
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        nombre_completo = f'{self.nombres} {self.apellidos}'.strip()
        return f'{nombre_completo} - {self.telefono}'

    def clean(self):
        self.validate()

    def validate(self):
        if self.documento:
            clientes = Cliente.objects.filter(documento__iexact=self.documento)
            if self.pk:
                clientes = clientes.exclude(pk=self.pk)
            if clientes.exists():
                raise ValidationError(
                    {'documento': ('Ya existe un cliente con ese documento.')}
                )

    def save(self, *args, **kwargs):
        self.validate()
        super().save(*args, **kwargs)


class Reserva(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        CONFIRMADA = 'CONFIRMADA', 'Confirmada'
        ATENDIDA = 'ATENDIDA', 'Atendida'
        CANCELADA = 'CANCELADA', 'Cancelada'
        NO_ASISTIO = 'NO_ASISTIO', 'No asistió'

    ESTADOS_ACTIVOS = [Estado.PENDIENTE, Estado.CONFIRMADA]

    TRANSICIONES = {
        Estado.PENDIENTE: [Estado.CONFIRMADA, Estado.CANCELADA],
        Estado.CONFIRMADA: [
            Estado.ATENDIDA,
            Estado.CANCELADA,
            Estado.NO_ASISTIO,
        ],
        Estado.ATENDIDA: [],
        Estado.CANCELADA: [],
        Estado.NO_ASISTIO: [],
    }

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='reservas',
    )
    mesa = models.ForeignKey(
        Mesa,
        on_delete=models.PROTECT,
        related_name='reservas',
    )
    fecha_hora = models.DateTimeField()
    cantidad_personas = models.PositiveSmallIntegerField()
    duracion_minutos = models.PositiveSmallIntegerField(default=120)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )
    observacion = models.TextField(blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reservas_registradas',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['fecha_hora', '-fecha_creacion']
        verbose_name = 'Reserva'
        verbose_name_plural = 'Reservas'

    def __str__(self):
        return f'Reserva {self.pk} - {self.cliente} - Mesa {self.mesa.numero}'

    @property
    def fin(self):
        return self.fecha_hora + timedelta(minutes=self.duracion_minutos)

    @property
    def vencida(self):
        return self.estado in self.ESTADOS_ACTIVOS and self.fin <= timezone.now()

    def clean(self):
        self.validate()

    def validate(self):
        errores = {}
        if self.cantidad_personas is not None and self.cantidad_personas <= 0:
            errores['cantidad_personas'] = (
                'La cantidad de personas debe ser mayor que cero.'
            )
        if self.duracion_minutos is not None and self.duracion_minutos <= 0:
            errores['duracion_minutos'] = 'La duración debe ser mayor que cero minutos.'
        if self.fecha_hora is not None:
            from django.utils import timezone

            if self.estado in self.ESTADOS_ACTIVOS:
                if self.fecha_hora <= timezone.now():
                    errores['fecha_hora'] = (
                        'La fecha y hora de la reserva debe ser futura.'
                    )
            if self.mesa_id and self.estado in self.ESTADOS_ACTIVOS:
                if not self.mesa.activo:
                    errores['mesa'] = 'No se puede reservar una mesa inactiva.'
                if self.mesa.estado == Mesa.Estado.FUERA_SERVICIO:
                    errores['mesa'] = 'No se puede reservar una mesa fuera de servicio.'
                if self.mesa.capacidad is not None and (
                    self.cantidad_personas is not None
                    and self.cantidad_personas > self.mesa.capacidad
                ):
                    errores['cantidad_personas'] = (
                        'La cantidad de personas supera la capacidad '
                        f'de la mesa ({self.mesa.capacidad} personas).'
                    )
                if self.estado in self.ESTADOS_ACTIVOS:
                    if self._hay_choque_de_horario():
                        errores['fecha_hora'] = (
                            'Ya existe una reserva activa para esta mesa '
                            'en ese horario.'
                        )
        if errores:
            raise ValidationError(errores)

    def _hay_choque_de_horario(self):
        fin = self.fin
        reservas = Reserva.objects.filter(
            mesa_id=self.mesa_id,
            estado__in=self.ESTADOS_ACTIVOS,
        )
        if self.pk:
            reservas = reservas.exclude(pk=self.pk)
        for reserva in reservas:
            inicio_existente = reserva.fecha_hora
            fin_existente = reserva.fin
            if inicio_existente < fin and self.fecha_hora < fin_existente:
                return True
        return False

    def save(self, *args, **kwargs):
        with transaction.atomic():
            mesas_ids = {self.mesa_id}
            if self.pk:
                anterior = Reserva.objects.select_for_update().get(pk=self.pk)
                mesas_ids.add(anterior.mesa_id)
            # Una fila de mesa existe incluso cuando todavía no hay reservas.
            mesas = {
                m.pk: m
                for m in Mesa.objects.select_for_update()
                .filter(pk__in=mesas_ids)
                .order_by('pk')
            }
            self.mesa = mesas[self.mesa_id]
            self.validate()
            super().save(*args, **kwargs)
