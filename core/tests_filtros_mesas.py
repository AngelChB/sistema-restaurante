from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from catalogo.models import Categoria, Producto
from mesas.forms import MesaForm
from mesas.models import Mesa
from pedidos.models import Pedido


class FiltrosInvalidosTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='filtros', password='Clave123!'
        )
        self.client.force_login(self.user)

    def test_ids_invalidos_no_provocan_error(self):
        rutas = [
            ('lista_productos', 'categoria'),
            ('lista_compras', 'proveedor'),
            ('lista_ingredientes', 'unidad'),
            ('historial_movimientos', 'ingrediente'),
            ('lista_recetas', 'categoria'),
        ]
        for ruta, campo in rutas:
            for valor in ['abc', '-1', '0', '1.5', '9' * 80]:
                with self.subTest(ruta=ruta, valor=valor):
                    response = self.client.get(reverse(ruta), {campo: valor})
                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(list(get_messages(response.wsgi_request)))

    def test_fechas_invalidas_no_provocan_error(self):
        for ruta, campo in [
            ('lista_reservas', 'fecha'),
            ('historial_movimientos', 'fecha_desde'),
            ('historial_movimientos', 'fecha_hasta'),
        ]:
            for valor in ['ayer', '2026-02-30', '2026-13-01']:
                with self.subTest(ruta=ruta, valor=valor):
                    response = self.client.get(reverse(ruta), {campo: valor})
                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(list(get_messages(response.wsgi_request)))

    def test_filtro_valido_sigue_filtrando(self):
        a = Categoria.objects.create(nombre='A')
        b = Categoria.objects.create(nombre='B')
        Producto.objects.create(categoria=a, nombre='Uno', precio=10)
        Producto.objects.create(categoria=b, nombre='Dos', precio=10)
        response = self.client.get(reverse('lista_productos'), {'categoria': a.pk})
        self.assertContains(response, 'Uno')
        self.assertNotContains(response, 'Dos')

    def test_filtros_vacios_no_generan_error(self):
        response = self.client.get(reverse('lista_productos'), {'categoria': ''})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(list(get_messages(response.wsgi_request)))


class MesaConPedidoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='mesas', password='Clave123!'
        )
        self.client.force_login(self.user)
        self.mesa = Mesa.objects.create(numero=1, capacidad=4)
        self.pedido = Pedido.objects.create(mesa=self.mesa, mesero=self.user)
        self.mesa.refresh_from_db()

    def datos(self, **cambios):
        datos = {
            'numero': 1,
            'capacidad': 4,
            'estado': 'OCUPADA',
            'activo': True,
            'ubicacion': '',
        }
        datos.update(cambios)
        return datos

    def test_no_se_puede_liberar_reservar_o_retirar_mesa_con_pedido(self):
        for estado in ['LIBRE', 'RESERVADA', 'FUERA_SERVICIO']:
            with self.subTest(estado=estado):
                response = self.client.post(
                    reverse('editar_mesa', args=[self.mesa.pk]),
                    self.datos(estado=estado),
                )
                self.assertEqual(response.status_code, 200)
                self.mesa.refresh_from_db()
                self.assertEqual(self.mesa.estado, Mesa.Estado.OCUPADA)

    def test_no_se_puede_desactivar_mesa_con_pedido(self):
        response = self.client.post(
            reverse('editar_mesa', args=[self.mesa.pk]), self.datos(activo=False)
        )
        self.assertEqual(response.status_code, 200)
        self.mesa.refresh_from_db()
        self.assertTrue(self.mesa.activo)

    def test_permite_editar_ubicacion_sin_alterar_estado(self):
        response = self.client.post(
            reverse('editar_mesa', args=[self.mesa.pk]), self.datos(ubicacion='Terraza')
        )
        self.assertEqual(response.status_code, 302)
        self.mesa.refresh_from_db()
        self.assertEqual(self.mesa.ubicacion, 'Terraza')

    def test_permite_desactivar_despues_de_cancelar_pedido(self):
        self.pedido.estado = Pedido.Estado.CANCELADO
        self.pedido.save()
        form = MesaForm(
            data=self.datos(estado='FUERA_SERVICIO', activo=False), instance=self.mesa
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.mesa.refresh_from_db()
        self.assertFalse(self.mesa.activo)

    def test_admin_tambien_valida_mesa_con_pedido(self):
        response = self.client.post(
            reverse('admin:mesas_mesa_change', args=[self.mesa.pk]),
            self.datos(estado='LIBRE'),
        )
        self.assertEqual(response.status_code, 200)
        self.mesa.refresh_from_db()
        self.assertEqual(self.mesa.estado, Mesa.Estado.OCUPADA)
