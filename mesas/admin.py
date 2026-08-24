from django.contrib import admin

from .models import Mesa


@admin.register(Mesa)
class MesaAdmin(admin.ModelAdmin):
    list_display = ('numero', 'capacidad', 'estado', 'ubicacion', 'activo')
    list_filter = ('estado', 'activo')
    search_fields = ('numero', 'ubicacion')
    list_editable = ('estado',)