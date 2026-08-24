from django.contrib import admin

from .models import DetallePedido, Pedido


class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0
    autocomplete_fields = ('producto',)
    readonly_fields = ('precio_unitario',)


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'mesa', 'mesero', 'estado', 'total', 'fecha_creacion')
    list_filter = ('estado', 'mesa', 'fecha_creacion')
    search_fields = ('id', 'mesa__numero', 'mesero__username')
    list_editable = ('estado',)
    readonly_fields = ('total',)
    inlines = (DetallePedidoInline,)
