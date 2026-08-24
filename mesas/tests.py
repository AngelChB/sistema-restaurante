from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from personal.models import PerfilEmpleado

from .models import Mesa


class MesaViewsTests(TestCase):
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

    def test_visitante_no_autenticado_es_redirigido_al_login(self):
        response = self.client.get(reverse('lista_mesas'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('lista_mesas')}",
        )

    def test_usuario_autenticado_puede_ver_la_lista_de_mesas(self):
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('lista_mesas'))
        self.assertEqual(response.status_code, 200)

    def test_usuario_staff_puede_crear_una_mesa(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('crear_mesa'),
            {
                'numero': 1,
                'capacidad': 4,
                'estado': Mesa.Estado.LIBRE,
                'ubicacion': '',
                'activo': True,
            },
        )
        self.assertRedirects(response, reverse('lista_mesas'))
        self.assertTrue(Mesa.objects.filter(numero=1).exists())

    def test_usuario_staff_puede_editar_una_mesa(self):
        mesa = Mesa.objects.create(numero=1, capacidad=4)
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('editar_mesa', args=[mesa.pk]),
            {
                'numero': 1,
                'capacidad': 6,
                'estado': Mesa.Estado.OCUPADA,
                'ubicacion': 'Terraza',
                'activo': True,
            },
        )
        self.assertRedirects(response, reverse('lista_mesas'))
        mesa.refresh_from_db()
        self.assertEqual(mesa.capacidad, 6)
        self.assertEqual(mesa.estado, Mesa.Estado.OCUPADA)

    def test_usuario_no_staff_recibe_403_al_intentar_crear(self):
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('crear_mesa'))
        self.assertEqual(response.status_code, 403)

    def test_no_se_permite_crear_dos_mesas_con_el_mismo_numero(self):
        Mesa.objects.create(numero=1, capacidad=4)
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('crear_mesa'),
            {
                'numero': 1,
                'capacidad': 6,
                'estado': Mesa.Estado.LIBRE,
                'ubicacion': '',
                'activo': True,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Mesa.objects.filter(numero=1).count(), 1)
