from django.contrib import admin

from .models import CierreCaja, Pago


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'pedido',
        'cajero',
        'metodo',
        'monto',
        'vuelto',
        'fecha_pago',
    )
    list_filter = ('metodo', 'fecha_pago')
    search_fields = ('pedido__id', 'cajero__username', 'referencia')
    date_hierarchy = 'fecha_pago'
    readonly_fields = ('pedido', 'cajero')

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj:
            readonly.extend(['metodo', 'monto', 'monto_recibido', 'vuelto'])
        return readonly

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CierreCaja)
class CierreCajaAdmin(admin.ModelAdmin):
    list_display = (
        'fecha_operacion',
        'responsable',
        'cantidad_pagos',
        'total_ventas',
        'efectivo_esperado',
        'efectivo_contado',
        'diferencia',
        'fecha_cierre',
    )
    list_filter = ('fecha_operacion',)
    search_fields = ('responsable__username', 'responsable__first_name')
    date_hierarchy = 'fecha_operacion'
    readonly_fields = (
        'efectivo_ventas',
        'efectivo_esperado',
        'diferencia',
        'total_tarjeta',
        'total_yape',
        'total_plin',
        'total_ventas',
        'cantidad_pagos',
        'fecha_cierre',
    )

    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False
