from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalogo.models import Categoria, Producto
from mesas.models import Mesa
from pedidos.models import Pedido
from personal.models import PerfilEmpleado


class SalaViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.mesero1 = User.objects.create_user(
            username='mesero1', password='test12345'
        )
        PerfilEmpleado.objects.create(
            usuario=self.mesero1, rol=PerfilEmpleado.Rol.MESERO
        )
        self.mesero2 = User.objects.create_user(
            username='mesero2', password='test12345'
        )
        PerfilEmpleado.objects.create(
            usuario=self.mesero2, rol=PerfilEmpleado.Rol.MESERO
        )
        self.staff = User.objects.create_user(
            username='admin1', password='test12345', is_staff=True
        )
        PerfilEmpleado.objects.create(
            usuario=self.staff, rol=PerfilEmpleado.Rol.ADMINISTRADOR
        )
        self.categoria = Categoria.objects.create(nombre='Bebidas')
        self.producto = Producto.objects.create(
            categoria=self.categoria,
            nombre='Café',
            precio='12.50',
            disponible=True,
        )
        self.mesa1 = Mesa.objects.create(numero=1, capacidad=2)
        self.mesa2 = Mesa.objects.create(numero=2, capacidad=2)
        self.mesa3 = Mesa.objects.create(numero=3, capacidad=2)
        self.mesa4 = Mesa.objects.create(numero=4, capacidad=2)

    def _crear_pedido(self, mesero, mesa, estado):
        return Pedido.objects.create(
            mesa=mesa, mesero=mesero, estado=estado
        )

    def test_visitante_no_autenticado_es_redirigido_al_login(self):
        response = self.client.get(reverse('panel_sala'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('panel_sala')}",
        )

    def test_usuario_autenticado_puede_abrir_el_panel(self):
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('panel_sala'))
        self.assertEqual(response.status_code, 200)

    def test_el_panel_muestra_pedidos_con_estado_listo(self):
        pedido = self._crear_pedido(
            self.mesero1, self.mesa1, Pedido.Estado.LISTO
        )
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('panel_sala'))
        self.assertContains(response, f'Pedido {pedido.pk}')
        self.assertContains(response, 'Marcar como entregado')

    def test_el_panel_no_muestra_pedidos_abierto_en_preparacion_pagado_ni_cancelado(self):
        p1 = self._crear_pedido(self.mesero1, self.mesa1, Pedido.Estado.ABIERTO)
        p2 = self._crear_pedido(self.mesero1, self.mesa2, Pedido.Estado.EN_PREPARACION)
        p3 = self._crear_pedido(self.mesero1, self.mesa3, Pedido.Estado.PAGADO)
        p4 = self._crear_pedido(self.mesero1, self.mesa4, Pedido.Estado.CANCELADO)
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('panel_sala'))
        self.assertNotContains(response, f'Pedido {p1.pk}')
        self.assertNotContains(response, f'Pedido {p2.pk}')
        self.assertNotContains(response, f'Pedido {p3.pk}')
        self.assertNotContains(response, f'Pedido {p4.pk}')

    def test_un_usuario_normal_solamente_ve_sus_propios_pedidos(self):
        p1 = self._crear_pedido(self.mesero1, self.mesa1, Pedido.Estado.LISTO)
        p2 = self._crear_pedido(self.mesero2, self.mesa2, Pedido.Estado.LISTO)
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('panel_sala'))
        self.assertContains(response, f'Pedido {p1.pk}')
        self.assertNotContains(response, f'Pedido {p2.pk}')

    def test_un_usuario_staff_puede_ver_pedidos_de_todos_los_meseros(self):
        p1 = self._crear_pedido(self.mesero1, self.mesa1, Pedido.Estado.LISTO)
        p2 = self._crear_pedido(self.mesero2, self.mesa2, Pedido.Estado.LISTO)
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(reverse('panel_sala'))
        self.assertContains(response, f'Pedido {p1.pk}')
        self.assertContains(response, f'Pedido {p2.pk}')

    def test_la_ruta_de_entrega_no_acepta_solicitudes_get(self):
        pedido = self._crear_pedido(
            self.mesero1, self.mesa1, Pedido.Estado.LISTO
        )
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(
            reverse('marcar_pedido_entregado', args=[pedido.pk])
        )
        self.assertEqual(response.status_code, 405)

    def test_se_puede_cambiar_listo_a_entregado(self):
        pedido = self._crear_pedido(
            self.mesero1, self.mesa1, Pedido.Estado.LISTO
        )
        self.client.login(username='mesero1', password='test12345')
        response = self.client.post(
            reverse('marcar_pedido_entregado', args=[pedido.pk])
        )
        self.assertRedirects(response, reverse('panel_sala'))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.ENTREGADO)

    def test_no_se_puede_cambiar_abierto_directamente_a_entregado(self):
        pedido = self._crear_pedido(
            self.mesero1, self.mesa1, Pedido.Estado.ABIERTO
        )
        self.client.login(username='mesero1', password='test12345')
        response = self.client.post(
            reverse('marcar_pedido_entregado', args=[pedido.pk])
        )
        self.assertRedirects(response, reverse('panel_sala'))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.ABIERTO)

    def test_un_mesero_no_puede_entregar_el_pedido_de_otro_mesero(self):
        pedido = self._crear_pedido(
            self.mesero2, self.mesa1, Pedido.Estado.LISTO
        )
        self.client.login(username='mesero1', password='test12345')
        response = self.client.post(
            reverse('marcar_pedido_entregado', args=[pedido.pk])
        )
        self.assertEqual(response.status_code, 403)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.LISTO)

    def test_un_usuario_staff_si_puede_entregar_el_pedido_de_otro_mesero(self):
        pedido = self._crear_pedido(
            self.mesero2, self.mesa1, Pedido.Estado.LISTO
        )
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('marcar_pedido_entregado', args=[pedido.pk])
        )
        self.assertRedirects(response, reverse('panel_sala'))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.ENTREGADO)
