from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction


class Proveedor(models.Model):
    razon_social = models.CharField(max_length=150, unique=True)
    ruc = models.CharField(
        max_length=11,
        unique=True,
        null=True,
        blank=True,
    )
    contacto = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['razon_social']
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'

    def __str__(self):
        return self.razon_social


class Compra(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', 'Borrador'
        RECIBIDA = 'RECIBIDA', 'Recibida'
        CANCELADA = 'CANCELADA', 'Cancelada'

    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.PROTECT,
        related_name='compras',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='compras_registradas',
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.BORRADOR,
    )
    numero_documento = models.CharField(max_length=50, blank=True)
    fecha_documento = models.DateField()
    observacion = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    fecha_recepcion = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_creacion', '-id']
        verbose_name = 'Compra'
        verbose_name_plural = 'Compras'

    def __str__(self):
        return f'Compra {self.id} - {self.proveedor.razon_social}'

    @property
    def total(self):
        return sum(d.subtotal for d in self.detalles.all())

    def validate(self):
        if self.pk:
            anterior = Compra.objects.get(pk=self.pk)
            if anterior.estado != self.estado:
                if anterior.estado != self.Estado.BORRADOR:
                    raise ValidationError(
                        'Solo se pueden modificar compras en borrador.'
                    )
                if self.estado not in [
                    self.Estado.BORRADOR,
                    self.Estado.RECIBIDA,
                    self.Estado.CANCELADA,
                ]:
                    raise ValidationError('Estado no válido para una compra.')

    def clean(self):
        self.validate()

    def save(self, *args, **kwargs):
        with transaction.atomic():
            self.validate()
            super().save(*args, **kwargs)


class DetalleCompra(models.Model):
    compra = models.ForeignKey(
        Compra,
        on_delete=models.CASCADE,
        related_name='detalles',
    )
    ingrediente = models.ForeignKey(
        'inventario.Ingrediente',
        on_delete=models.PROTECT,
        related_name='detalles_compra',
    )
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=4)

    class Meta:
        ordering = ['compra', 'ingrediente']
        verbose_name = 'Detalle de compra'
        verbose_name_plural = 'Detalles de compra'
        constraints = [
            models.UniqueConstraint(
                fields=['compra', 'ingrediente'],
                name='compra_ingrediente_unica',
            ),
        ]

    def __str__(self):
        return f'{self.cantidad} de {self.ingrediente.nombre}'

    @property
    def subtotal(self):
        return self.cantidad * self.costo_unitario

    def clean(self):
        if self.cantidad is not None and self.cantidad <= 0:
            raise ValidationError({
                'cantidad': 'La cantidad debe ser mayor que cero.'
            })
        if self.costo_unitario is not None and self.costo_unitario < 0:
            raise ValidationError({
                'costo_unitario': 'El costo unitario no puede ser negativo.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
