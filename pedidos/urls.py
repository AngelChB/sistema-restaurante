from django.urls import path

from . import views

urlpatterns = [
    path('', views.lista_pedidos, name='lista_pedidos'),
    path('nuevo/', views.crear_pedido, name='crear_pedido'),
    path('<int:pk>/', views.detalle_pedido, name='detalle_pedido'),
    path('<int:pk>/cambiar-estado/', views.cambiar_estado_pedido, name='cambiar_estado_pedido'),
]
