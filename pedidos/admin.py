from django.contrib import admin

from .models import DetallePedido, Pedido


class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0
    autocomplete_fields = ('producto',)
    readonly_fields = ('precio_unitario',)

    def _editable(self, obj):
        return obj is None or obj.estado == Pedido.Estado.ABIERTO

    def has_add_permission(self, request, obj=None):
        return self._editable(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._editable(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._editable(obj) and super().has_delete_permission(request, obj)



@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'mesa', 'mesero', 'estado', 'total', 'fecha_creacion')
    list_filter = ('estado', 'mesa', 'fecha_creacion')
    search_fields = ('id', 'mesa__numero', 'mesero__username')
    readonly_fields = ('total', 'estado')

    def has_change_permission(self, request, obj=None):
        return (obj is None or obj.estado == Pedido.Estado.ABIERTO) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False
    inlines = (DetallePedidoInline,)
