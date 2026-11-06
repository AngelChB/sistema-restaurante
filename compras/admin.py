from django.contrib import admin

from .models import Compra, DetalleCompra, Proveedor


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = (
        'razon_social',
        'ruc',
        'contacto',
        'telefono',
        'activo',
    )
    search_fields = ('razon_social', 'ruc', 'contacto', 'telefono')
    list_filter = ('activo',)


class DetalleCompraInline(admin.TabularInline):
    model = DetalleCompra
    extra = 1
    autocomplete_fields = ('ingrediente',)

    def _editable(self, obj):
        return obj is None or obj.estado == Compra.Estado.BORRADOR

    def has_add_permission(self, request, obj=None):
        return self._editable(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._editable(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._editable(obj) and super().has_delete_permission(request, obj)


@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'numero_documento',
        'proveedor',
        'estado',
        'fecha_documento',
        'total',
        'usuario',
        'fecha_recepcion',
    )
    list_filter = ('estado', 'proveedor', 'fecha_documento')
    search_fields = ('numero_documento', 'proveedor__razon_social')
    date_hierarchy = 'fecha_documento'
    autocomplete_fields = ('proveedor',)
    inlines = [DetalleCompraInline]

    def get_readonly_fields(self, request, obj=None):
        if obj is not None and obj.estado != Compra.Estado.BORRADOR:
            return [f.name for f in self.model._meta.fields]
        return ['usuario', 'fecha_recepcion', 'estado']

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.estado != Compra.Estado.BORRADOR:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # La eliminación masiva de Django omite Model.delete().
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)


@admin.register(DetalleCompra)
class DetalleCompraAdmin(admin.ModelAdmin):
    list_display = (
        'compra',
        'ingrediente',
        'cantidad',
        'costo_unitario',
        'subtotal',
    )
    search_fields = (
        'compra__numero_documento',
        'ingrediente__nombre',
    )
    autocomplete_fields = ('ingrediente',)

    def has_add_permission(self, request):
        # Los detalles se gestionan en el formulario de la compra.
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
