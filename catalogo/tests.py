from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from personal.models import PerfilEmpleado

from .models import Categoria, Producto


class CatalogoViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='mesero1', password='test12345'
        )
        PerfilEmpleado.objects.create(
            usuario=self.user, rol=PerfilEmpleado.Rol.MESERO
        )
        self.staff = User.objects.create_user(
            username='admin1', password='test12345', is_staff=True
        )
        PerfilEmpleado.objects.create(
            usuario=self.staff, rol=PerfilEmpleado.Rol.ADMINISTRADOR
        )
        self.categoria = Categoria.objects.create(
            nombre='Bebidas', descripcion='', activo=True
        )
        self.producto = Producto.objects.create(
            categoria=self.categoria,
            nombre='Café',
            descripcion='',
            precio='12.50',
            disponible=True,
        )

    def test_visitante_no_autenticado_es_redirigido_al_login(self):
        response = self.client.get(reverse('lista_productos'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('lista_productos')}",
        )

    def test_usuario_autenticado_puede_ver_la_lista_de_productos(self):
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('lista_productos'))
        self.assertEqual(response.status_code, 200)

    def test_busqueda_por_nombre_funciona(self):
        Producto.objects.create(
            categoria=self.categoria, nombre='Pan', precio='3.00', disponible=True
        )
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(
            reverse('lista_productos'), {'buscar': 'caf'}
        )
        self.assertContains(response, '>Café<')
        self.assertNotContains(response, '>Pan<')

    def test_filtro_por_categoria_funciona(self):
        otra = Categoria.objects.create(nombre='Postres', activo=True)
        Producto.objects.create(
            categoria=otra, nombre='Torta', precio='20.00', disponible=True
        )
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(
            reverse('lista_productos'), {'categoria': self.categoria.pk}
        )
        self.assertContains(response, 'Café')
        self.assertNotContains(response, 'Torta')

    def test_usuario_staff_puede_crear_una_categoria(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('crear_categoria'),
            {'nombre': 'Postres', 'descripcion': '', 'activo': True},
        )
        self.assertRedirects(response, reverse('lista_categorias'))
        self.assertTrue(Categoria.objects.filter(nombre='Postres').exists())

    def test_usuario_staff_puede_crear_un_producto(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('crear_producto'),
            {
                'categoria': self.categoria.pk,
                'nombre': 'Jugo',
                'descripcion': '',
                'precio': '8.50',
                'disponible': True,
            },
        )
        self.assertRedirects(response, reverse('lista_productos'))
        self.assertTrue(Producto.objects.filter(nombre='Jugo').exists())

    def test_usuario_staff_puede_editar_un_producto(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('editar_producto', args=[self.producto.pk]),
            {
                'categoria': self.categoria.pk,
                'nombre': 'Café',
                'descripcion': '',
                'precio': '15.00',
                'disponible': True,
            },
        )
        self.assertRedirects(response, reverse('lista_productos'))
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.precio, Decimal('15.00'))

    def test_usuario_no_staff_recibe_403_al_crear_un_producto(self):
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('crear_producto'))
        self.assertEqual(response.status_code, 403)

    def test_no_se_permite_categoria_duplicada_ignorando_mayusculas(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('crear_categoria'),
            {'nombre': 'bebidas', 'descripcion': '', 'activo': True},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Categoria.objects.filter(nombre__iexact='bebidas').count(), 1)

    def test_no_se_permite_producto_con_precio_cero_o_negativo(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('crear_producto'),
            {
                'categoria': self.categoria.pk,
                'nombre': 'Agua',
                'descripcion': '',
                'precio': '0',
                'disponible': True,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Producto.objects.filter(nombre='Agua').exists())
