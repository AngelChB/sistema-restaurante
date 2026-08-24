from django.contrib import admin

from .models import Cliente, Reserva


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombres', 'apellidos', 'documento', 'telefono', 'activo')
    search_fields = ('nombres', 'apellidos', 'documento', 'telefono')
    list_filter = ('activo',)


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'cliente',
        'mesa',
        'fecha_hora',
        'cantidad_personas',
        'estado',
        'usuario',
    )
    list_filter = ('estado', 'mesa', 'fecha_hora')
    search_fields = (
        'cliente__nombres',
        'cliente__apellidos',
        'cliente__telefono',
        'mesa__numero',
    )
    date_hierarchy = 'fecha_hora'
    autocomplete_fields = ('cliente',)
