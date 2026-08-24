from django.urls import path

from . import views

urlpatterns = [
    path('', views.lista_empleados, name='lista_empleados'),
    path('nuevo/', views.crear_empleado, name='crear_empleado'),
    path('<int:pk>/editar/', views.editar_empleado, name='editar_empleado'),
    path(
        '<int:pk>/password/',
        views.cambiar_password_empleado,
        name='cambiar_password_empleado',
    ),
    path(
        '<int:pk>/usuario/',
        views.cambiar_usuario_empleado,
        name='cambiar_usuario_empleado',
    ),
    path(
        '<int:pk>/estado/',
        views.alternar_estado_empleado,
        name='alternar_estado_empleado',
    ),
]
