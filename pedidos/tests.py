from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from catalogo.models import Categoria, Producto
from mesas.models import Mesa
from pedidos.models import DetallePedido, Pedido
from personal.models import PerfilEmpleado


class PedidoModelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.mesero = User.objects.create_user(
            username='mesero1', password='test12345'
        )
        self.categoria = Categoria.objects.create(nombre='Bebidas')
        self.producto = Producto.objects.create(
            categoria=self.categoria,
            nombre='Café',
            precio=Decimal('12.50'),
            disponible=True,
        )
        self.mesa = Mesa.objects.create(numero=1, capacidad=4)

    def _crear_pedido(self, mesa=None, estado=Pedido.Estado.ABIERTO):
        return Pedido.objects.create(
            mesa=mesa or self.mesa,
            mesero=self.mesero,
            estado=estado,
        )

    def test_detalle_copia_automaticamente_el_precio_del_producto(self):
        pedido = self._crear_pedido()
        detalle = DetallePedido.objects.create(
            pedido=pedido, producto=self.producto, cantidad=2
        )
        self.assertEqual(detalle.precio_unitario, Decimal('12.50'))

    def test_cambio_de_precio_del_producto_no_afecta_el_historico(self):
        pedido = self._crear_pedido()
        detalle = DetallePedido.objects.create(
            pedido=pedido, producto=self.producto, cantidad=1
        )
        self.producto.precio = Decimal('99.00')
        self.producto.save()
        detalle.refresh_from_db()
        self.assertEqual(detalle.precio_unitario, Decimal('12.50'))

    def test_pedido_activo_cambia_la_mesa_a_ocupada(self):
        self._crear_pedido()
        self.mesa.refresh_from_db()
        self.assertEqual(self.mesa.estado, Mesa.Estado.OCUPADA)

    def test_pedido_pagado_cambia_la_mesa_a_libre(self):
        pedido = self._crear_pedido()
        DetallePedido.objects.create(pedido=pedido, producto=self.producto, cantidad=1)
        pedido.estado = Pedido.Estado.ENTREGADO
        pedido.save()
        from caja.models import Pago
        Pago.objects.create(pedido=pedido, cajero=self.mesero, metodo='EFECTIVO',
                            monto=pedido.total, monto_recibido=pedido.total)
        self.mesa.refresh_from_db()
        self.assertEqual(self.mesa.estado, Mesa.Estado.LIBRE)

    def test_pedido_cancelado_cambia_la_mesa_a_libre(self):
        pedido = self._crear_pedido()
        pedido.estado = Pedido.Estado.CANCELADO
        pedido.save()
        self.mesa.refresh_from_db()
        self.assertEqual(self.mesa.estado, Mesa.Estado.LIBRE)

    def test_no_se_permiten_dos_pedidos_activos_en_la_misma_mesa(self):
        self._crear_pedido()
        with self.assertRaises(ValidationError):
            self._crear_pedido()

    def test_no_se_permite_usar_una_mesa_fuera_de_servicio(self):
        self.mesa.estado = Mesa.Estado.FUERA_SERVICIO
        self.mesa.save()
        with self.assertRaises(ValidationError):
            self._crear_pedido()

    def test_no_se_permite_agregar_un_producto_no_disponible(self):
        self.producto.disponible = False
        self.producto.save()
        pedido = self._crear_pedido()
        with self.assertRaises(ValidationError):
            DetallePedido.objects.create(
                pedido=pedido, producto=self.producto, cantidad=1
            )


class PedidoViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='mesero1', password='test12345'
        )
        PerfilEmpleado.objects.create(
            usuario=self.user, rol=PerfilEmpleado.Rol.MESERO
        )
        self.categoria = Categoria.objects.create(nombre='Bebidas')
        self.producto = Producto.objects.create(
            categoria=self.categoria,
            nombre='Café',
            precio=Decimal('12.50'),
            disponible=True,
        )
        self.mesa = Mesa.objects.create(numero=1, capacidad=4)

    def _datos_crear(self, cantidad='2', producto=None, total_forms='1'):
        return {
            'mesa': self.mesa.pk,
            'observacion': '',
            'detalles-TOTAL_FORMS': total_forms,
            'detalles-INITIAL_FORMS': '0',
            'detalles-MIN_NUM_FORMS': '1',
            'detalles-MAX_NUM_FORMS': '1000',
            'detalles-0-producto': (producto or self.producto).pk,
            'detalles-0-cantidad': cantidad,
            'detalles-0-observacion': '',
        }

    def test_visitante_no_autenticado_es_redirigido_al_login(self):
        response = self.client.get(reverse('lista_pedidos'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('lista_pedidos')}",
        )

    def test_usuario_autenticado_puede_ver_la_lista_de_pedidos(self):
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('lista_pedidos'))
        self.assertEqual(response.status_code, 200)

    def test_la_lista_muestra_un_boton_ver_detalle(self):
        self.client.login(username='mesero1', password='test12345')
        pedido = Pedido.objects.create(mesa=self.mesa, mesero=self.user)
        response = self.client.get(reverse('lista_pedidos'))
        self.assertContains(response, 'Ver detalle')

    def test_el_boton_ver_detalle_lleva_al_pedido_correcto(self):
        self.client.login(username='mesero1', password='test12345')
        pedido = Pedido.objects.create(mesa=self.mesa, mesero=self.user)
        response = self.client.get(reverse('lista_pedidos'))
        self.assertContains(
            response,
            f'href="{reverse("detalle_pedido", args=[pedido.pk])}"',
        )

    def test_el_detalle_muestra_la_seccion_acciones(self):
        self.client.login(username='mesero1', password='test12345')
        pedido = Pedido.objects.create(mesa=self.mesa, mesero=self.user)
        response = self.client.get(reverse('detalle_pedido', args=[pedido.pk]))
        self.assertContains(response, 'Cancelar pedido')
        self.assertContains(response, 'Volver a pedidos')

    def test_un_pedido_entregado_no_ofrece_boton_cancelar(self):
        self.client.login(username='mesero1', password='test12345')
        pedido = Pedido.objects.create(
            mesa=self.mesa,
            mesero=self.user,
            estado=Pedido.Estado.ENTREGADO,
        )
        response = self.client.get(reverse('detalle_pedido', args=[pedido.pk]))
        self.assertNotContains(response, 'Cancelar pedido')
        self.assertContains(response, 'Volver a pedidos')

    def test_la_cancelacion_desde_el_detalle_funciona(self):
        self.client.login(username='mesero1', password='test12345')
        pedido = Pedido.objects.create(mesa=self.mesa, mesero=self.user)
        response = self.client.post(
            reverse('cambiar_estado_pedido', args=[pedido.pk]),
            {'estado': Pedido.Estado.CANCELADO},
        )
        self.assertRedirects(
            response, reverse('detalle_pedido', args=[pedido.pk])
        )
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.CANCELADO)

    def test_usuario_autenticado_puede_abrir_el_formulario(self):
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('crear_pedido'))
        self.assertEqual(response.status_code, 200)

    def test_se_puede_crear_un_pedido_con_un_detalle(self):
        self.client.login(username='mesero1', password='test12345')
        response = self.client.post(reverse('crear_pedido'), self._datos_crear())
        pedido = Pedido.objects.get(mesa=self.mesa)
        self.assertRedirects(response, reverse('detalle_pedido', args=[pedido.pk]))
        self.assertEqual(pedido.detalles.count(), 1)

    def test_el_mesero_se_asigna_al_usuario_autenticado(self):
        self.client.login(username='mesero1', password='test12345')
        self.client.post(reverse('crear_pedido'), self._datos_crear())
        pedido = Pedido.objects.get(mesa=self.mesa)
        self.assertEqual(pedido.mesero, self.user)

    def test_el_precio_se_copia_automaticamente_desde_el_producto(self):
        self.client.login(username='mesero1', password='test12345')
        self.client.post(reverse('crear_pedido'), self._datos_crear())
        detalle = DetallePedido.objects.get(pedido__mesa=self.mesa)
        self.assertEqual(detalle.precio_unitario, Decimal('12.50'))

    def test_la_mesa_cambia_a_ocupada_despues_de_crear_el_pedido(self):
        self.client.login(username='mesero1', password='test12345')
        self.client.post(reverse('crear_pedido'), self._datos_crear())
        self.mesa.refresh_from_db()
        self.assertEqual(self.mesa.estado, Mesa.Estado.OCUPADA)

    def test_no_se_puede_crear_un_pedido_sin_detalles(self):
        self.client.login(username='mesero1', password='test12345')
        datos = {
            'mesa': self.mesa.pk,
            'observacion': '',
            'detalles-TOTAL_FORMS': '1',
            'detalles-INITIAL_FORMS': '0',
            'detalles-MIN_NUM_FORMS': '1',
            'detalles-MAX_NUM_FORMS': '1000',
            'detalles-0-producto': '',
            'detalles-0-cantidad': '',
            'detalles-0-observacion': '',
        }
        response = self.client.post(reverse('crear_pedido'), datos)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Pedido.objects.count(), 0)

    def test_no_se_puede_repetir_un_producto_dentro_del_mismo_pedido(self):
        self.client.login(username='mesero1', password='test12345')
        datos = {
            'mesa': self.mesa.pk,
            'observacion': '',
            'detalles-TOTAL_FORMS': '2',
            'detalles-INITIAL_FORMS': '0',
            'detalles-MIN_NUM_FORMS': '1',
            'detalles-MAX_NUM_FORMS': '1000',
            'detalles-0-producto': self.producto.pk,
            'detalles-0-cantidad': '1',
            'detalles-0-observacion': '',
            'detalles-1-producto': self.producto.pk,
            'detalles-1-cantidad': '1',
            'detalles-1-observacion': '',
        }
        response = self.client.post(reverse('crear_pedido'), datos)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Pedido.objects.count(), 0)

    def test_el_detalle_muestra_el_total_correcto(self):
        self.client.login(username='mesero1', password='test12345')
        self.client.post(reverse('crear_pedido'), self._datos_crear(cantidad='2'))
        pedido = Pedido.objects.get(mesa=self.mesa)
        self.assertEqual(pedido.total, Decimal('25.00'))
        response = self.client.get(reverse('detalle_pedido', args=[pedido.pk]))
        self.assertContains(response, 'S/ 25.00')

    def test_la_ruta_para_cambiar_estado_no_acepta_get(self):
        self.client.login(username='mesero1', password='test12345')
        pedido = Pedido.objects.create(mesa=self.mesa, mesero=self.user)
        response = self.client.get(reverse('cambiar_estado_pedido', args=[pedido.pk]))
        self.assertEqual(response.status_code, 405)

    def test_un_pedido_entregado_no_puede_cambiar_manual_a_pagado(self):
        self.client.login(username='mesero1', password='test12345')
        pedido = Pedido.objects.create(
            mesa=self.mesa,
            mesero=self.user,
            estado=Pedido.Estado.ENTREGADO,
        )
        self.mesa.refresh_from_db()
        self.assertEqual(self.mesa.estado, Mesa.Estado.OCUPADA)
        response = self.client.post(
            reverse('cambiar_estado_pedido', args=[pedido.pk]),
            {'estado': Pedido.Estado.PAGADO},
        )
        self.assertRedirects(response, reverse('detalle_pedido', args=[pedido.pk]))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.ENTREGADO)
        self.mesa.refresh_from_db()
        self.assertEqual(self.mesa.estado, Mesa.Estado.OCUPADA)

    def test_una_transicion_de_estado_no_permitida_es_rechazada(self):
        self.client.login(username='mesero1', password='test12345')
        pedido = Pedido.objects.create(mesa=self.mesa, mesero=self.user)
        response = self.client.post(
            reverse('cambiar_estado_pedido', args=[pedido.pk]),
            {'estado': Pedido.Estado.PAGADO},
        )
        self.assertRedirects(response, reverse('detalle_pedido', args=[pedido.pk]))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.ABIERTO)
