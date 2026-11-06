from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from caja.models import Pago
from catalogo.models import Categoria, Producto
from mesas.models import Mesa
from pedidos.models import DetallePedido, Pedido
from reservas.models import Cliente


class PaginacionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='paginas', password='Clave123!'
        )
        self.client.force_login(self.user)

    def test_clientes_se_dividen_en_paginas_y_conservan_busqueda(self):
        Cliente.objects.bulk_create(
            [Cliente(nombres='Cliente ' + str(i), telefono='999') for i in range(31)]
        )
        r1 = self.client.get(
            reverse('lista_clientes'), {'buscar': 'Cliente', 'pagina': 1}
        )
        r2 = self.client.get(
            reverse('lista_clientes'), {'buscar': 'Cliente', 'pagina': 2}
        )
        p1, p2 = r1.context['clientes'], r2.context['clientes']
        self.assertEqual(len(p1), 25)
        self.assertEqual(len(p2), 6)
        self.assertFalse({c.pk for c in p1} & {c.pk for c in p2})
        self.assertIn('buscar=Cliente', p1.url_siguiente)
        self.assertIn('pagina=2', p1.url_siguiente)

    def test_pagina_invalida_no_provoca_error(self):
        for valor in ['abc', '0', '-1', '999999999999999999999999']:
            with self.subTest(valor=valor):
                response = self.client.get(reverse('lista_clientes'), {'pagina': valor})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['clientes'].number, 1)

    def test_listados_vacios_tienen_pagina_valida(self):
        for ruta, nombre in [
            ('lista_pedidos', 'pedidos'),
            ('lista_compras', 'compras'),
            ('historial_movimientos', 'movimientos'),
            ('lista_reservas', 'reservas'),
            ('lista_empleados', 'usuarios'),
        ]:
            with self.subTest(ruta=ruta):
                response = self.client.get(reverse(ruta))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context[nombre].paginator.per_page, 25)

    def test_paginar_caja_no_reduce_totales(self):
        categoria = Categoria.objects.create(nombre='Menú')
        producto = Producto.objects.create(
            categoria=categoria, nombre='Plato', precio=10
        )
        mesa = Mesa.objects.create(numero=1, capacidad=4)
        for _ in range(26):
            pedido = Pedido.objects.create(
                mesa=mesa, mesero=self.user, estado='ABIERTO'
            )
            DetallePedido.objects.create(pedido=pedido, producto=producto, cantidad=1)
            pedido.estado = Pedido.Estado.ENTREGADO
            pedido.save()
            Pago.objects.create(
                pedido=pedido,
                cajero=self.user,
                metodo='EFECTIVO',
                monto=10,
                monto_recibido=10,
            )
        response = self.client.get(
            reverse('panel_caja'), {'pagina_pagos': 2, 'pagina_pendientes': 1}
        )
        self.assertEqual(len(response.context['pagos']), 1)
        self.assertEqual(response.context['cantidad_pagos'], 26)
        self.assertEqual(response.context['total_dia'], Decimal('260'))
        self.assertIn('pagina_pendientes=1', response.context['pagos'].url_anterior)

    def test_paginacion_no_expone_pedidos_ajenos(self):
        from personal.models import PerfilEmpleado

        otro = get_user_model().objects.create_user(username='mesero')
        PerfilEmpleado.objects.create(usuario=otro, rol='MESERO')
        mesa = Mesa.objects.create(numero=1, capacidad=4)
        Pedido.objects.create(mesa=mesa, mesero=self.user)
        self.client.force_login(otro)
        response = self.client.get(reverse('lista_pedidos'))
        self.assertEqual(response.context['pedidos'].paginator.count, 0)

    def test_paneles_incluyen_actualizacion_y_control_de_pausa(self):
        for ruta in ['panel_cocina', 'panel_sala']:
            response = self.client.get(reverse(ruta))
            self.assertContains(response, 'data-panel-live')
            self.assertContains(response, 'alternar-actualizacion')
            self.assertContains(response, 'js/panel-live.js')
