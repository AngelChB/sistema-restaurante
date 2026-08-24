from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('cuentas/', include('django.contrib.auth.urls')),
    path('mesas/', include('mesas.urls')),
    path('catalogo/', include('catalogo.urls')),
    path('pedidos/', include('pedidos.urls')),
    path('cocina/', include('cocina.urls')),
    path('sala/', include('sala.urls')),
    path('caja/', include('caja.urls')),
    path('inventario/', include('inventario.urls')),
    path('compras/', include('compras.urls')),
    path('reservas/', include('reservas.urls')),
    path('personal/', include('personal.urls')),
    path('reportes/', include('reportes.urls')),
    path('', include('core.urls')),
]
