from django.contrib import admin

from .models import PerfilEmpleado


@admin.register(PerfilEmpleado)
class PerfilEmpleadoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'nombres', 'rol', 'telefono', 'usuario_activo')
    list_filter = ('rol', 'usuario__is_active')
    search_fields = (
        'usuario__username',
        'usuario__first_name',
        'usuario__last_name',
        'usuario__email',
    )
    autocomplete_fields = ('usuario',)

    @admin.display(description='Nombres')
    def nombres(self, obj):
        return obj.usuario.get_full_name() or obj.usuario.username

    @admin.display(description='Activo', boolean=True)
    def usuario_activo(self, obj):
        return obj.usuario.is_active
