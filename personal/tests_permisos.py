from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from mesas.models import Mesa
from pedidos.models import Pedido

from .models import PerfilEmpleado

User = get_user_model()


def crear_usuario(username, rol):
    usuario = User.objects.create_user(username=username, password='test12345')
    PerfilEmpleado.objects.create(usuario=usuario, rol=rol)
    return usuario


MODULOS = [
    'lista_mesas',
    'lista_productos',
    'lista_categorias',
    'lista_pedidos',
    'crear_pedido',
    'panel_cocina',
    'panel_sala',
    'panel_caja',
    'lista_empleados',
    'panel_inventario',
    'lista_compras',
    'lista_reservas',
    'reporte_ventas',
]

MODULOS_SOLO_ADMIN = ['crear_mesa', 'crear_producto', 'crear_categoria']

CATALOGO = ['lista_productos', 'lista_categorias']


class PermisosPorRolTests(TestCase):
    def setUp(self):
        self.superusuario = User.objects.create_superuser(
            username='super',
            email='super@restaurante.com',
            password='test12345',
        )
        self.administrador = crear_usuario('admin1', PerfilEmpleado.Rol.ADMINISTRADOR)
        self.mesero = crear_usuario('mesero1', PerfilEmpleado.Rol.MESERO)
        self.cocinero = crear_usuario('cocinero1', PerfilEmpleado.Rol.COCINA)
        self.cajero = crear_usuario('cajero1', PerfilEmpleado.Rol.CAJERO)
        self.sin_perfil = User.objects.create_user(
            username='anonimo', password='test12345'
        )
        self.mesa = Mesa.objects.create(numero=1, capacidad=4)
        self.mesa2 = Mesa.objects.create(numero=2, capacidad=4)

    def _login(self, usuario):
        self.client.login(username=usuario.username, password='test12345')

    def _acceder_a(self, urls):
        for nombre in urls:
            with self.subTest(url=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)

    def _bloqueado_en(self, urls):
        for nombre in urls:
            with self.subTest(url=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 403)

    def test_superusuario_tiene_acceso_a_todos_los_modulos(self):
        self._login(self.superusuario)
        self._acceder_a(MODULOS + MODULOS_SOLO_ADMIN)

    def test_administrador_tiene_acceso_a_todos_los_modulos(self):
        self._login(self.administrador)
        self._acceder_a(MODULOS + MODULOS_SOLO_ADMIN)

    def test_mesero_tiene_acceso_a_mesas_catalogo_pedidos_y_sala(self):
        self._login(self.mesero)
        self._acceder_a(
            ['lista_mesas'] + CATALOGO + ['lista_pedidos', 'crear_pedido', 'panel_sala']
        )

    def test_mesero_no_tiene_acceso_a_cocina_caja_personal_ni_a_crear(self):
        self._login(self.mesero)
        self._bloqueado_en(
            ['panel_cocina', 'panel_caja', 'lista_empleados'] + MODULOS_SOLO_ADMIN
        )

    def test_cocina_tiene_acceso_al_panel_de_cocina_y_al_catalogo(self):
        self._login(self.cocinero)
        self._acceder_a(['panel_cocina'] + CATALOGO)

    def test_cocina_no_tiene_acceso_a_mesas_pedidos_sala_caja_ni_personal(self):
        self._login(self.cocinero)
        self._bloqueado_en(
            [
                'lista_mesas',
                'lista_pedidos',
                'crear_pedido',
                'panel_sala',
                'panel_caja',
                'lista_empleados',
            ]
        )

    def test_cajero_tiene_acceso_al_panel_de_caja_y_al_catalogo(self):
        self._login(self.cajero)
        self._acceder_a(['panel_caja'] + CATALOGO)

    def test_cajero_no_tiene_acceso_a_cocina_pedidos_sala_ni_personal(self):
        self._login(self.cajero)
        self._bloqueado_en(
            [
                'lista_mesas',
                'lista_pedidos',
                'crear_pedido',
                'panel_cocina',
                'panel_sala',
                'lista_empleados',
            ]
        )

    def test_mesero_tiene_acceso_a_reservas(self):
        self._login(self.mesero)
        self._acceder_a(['lista_reservas'])

    def test_mesero_no_tiene_acceso_a_inventario_ni_compras(self):
        self._login(self.mesero)
        self._bloqueado_en(['panel_inventario', 'lista_compras', 'reporte_ventas'])

    def test_cocina_tiene_acceso_a_inventario_y_compras(self):
        self._login(self.cocinero)
        self._acceder_a(['panel_inventario', 'lista_compras'])

    def test_cocina_no_tiene_acceso_a_reservas(self):
        self._login(self.cocinero)
        self._bloqueado_en(['lista_reservas'])

    def test_cajero_tiene_acceso_a_caja_y_reportes(self):
        self._login(self.cajero)
        self._acceder_a(['panel_caja', 'reporte_ventas'])

    def test_acceso_denegado_muestra_pagina_amigable(self):
        self._login(self.mesero)
        response = self.client.get(reverse('panel_inventario'))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Acceso no autorizado', status_code=403)
        self.assertContains(response, reverse('dashboard'), status_code=403)

    def test_el_context_processor_expone_el_nombre_del_rol(self):
        self._login(self.cajero)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['rol_usuario'], PerfilEmpleado.Rol.CAJERO)
        self.assertEqual(response.context['rol_usuario_nombre'], 'Cajero')

    def test_usuario_sin_perfil_solo_accede_al_dashboard(self):
        self._login(self.sin_perfil)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)
        self._bloqueado_en(MODULOS)

    def test_mesero_solo_ve_sus_propios_pedidos_en_la_lista(self):
        otro = crear_usuario('mesero2', PerfilEmpleado.Rol.MESERO)
        p1 = Pedido.objects.create(
            mesa=self.mesa, mesero=self.mesero, estado=Pedido.Estado.ABIERTO
        )
        p2 = Pedido.objects.create(
            mesa=self.mesa2, mesero=otro, estado=Pedido.Estado.ABIERTO
        )
        self._login(self.mesero)
        response = self.client.get(reverse('lista_pedidos'))
        self.assertContains(response, f'Pedido {p1.pk}')
        self.assertNotContains(response, f'Pedido {p2.pk}')

    def test_administrador_ve_los_pedidos_de_todos_los_meseros(self):
        otro = crear_usuario('mesero2', PerfilEmpleado.Rol.MESERO)
        p1 = Pedido.objects.create(
            mesa=self.mesa, mesero=self.mesero, estado=Pedido.Estado.ABIERTO
        )
        p2 = Pedido.objects.create(
            mesa=self.mesa2, mesero=otro, estado=Pedido.Estado.ABIERTO
        )
        self._login(self.administrador)
        response = self.client.get(reverse('lista_pedidos'))
        self.assertContains(response, f'Pedido {p1.pk}')
        self.assertContains(response, f'Pedido {p2.pk}')

    def test_mesero_no_puede_ver_detalle_de_pedido_ajeno(self):
        otro = crear_usuario('mesero2', PerfilEmpleado.Rol.MESERO)
        pedido = Pedido.objects.create(
            mesa=self.mesa, mesero=otro, estado=Pedido.Estado.ABIERTO
        )
        self._login(self.mesero)
        response = self.client.get(reverse('detalle_pedido', args=[pedido.pk]))
        self.assertEqual(response.status_code, 403)

    def test_mesero_no_puede_cambiar_estado_de_pedido_ajeno(self):
        otro = crear_usuario('mesero2', PerfilEmpleado.Rol.MESERO)
        pedido = Pedido.objects.create(
            mesa=self.mesa, mesero=otro, estado=Pedido.Estado.ABIERTO
        )
        self._login(self.mesero)
        response = self.client.post(
            reverse('cambiar_estado_pedido', args=[pedido.pk]),
            {'estado': Pedido.Estado.EN_PREPARACION},
        )
        self.assertEqual(response.status_code, 403)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.ABIERTO)

    def test_el_nav_oculta_enlaces_segun_el_rol(self):
        self._login(self.cocinero)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, reverse('panel_cocina'))
        self.assertContains(response, reverse('lista_productos'))
        self.assertNotContains(response, reverse('lista_mesas'))
        self.assertNotContains(response, reverse('panel_caja'))
        self.assertNotContains(response, reverse('lista_empleados'))

    def test_el_nav_administrador_muestra_todos_los_enlaces(self):
        self._login(self.administrador)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, reverse('lista_mesas'))
        self.assertContains(response, reverse('lista_pedidos'))
        self.assertContains(response, reverse('panel_cocina'))
        self.assertContains(response, reverse('panel_sala'))
        self.assertContains(response, reverse('panel_caja'))
        self.assertContains(response, reverse('lista_empleados'))

    def test_el_context_processor_expone_el_rol_del_usuario(self):
        self._login(self.cajero)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['rol_usuario'], PerfilEmpleado.Rol.CAJERO)
        self.assertFalse(response.context['es_administrador'])
        self.assertTrue(response.context['puede_ver_caja'])
        self.assertFalse(response.context['puede_ver_cocina'])
