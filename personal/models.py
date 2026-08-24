from django.conf import settings
from django.db import models


class PerfilEmpleado(models.Model):
    class Rol(models.TextChoices):
        ADMINISTRADOR = 'ADMINISTRADOR', 'Administrador'
        MESERO = 'MESERO', 'Mesero'
        COCINA = 'COCINA', 'Cocina'
        CAJERO = 'CAJERO', 'Cajero'

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='perfil_empleado',
    )
    rol = models.CharField(
        max_length=20,
        choices=Rol.choices,
        default=Rol.MESERO,
    )
    telefono = models.CharField(max_length=20, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['usuario__username']
        verbose_name = 'Perfil de empleado'
        verbose_name_plural = 'Perfiles de empleados'

    def __str__(self):
        return f'{self.usuario} - {self.get_rol_display()}'
