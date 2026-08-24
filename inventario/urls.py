from django.urls import path

from . import views

urlpatterns = [
    path('', views.panel_inventario, name='panel_inventario'),
    path('ingredientes/', views.lista_ingredientes, name='lista_ingredientes'),
    path('ingredientes/nuevo/', views.crear_ingrediente, name='crear_ingrediente'),
    path(
        'ingredientes/<int:pk>/editar/',
        views.editar_ingrediente,
        name='editar_ingrediente',
    ),
    path('movimientos/', views.historial_movimientos, name='historial_movimientos'),
    path('movimientos/nuevo/', views.registrar_movimiento, name='registrar_movimiento'),
    path('unidades/', views.lista_unidades, name='lista_unidades'),
    path('unidades/nueva/', views.crear_unidad, name='crear_unidad'),
    path('unidades/<int:pk>/editar/', views.editar_unidad, name='editar_unidad'),
    path('recetas/', views.lista_recetas, name='lista_recetas'),
    path('recetas/nueva/', views.crear_receta, name='crear_receta'),
    path('recetas/<int:pk>/editar/', views.editar_receta, name='editar_receta'),
]
