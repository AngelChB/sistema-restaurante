from django.urls import path

from . import views

urlpatterns = [
    path('proveedores/', views.lista_proveedores, name='lista_proveedores'),
    path(
        'proveedores/nuevo/',
        views.crear_proveedor,
        name='crear_proveedor',
    ),
    path(
        'proveedores/<int:pk>/editar/',
        views.editar_proveedor,
        name='editar_proveedor',
    ),
    path('', views.lista_compras, name='lista_compras'),
    path('nueva/', views.crear_compra, name='crear_compra'),
    path('<int:pk>/editar/', views.editar_compra, name='editar_compra'),
    path('<int:pk>/', views.detalle_compra, name='detalle_compra'),
    path(
        '<int:pk>/recibir/',
        views.recibir_compra_view,
        name='recibir_compra',
    ),
    path(
        '<int:pk>/cancelar/',
        views.cancelar_compra,
        name='cancelar_compra',
    ),
]
