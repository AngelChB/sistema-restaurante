from django.urls import path

from . import views

urlpatterns = [
    path('', views.panel_sala, name='panel_sala'),
    path('<int:pk>/entregar/', views.marcar_pedido_entregado, name='marcar_pedido_entregado'),
]
