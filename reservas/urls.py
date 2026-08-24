from django.urls import path

from . import views

urlpatterns = [
    path('', views.lista_reservas, name='lista_reservas'),
    path('nueva/', views.crear_reserva, name='crear_reserva'),
    path('<int:pk>/', views.detalle_reserva, name='detalle_reserva'),
    path('<int:pk>/editar/', views.editar_reserva, name='editar_reserva'),
    path('<int:pk>/confirmar/', views.confirmar_reserva, name='confirmar_reserva'),
    path('<int:pk>/cancelar/', views.cancelar_reserva, name='cancelar_reserva'),
    path('<int:pk>/atender/', views.atender_reserva, name='atender_reserva'),
    path('<int:pk>/no-asistio/', views.no_asistio_reserva, name='no_asistio_reserva'),
    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('clientes/nuevo/', views.crear_cliente, name='crear_cliente'),
    path('clientes/<int:pk>/editar/', views.editar_cliente, name='editar_cliente'),
]
