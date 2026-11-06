from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import EmpleadoCrearForm, EmpleadoEditarForm
from .models import PerfilEmpleado


class OpcionesEmpleadoTests(TestCase):
    def datos(self):
        return {
            'username': 'nuevo',
            'password1': 'ClaveCompleja123!',
            'password2': 'ClaveCompleja123!',
            'rol': 'MESERO',
        }

    def test_empleado_inactivo_no_puede_iniciar_sesion(self):
        form = EmpleadoCrearForm(data=self.datos())
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertFalse(user.is_active)
        self.assertFalse(
            self.client.login(username='nuevo', password='ClaveCompleja123!')
        )
        self.assertTrue(PerfilEmpleado.objects.filter(usuario=user).exists())

    def test_empleado_activo_puede_iniciar_sesion(self):
        datos = self.datos()
        datos['is_active'] = 'on'
        form = EmpleadoCrearForm(data=datos)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertTrue(
            self.client.login(username='nuevo', password='ClaveCompleja123!')
        )

    def test_staff_se_puede_conceder_y_retirar(self):
        user = get_user_model().objects.create_user(username='editar')
        datos = {'rol': 'MESERO', 'is_active': 'on', 'is_staff': 'on'}
        form = EmpleadoEditarForm(data=datos, instance=user)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        datos.pop('is_staff')
        form = EmpleadoEditarForm(data=datos, instance=user)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        user.refresh_from_db()
        self.assertFalse(user.is_staff)

    def test_no_puede_retirarse_staff_desde_la_vista(self):
        user = get_user_model().objects.create_user(username='admin', is_staff=True)
        PerfilEmpleado.objects.create(usuario=user, rol='ADMINISTRADOR')
        self.client.force_login(user)
        response = self.client.post(
            reverse('editar_empleado', args=[user.pk]),
            {'rol': 'ADMINISTRADOR', 'is_active': 'on'},
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_staff)

    def test_commit_false_no_guarda_usuario_ni_perfil(self):
        form = EmpleadoCrearForm(data=self.datos())
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save(commit=False)
        self.assertIsNone(user.pk)
        self.assertFalse(PerfilEmpleado.objects.exists())
