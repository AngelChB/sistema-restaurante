from django.urls import path

from . import views

urlpatterns = [
    path('', views.panel_cocina, name='panel_cocina'),
    path(
        '<int:pk>/actualizar-estado/',
        views.actualizar_estado_cocina,
        name='actualizar_estado_cocina',
    ),
]
