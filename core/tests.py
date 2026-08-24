from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from caja.models import Pago
from catalogo.models import Categoria, Producto
from compras.models import Compra, Proveedor
from inventario.models import Ingrediente, UnidadMedida
from mesas.models import Mesa
from pedidos.models import DetallePedido, Pedido
from personal.models import PerfilEmpleado
from reservas.models import Cliente, Reserva


def _crear_usuario(username, rol):
    user = get_user_model().objects.create_user(
        username=username, password='test12345'
    )
    PerfilEmpleado.objects.create(usuario=user, rol=rol)
    return user


class DashboardTests(TestCase):
    def setUp(self):
        self.mesero = _crear_usuario('mesero1', PerfilEmpleado.Rol.MESERO)
        self.user = self.mesero
        self.administrador = _crear_usuario(
            'admin1', PerfilEmpleado.Rol.ADMINISTRADOR
        )
        self.cocina = _crear_usuario('cocina1', PerfilEmpleado.Rol.COCINA)
        self.cajero = _crear_usuario('cajero1', PerfilEmpleado.Rol.CAJERO)

    def test_usuario_no_autenticado_es_redirigido_al_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('dashboard')}",
        )

    def test_usuario_autenticado_puede_abrir_el_dashboard(self):
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_responde_con_estado_http_200(self):
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_administrador_puede_abrir_el_dashboard(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_mesero_puede_abrir_el_dashboard(self):
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_cocina_puede_abrir_el_dashboard(self):
        self.client.login(username='cocina1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_cajero_puede_abrir_el_dashboard(self):
        self.client.login(username='cajero1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def _crear_pedido_entregado_y_pago(self, mesero, cajero, monto=None):
        mesa = Mesa.objects.create(numero=99, capacidad=4)
        categoria = Categoria.objects.create(nombre='Bebidas')
        producto = Producto.objects.create(
            categoria=categoria, nombre='Agua', precio=Decimal('10.00')
        )
        pedido = Pedido.objects.create(
            mesa=mesa, mesero=mesero, estado=Pedido.Estado.ENTREGADO
        )
        DetallePedido.objects.create(pedido=pedido, producto=producto, cantidad=2)
        if monto is None:
            monto = pedido.total
        return Pago.objects.create(
            pedido=pedido,
            cajero=cajero,
            metodo=Pago.Metodo.EFECTIVO,
            monto=monto,
            monto_recibido=monto,
        )

    def test_ventas_de_hoy_se_calculan_correctamente(self):
        self._crear_pedido_entregado_y_pago(self.mesero, self.cajero)
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['ventas_hoy'], Decimal('20.00'))
        self.assertEqual(response.context['cantidad_pagos_hoy'], 1)
        self.assertEqual(response.context['ticket_promedio'], Decimal('20.00'))

    def test_pagos_de_otros_dias_no_aparecen_en_ventas_de_hoy(self):
        pago = self._crear_pedido_entregado_y_pago(self.mesero, self.cajero)
        Pago.objects.filter(pk=pago.pk).update(
            fecha_pago=timezone.now() - timedelta(days=1)
        )
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['ventas_hoy'], Decimal('0'))

    def test_pedidos_activos_se_contabilizan_correctamente(self):
        mesa1 = Mesa.objects.create(numero=1, capacidad=4)
        mesa2 = Mesa.objects.create(numero=2, capacidad=4)
        Pedido.objects.create(
            mesa=mesa1, mesero=self.mesero, estado=Pedido.Estado.ABIERTO
        )
        Pedido.objects.create(
            mesa=mesa2,
            mesero=self.mesero,
            estado=Pedido.Estado.EN_PREPARACION,
        )
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['pedidos_activos_cantidad'], 2)
        self.assertEqual(response.context['cantidad_abiertos'], 1)
        self.assertEqual(response.context['cantidad_en_preparacion'], 1)

    def test_mesero_solo_ve_sus_propios_pedidos_activos(self):
        otro_mesero = _crear_usuario('mesero2', PerfilEmpleado.Rol.MESERO)
        mesa = Mesa.objects.create(numero=1, capacidad=4)
        Pedido.objects.create(
            mesa=mesa, mesero=self.mesero, estado=Pedido.Estado.ABIERTO
        )
        self.client.login(username='mesero2', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['pedidos_activos_cantidad'], 0)

    def test_reservas_de_hoy_se_contabilizan_correctamente(self):
        mesa = Mesa.objects.create(numero=1, capacidad=4)
        cliente = Cliente.objects.create(
            nombres='Juan', apellidos='Pérez', telefono='987654321'
        )
        tz = timezone.get_current_timezone()
        fecha_controlada = timezone.localdate() + timedelta(days=10)

        def _fecha_local_en(dia):
            return timezone.make_aware(
                datetime.combine(dia, time(12, 0)), tz
            )

        Reserva.objects.create(
            cliente=cliente,
            mesa=mesa,
            usuario=self.mesero,
            fecha_hora=_fecha_local_en(fecha_controlada),
            cantidad_personas=2,
        )
        Reserva.objects.create(
            cliente=cliente,
            mesa=mesa,
            usuario=self.mesero,
            fecha_hora=_fecha_local_en(fecha_controlada + timedelta(days=1)),
            cantidad_personas=2,
        )
        self.client.login(username='admin1', password='test12345')
        with mock.patch(
            'core.views.timezone.localdate', return_value=fecha_controlada
        ):
            response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['cantidad_reservas_hoy'], 1)
        self.assertEqual(response.context['cantidad_pendientes'], 1)

    def test_bajo_stock_se_contabiliza_correctamente(self):
        unidad = UnidadMedida.objects.create(
            nombre='Kilogramo', abreviatura='kg'
        )
        Ingrediente.objects.create(
            nombre='Harina',
            unidad_medida=unidad,
            stock_actual=Decimal('5'),
            stock_minimo=Decimal('10'),
        )
        Ingrediente.objects.create(
            nombre='Azúcar',
            unidad_medida=unidad,
            stock_actual=Decimal('0'),
            stock_minimo=Decimal('5'),
        )
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['bajo_stock'], 2)
        self.assertEqual(response.context['sin_stock'], 1)

    def test_compras_en_borrador_se_contabilizan_correctamente(self):
        proveedor = Proveedor.objects.create(
            razon_social='Distribuidora del Norte', ruc='20123456789'
        )
        Compra.objects.create(
            proveedor=proveedor,
            usuario=self.administrador,
            estado=Compra.Estado.BORRADOR,
            fecha_documento=timezone.localdate(),
        )
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['cantidad_compras_borrador'], 1)

    def test_mesero_no_ve_informacion_de_caja(self):
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Ventas de hoy')
        self.assertNotContains(response, 'Ticket promedio')

    def test_cocina_no_ve_informacion_de_ventas(self):
        self.client.login(username='cocina1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Ventas de hoy')

    def test_cajero_no_ve_controles_de_inventario(self):
        self.client.login(username='cajero1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Alertas de inventario')
        self.assertNotContains(response, 'Bajo stock')

    def test_administrador_ve_todas_las_secciones(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Ventas de hoy')
        self.assertContains(response, 'Pedidos activos')
        self.assertContains(response, 'Mesas libres')
        self.assertContains(response, 'Reservas de hoy')
        self.assertContains(response, 'Bajo stock')
        self.assertContains(response, 'Compras pendientes')
        self.assertContains(response, 'Estado de mesas')
        self.assertContains(response, 'Próximas reservas')
        self.assertContains(response, 'Alertas de inventario')
