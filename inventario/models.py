from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction


class UnidadMedida(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    abreviatura = models.CharField(max_length=10, unique=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Unidad de medida'
        verbose_name_plural = 'Unidades de medida'

    def __str__(self):
        return f'{self.nombre} ({self.abreviatura})'


class Ingrediente(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    unidad_medida = models.ForeignKey(
        UnidadMedida,
        on_delete=models.PROTECT,
    )
    stock_actual = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    stock_minimo = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Ingrediente'
        verbose_name_plural = 'Ingredientes'

    def __str__(self):
        return self.nombre

    @property
    def bajo_stock(self):
        return self.stock_actual <= self.stock_minimo

    def clean(self):
        if self.stock_actual is not None and self.stock_actual < 0:
            raise ValidationError(
                {'stock_actual': 'El stock actual no puede ser negativo.'}
            )
        if self.stock_minimo is not None and self.stock_minimo < 0:
            raise ValidationError(
                {'stock_minimo': 'El stock mínimo no puede ser negativo.'}
            )
        if self.costo_unitario is not None and self.costo_unitario < 0:
            raise ValidationError(
                {'costo_unitario': 'El costo unitario no puede ser negativo.'}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class RecetaProducto(models.Model):
    producto = models.ForeignKey(
        'catalogo.Producto',
        on_delete=models.CASCADE,
        related_name='receta',
    )
    ingrediente = models.ForeignKey(
        Ingrediente,
        on_delete=models.PROTECT,
        related_name='recetas',
    )
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        ordering = ['producto', 'ingrediente']
        verbose_name = 'Ingrediente de receta'
        verbose_name_plural = 'Ingredientes de recetas'
        constraints = [
            models.UniqueConstraint(
                fields=['producto', 'ingrediente'],
                name='receta_producto_ingrediente_unica',
            ),
        ]

    def __str__(self):
        return f'{self.ingrediente.nombre} para {self.producto.nombre}'

    def clean(self):
        if self.cantidad is not None and self.cantidad <= 0:
            raise ValidationError({'cantidad': 'La cantidad debe ser mayor que cero.'})
        if self.producto_id and self.ingrediente_id:
            duplicada = RecetaProducto.objects.filter(
                producto_id=self.producto_id,
                ingrediente_id=self.ingrediente_id,
            )
            if self.pk:
                duplicada = duplicada.exclude(pk=self.pk)
            if duplicada.exists():
                raise ValidationError(
                    'Este ingrediente ya está en la receta de este producto.'
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class MovimientoInventario(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = 'ENTRADA', 'Entrada'
        SALIDA = 'SALIDA', 'Salida'
        AJUSTE_POSITIVO = 'AJUSTE_POSITIVO', 'Ajuste positivo'
        AJUSTE_NEGATIVO = 'AJUSTE_NEGATIVO', 'Ajuste negativo'

    AUMENTAN_STOCK = [Tipo.ENTRADA, Tipo.AJUSTE_POSITIVO]
    REDUCEN_STOCK = [Tipo.SALIDA, Tipo.AJUSTE_NEGATIVO]

    ingrediente = models.ForeignKey(
        Ingrediente,
        on_delete=models.PROTECT,
        related_name='movimientos',
    )
    pedido = models.ForeignKey(
        'pedidos.Pedido',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='movimientos_inventario',
    )
    compra = models.ForeignKey(
        'compras.Compra',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='movimientos_inventario',
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)
    stock_anterior = models.DecimalField(
        max_digits=12, decimal_places=3, editable=False
    )
    stock_resultante = models.DecimalField(
        max_digits=12, decimal_places=3, editable=False
    )
    motivo = models.CharField(max_length=200)
    referencia = models.CharField(max_length=100, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos_inventario',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_creacion', '-id']
        verbose_name = 'Movimiento de inventario'
        verbose_name_plural = 'Movimientos de inventario'
        constraints = [
            models.UniqueConstraint(
                fields=['tipo', 'pedido', 'ingrediente'],
                condition=models.Q(pedido__isnull=False),
                name='movimiento_pedido_tipo_ingrediente_unica',
            ),
            models.UniqueConstraint(
                fields=['tipo', 'compra', 'ingrediente'],
                condition=models.Q(compra__isnull=False),
                name='movimiento_compra_tipo_ingrediente_unica',
            ),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()} {self.cantidad} de {self.ingrediente.nombre}'

    def clean(self):
        if self.cantidad is not None and self.cantidad <= 0:
            raise ValidationError({'cantidad': 'La cantidad debe ser mayor que cero.'})

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError('Un movimiento ya creado no puede modificarse.')
        with transaction.atomic():
            ingrediente = Ingrediente.objects.select_for_update().get(
                pk=self.ingrediente_id
            )
            self.ingrediente = ingrediente
            self.full_clean()
            self.stock_anterior = ingrediente.stock_actual
            if self.tipo in self.AUMENTAN_STOCK:
                self.stock_resultante = self.stock_anterior + self.cantidad
            elif self.tipo in self.REDUCEN_STOCK:
                self.stock_resultante = self.stock_anterior - self.cantidad
                if self.stock_resultante < 0:
                    raise ValidationError(
                        'No hay suficiente stock disponible para este movimiento.'
                    )
            super().save(*args, **kwargs)
            ingrediente.stock_actual = self.stock_resultante
            ingrediente.save(update_fields=['stock_actual', 'fecha_actualizacion'])

    def delete(self, *args, **kwargs):
        raise ValidationError('No se puede eliminar un movimiento de inventario.')
