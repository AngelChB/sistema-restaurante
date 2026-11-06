from caja.models import Pago
from pedidos.models import DetallePedido
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalogo.models import Categoria, Producto
from inventario.models import Ingrediente, MovimientoInventario, RecetaProducto, UnidadMedida
from mesas.models import Mesa
from pedidos.models import DetallePedido, Pedido
from personal.models import PerfilEmpleado


class CocinaViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='mesero1', password='test12345'
        )
        self.cocinero = User.objects.create_user(
            username='cocinero', password='test12345'
        )
        PerfilEmpleado.objects.create(
            usuario=self.cocinero, rol=PerfilEmpleado.Rol.COCINA
        )
        self.categoria = Categoria.objects.create(nombre='Bebidas')
        self.producto = Producto.objects.create(
            categoria=self.categoria,
            nombre='Café',
            precio='12.50',
            disponible=True,
        )
        self.unidad = UnidadMedida.objects.create(
            nombre='Kilogramo', abreviatura='kg'
        )
        self.harina = Ingrediente.objects.create(
            nombre='Harina',
            unidad_medida=self.unidad,
            stock_actual=Decimal('100'),
            stock_minimo=Decimal('10'),
            costo_unitario=Decimal('5.00'),
        )
        RecetaProducto.objects.create(
            producto=self.producto,
            ingrediente=self.harina,
            cantidad=Decimal('0.5'),
        )
        self.mesa = Mesa.objects.create(numero=1, capacidad=4)

    def _crear_pedido(self, estado):
        if estado != Pedido.Estado.PAGADO:
            return Pedido.objects.create(mesa=self.mesa, mesero=self.user, estado=estado)
        pedido = Pedido.objects.create(mesa=self.mesa, mesero=self.user)
        DetallePedido.objects.create(pedido=pedido, producto=self.producto, cantidad=1)
        pedido.estado = Pedido.Estado.ENTREGADO
        pedido.save()
        Pago.objects.create(pedido=pedido, cajero=self.user, metodo='EFECTIVO',
                            monto=pedido.total, monto_recibido=pedido.total)
        pedido.refresh_from_db()
        return pedido

    def _crear_pedido_abierto_con_detalle(self, cantidad=1):
        pedido = self._crear_pedido(Pedido.Estado.ABIERTO)
        DetallePedido.objects.create(
            pedido=pedido, producto=self.producto, cantidad=cantidad
        )
        return pedido

    def test_visitante_no_autenticado_es_redirigido_al_login(self):
        response = self.client.get(reverse('panel_cocina'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('panel_cocina')}",
        )

    def test_usuario_autenticado_puede_abrir_el_panel(self):
        self.client.login(username='cocinero', password='test12345')
        response = self.client.get(reverse('panel_cocina'))
        self.assertEqual(response.status_code, 200)

    def test_el_panel_muestra_pedidos_abierto(self):
        pedido = self._crear_pedido(Pedido.Estado.ABIERTO)
        self.client.login(username='cocinero', password='test12345')
        response = self.client.get(reverse('panel_cocina'))
        self.assertContains(response, f'Pedido {pedido.pk}')
        self.assertContains(response, 'Comenzar preparación')

    def test_el_panel_muestra_pedidos_en_preparacion(self):
        pedido = self._crear_pedido(Pedido.Estado.EN_PREPARACION)
        self.client.login(username='cocinero', password='test12345')
        response = self.client.get(reverse('panel_cocina'))
        self.assertContains(response, f'Pedido {pedido.pk}')
        self.assertContains(response, 'Marcar como listo')

    def test_el_panel_muestra_pedidos_listo(self):
        pedido = self._crear_pedido(Pedido.Estado.LISTO)
        self.client.login(username='cocinero', password='test12345')
        response = self.client.get(reverse('panel_cocina'))
        self.assertContains(response, f'Pedido {pedido.pk}')
        self.assertContains(response, 'Esperando entrega')

    def test_el_panel_no_muestra_pedidos_pagado_ni_cancelado(self):
        pedido_pagado = self._crear_pedido(Pedido.Estado.PAGADO)
        pedido_cancelado = self._crear_pedido(Pedido.Estado.CANCELADO)
        self.client.login(username='cocinero', password='test12345')
        response = self.client.get(reverse('panel_cocina'))
        self.assertNotContains(response, f'Pedido {pedido_pagado.pk}')
        self.assertNotContains(response, f'Pedido {pedido_cancelado.pk}')

    def test_la_actualizacion_de_estado_no_acepta_get(self):
        pedido = self._crear_pedido(Pedido.Estado.ABIERTO)
        self.client.login(username='cocinero', password='test12345')
        response = self.client.get(
            reverse('actualizar_estado_cocina', args=[pedido.pk])
        )
        self.assertEqual(response.status_code, 405)

    def test_se_puede_cambiar_abierto_a_en_preparacion(self):
        pedido = self._crear_pedido_abierto_con_detalle()
        self.client.login(username='cocinero', password='test12345')
        response = self.client.post(
            reverse('actualizar_estado_cocina', args=[pedido.pk])
        )
        self.assertRedirects(response, reverse('panel_cocina'))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.EN_PREPARACION)
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock_actual, Decimal('99.5'))

    def test_se_puede_cambiar_en_preparacion_a_listo(self):
        pedido = self._crear_pedido(Pedido.Estado.EN_PREPARACION)
        self.client.login(username='cocinero', password='test12345')
        response = self.client.post(
            reverse('actualizar_estado_cocina', args=[pedido.pk])
        )
        self.assertRedirects(response, reverse('panel_cocina'))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.LISTO)

    def test_no_se_puede_cambiar_abierto_directamente_a_listo(self):
        pedido = self._crear_pedido_abierto_con_detalle()
        self.client.login(username='cocinero', password='test12345')
        response = self.client.post(
            reverse('actualizar_estado_cocina', args=[pedido.pk])
        )
        self.assertRedirects(response, reverse('panel_cocina'))
        pedido.refresh_from_db()
        self.assertNotEqual(pedido.estado, Pedido.Estado.LISTO)
        self.assertEqual(pedido.estado, Pedido.Estado.EN_PREPARACION)

    def test_no_se_puede_modificar_un_pedido_pagado_desde_cocina(self):
        pedido = self._crear_pedido(Pedido.Estado.PAGADO)
        self.client.login(username='cocinero', password='test12345')
        response = self.client.post(
            reverse('actualizar_estado_cocina', args=[pedido.pk])
        )
        self.assertRedirects(response, reverse('panel_cocina'))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.PAGADO)

    def test_el_panel_indica_que_se_descontaran_los_ingredientes(self):
        self.client.login(username='cocinero', password='test12345')
        response = self.client.get(reverse('panel_cocina'))
        self.assertContains(
            response,
            'Al comenzar se descontarán automáticamente los ingredientes.',
        )

    def test_al_comenzar_la_preparacion_se_descuentan_los_ingredientes(self):
        pedido = self._crear_pedido_abierto_con_detalle()
        self.client.login(username='cocinero', password='test12345')
        response = self.client.post(
            reverse('actualizar_estado_cocina', args=[pedido.pk])
        )
        self.assertRedirects(response, reverse('panel_cocina'))
        movimiento = MovimientoInventario.objects.get(pedido=pedido)
        self.assertEqual(movimiento.tipo, MovimientoInventario.Tipo.SALIDA)
        self.assertEqual(movimiento.cantidad, Decimal('0.5'))
        self.assertEqual(movimiento.usuario, self.cocinero)
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock_actual, Decimal('99.5'))

    def test_un_producto_sin_receta_impide_comenzar_y_muestra_el_error(self):
        producto_sin_receta = Producto.objects.create(
            categoria=self.categoria,
            nombre='Jugo',
            precio='9.00',
            disponible=True,
        )
        pedido = self._crear_pedido(Pedido.Estado.ABIERTO)
        DetallePedido.objects.create(
            pedido=pedido, producto=producto_sin_receta, cantidad=1
        )
        self.client.login(username='cocinero', password='test12345')
        response = self.client.post(
            reverse('actualizar_estado_cocina', args=[pedido.pk]),
            follow=True,
        )
        mensajes = [str(m) for m in response.context.get('messages')]
        self.assertTrue(any('Jugo' in mensaje for mensaje in mensajes))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.ABIERTO)
        self.assertEqual(MovimientoInventario.objects.count(), 0)

    def test_el_stock_insuficiente_impide_comenzar_y_muestra_el_error(self):
        self.harina.stock_actual = Decimal('0.1')
        self.harina.save()
        pedido = self._crear_pedido_abierto_con_detalle()
        self.client.login(username='cocinero', password='test12345')
        response = self.client.post(
            reverse('actualizar_estado_cocina', args=[pedido.pk]),
            follow=True,
        )
        mensajes = [str(m) for m in response.context.get('messages')]
        self.assertTrue(
            any('suficiente stock' in mensaje for mensaje in mensajes)
        )
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.ABIERTO)
        self.assertEqual(MovimientoInventario.objects.count(), 0)
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock_actual, Decimal('0.1'))

    def test_cambiar_en_preparacion_a_listo_no_vuelve_a_descontar(self):
        pedido = self._crear_pedido_abierto_con_detalle()
        self.client.login(username='cocinero', password='test12345')
        self.client.post(
            reverse('actualizar_estado_cocina', args=[pedido.pk])
        )
        self.harina.refresh_from_db()
        stock_descontado = self.harina.stock_actual
        response = self.client.post(
            reverse('actualizar_estado_cocina', args=[pedido.pk])
        )
        self.assertRedirects(response, reverse('panel_cocina'))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.LISTO)
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock_actual, stock_descontado)
        self.assertEqual(
            MovimientoInventario.objects.filter(pedido=pedido).count(), 1
        )
