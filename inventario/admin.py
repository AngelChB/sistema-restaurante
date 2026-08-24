from django.contrib import admin

from .models import Ingrediente, MovimientoInventario, RecetaProducto, UnidadMedida


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'abreviatura', 'activo')
    search_fields = ('nombre', 'abreviatura')
    list_filter = ('activo',)


@admin.register(Ingrediente)
class IngredienteAdmin(admin.ModelAdmin):
    list_display = (
        'nombre',
        'unidad_medida',
        'stock_actual',
        'stock_minimo',
        'bajo_stock',
        'activo',
    )
    search_fields = ('nombre',)
    list_filter = ('activo', 'unidad_medida')
    list_select_related = ('unidad_medida',)
    readonly_fields = ('stock_actual',)


@admin.register(RecetaProducto)
class RecetaProductoAdmin(admin.ModelAdmin):
    list_display = ('producto', 'ingrediente', 'cantidad')
    search_fields = ('producto__nombre', 'ingrediente__nombre')
    list_filter = ('producto', 'producto__categoria')
    autocomplete_fields = ('producto', 'ingrediente')


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = (
        'fecha_creacion',
        'ingrediente',
        'pedido',
        'compra',
        'tipo',
        'cantidad',
        'stock_anterior',
        'stock_resultante',
        'usuario',
        'motivo',
    )
    list_filter = ('tipo', 'ingrediente', 'fecha_creacion')
    search_fields = (
        'ingrediente__nombre',
        'motivo',
        'referencia',
        'pedido__id',
        'compra__id',
    )
    date_hierarchy = 'fecha_creacion'
    list_select_related = ('ingrediente', 'pedido', 'compra', 'usuario')

    def get_readonly_fields(self, request, obj=None):
        if obj is not None:
            return [f.name for f in self.model._meta.fields]
        return ['usuario', 'stock_anterior', 'stock_resultante']

    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)
