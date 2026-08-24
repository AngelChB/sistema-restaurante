from django.urls import path

from . import views

urlpatterns = [
    path('', views.lista_mesas, name='lista_mesas'),
    path('nueva/', views.crear_mesa, name='crear_mesa'),
    path('<int:pk>/editar/', views.editar_mesa, name='editar_mesa'),
]
