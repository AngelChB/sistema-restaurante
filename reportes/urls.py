from django.urls import path

from . import views

urlpatterns = [
    path('', views.reporte_ventas, name='reporte_ventas'),
    path('exportar/csv/', views.exportar_ventas_csv, name='exportar_ventas_csv'),
]
