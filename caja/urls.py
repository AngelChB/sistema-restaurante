from django.urls import path

from . import views

urlpatterns = [
    path('', views.panel_caja, name='panel_caja'),
    path(
        'pedido/<int:pedido_id>/pagar/',
        views.registrar_pago,
        name='registrar_pago',
    ),
    path('pago/<int:pk>/', views.detalle_pago, name='detalle_pago'),
    path('cerrar/', views.cerrar_caja, name='cerrar_caja'),
    path('cierres/<int:pk>/', views.detalle_cierre, name='detalle_cierre'),
]
