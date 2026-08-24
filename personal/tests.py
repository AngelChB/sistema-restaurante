from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from mesas.models import Mesa
from pedidos.models import Pedido

from .models import PerfilEmpleado

User = get_user_model()


class PersonalViewsTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='admin1', password='Clave12345', is_staff=True
        )
        PerfilEmpleado.objects.create(
            usuario=self.staff, rol=PerfilEmpleado.Rol.ADMINISTRADOR
        )
        self.normal = User.objects.create_user(
            username='mesero1', password='Clave12345'
        )
        self.empleado = User.objects.create_user(
            username='juan',
            password='Clave12345',
            first_name='Juan',
            last_name='Pérez',
            email='juan@restaurante.com',
        )
        PerfilEmpleado.objects.create(
            usuario=self.empleado, rol=PerfilEmpleado.Rol.MESERO
        )

    def _datos_crear(self, username='nuevo', email='nuevo@restaurante.com'):
        return {
            'username': username,
            'first_name': 'Ana',
            'last_name': 'López',
            'email': email,
            'password1': 'ClaveSegura123',
            'password2': 'ClaveSegura123',
            'rol': PerfilEmpleado.Rol.MESERO,
            'telefono': '999111222',
            'is_active': True,
        }

    def test_visitante_no_autenticado_es_redirigido_al_login(self):
        response = self.client.get(reverse('lista_empleados'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('lista_empleados')}",
        )

    def test_usuario_normal_recibe_403(self):
        self.client.login(username='mesero1', password='Clave12345')
        response = self.client.get(reverse('lista_empleados'))
        self.assertEqual(response.status_code, 403)

    def test_usuario_staff_puede_abrir_la_lista(self):
        self.client.login(username='admin1', password='Clave12345')
        response = self.client.get(reverse('lista_empleados'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sin perfil')

    def test_usuario_staff_puede_crear_un_empleado(self):
        self.client.login(username='admin1', password='Clave12345')
        response = self.client.post(
            reverse('crear_empleado'), self._datos_crear()
        )
        self.assertRedirects(response, reverse('lista_empleados'))
        self.assertTrue(User.objects.filter(username='nuevo').exists())

    def test_al_crear_empleado_tambien_se_crea_perfil_empleado(self):
        self.client.login(username='admin1', password='Clave12345')
        self.client.post(reverse('crear_empleado'), self._datos_crear())
        usuario = User.objects.get(username='nuevo')
        self.assertTrue(
            PerfilEmpleado.objects.filter(
                usuario=usuario, rol=PerfilEmpleado.Rol.MESERO
            ).exists()
        )
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)

    def test_la_contrasena_se_guarda_cifrada(self):
        self.client.login(username='admin1', password='Clave12345')
        self.client.post(reverse('crear_empleado'), self._datos_crear())
        usuario = User.objects.get(username='nuevo')
        self.assertNotEqual(usuario.password, 'ClaveSegura123')
        self.assertTrue(usuario.check_password('ClaveSegura123'))

    def test_no_se_permite_username_duplicado_ignorando_mayusculas(self):
        self.client.login(username='admin1', password='Clave12345')
        cantidad = User.objects.count()
        response = self.client.post(
            reverse('crear_empleado'), self._datos_crear(username='JUAN')
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), cantidad)

    def test_no_se_permite_correo_duplicado_ignorando_mayusculas(self):
        self.client.login(username='admin1', password='Clave12345')
        cantidad = User.objects.count()
        response = self.client.post(
            reverse('crear_empleado'),
            self._datos_crear(email='JUAN@RESTAURANTE.COM'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), cantidad)

    def test_se_puede_editar_el_rol_de_un_empleado(self):
        self.client.login(username='admin1', password='Clave12345')
        response = self.client.post(
            reverse('editar_empleado', args=[self.empleado.pk]),
            {
                'first_name': 'Juan',
                'last_name': 'Pérez',
                'email': 'juan@restaurante.com',
                'is_active': True,
                'is_staff': False,
                'rol': PerfilEmpleado.Rol.CAJERO,
                'telefono': '999000111',
            },
        )
        self.assertRedirects(response, reverse('lista_empleados'))
        perfil = self.empleado.perfil_empleado
        perfil.refresh_from_db()
        self.assertEqual(perfil.rol, PerfilEmpleado.Rol.CAJERO)
        self.assertEqual(perfil.telefono, '999000111')

    def test_un_usuario_no_puede_desactivarse_a_si_mismo(self):
        self.client.login(username='admin1', password='Clave12345')
        response = self.client.post(
            reverse('editar_empleado', args=[self.staff.pk]),
            {
                'first_name': '',
                'last_name': '',
                'email': '',
                'is_active': False,
                'is_staff': True,
                'rol': PerfilEmpleado.Rol.ADMINISTRADOR,
                'telefono': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_active)

    def test_un_usuario_no_puede_quitarse_sus_permisos_staff(self):
        self.client.login(username='admin1', password='Clave12345')
        response = self.client.post(
            reverse('editar_empleado', args=[self.staff.pk]),
            {
                'first_name': '',
                'last_name': '',
                'email': '',
                'is_active': True,
                'is_staff': False,
                'rol': PerfilEmpleado.Rol.ADMINISTRADOR,
                'telefono': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_staff)

    def test_la_busqueda_por_username_funciona(self):
        self.client.login(username='admin1', password='Clave12345')
        response = self.client.get(
            reverse('lista_empleados'), {'buscar': 'juan'}
        )
        self.assertContains(response, 'juan')
        self.assertNotContains(response, 'mesero1')

    def test_el_filtro_por_rol_funciona(self):
        self.client.login(username='admin1', password='Clave12345')
        cajero = User.objects.create_user(
            username='carlos', password='Clave12345'
        )
        PerfilEmpleado.objects.create(
            usuario=cajero, rol=PerfilEmpleado.Rol.CAJERO
        )
        response = self.client.get(
            reverse('lista_empleados'), {'rol': PerfilEmpleado.Rol.CAJERO}
        )
        self.assertContains(response, 'carlos')
        self.assertNotContains(response, 'juan')


class CambiarPasswordTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin2', password='ClaveAdmin123', is_staff=True
        )
        PerfilEmpleado.objects.create(
            usuario=self.admin, rol=PerfilEmpleado.Rol.ADMINISTRADOR
        )
        self.mesero = User.objects.create_user(
            username='carlos',
            password='ClaveVieja123',
            first_name='Carlos',
            last_name='Ramírez',
        )
        PerfilEmpleado.objects.create(
            usuario=self.mesero, rol=PerfilEmpleado.Rol.MESERO
        )
        self.url = reverse(
            'cambiar_password_empleado', args=[self.mesero.pk]
        )

    def _login_admin(self):
        self.client.login(username='admin2', password='ClaveAdmin123')

    def test_administrador_puede_abrir_la_pantalla(self):
        self._login_admin()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cambiar contraseña')
        self.assertContains(response, 'Carlos Ramírez')
        self.assertNotContains(response, 'ClaveVieja123')

    def test_administrador_cambia_la_contrasena_correctamente(self):
        self._login_admin()
        response = self.client.post(
            self.url,
            {'new_password1': 'NuevaClave987', 'new_password2': 'NuevaClave987'},
        )
        self.assertRedirects(response, reverse('lista_empleados'))
        self.mesero.refresh_from_db()
        self.assertTrue(self.mesero.check_password('NuevaClave987'))

    def test_la_contrasena_antigua_deja_de_funcionar(self):
        self._login_admin()
        self.client.post(
            self.url,
            {'new_password1': 'NuevaClave987', 'new_password2': 'NuevaClave987'},
        )
        self.mesero.refresh_from_db()
        self.assertFalse(self.mesero.check_password('ClaveVieja123'))
        self.assertTrue(self.mesero.check_password('NuevaClave987'))

    def test_contrasenas_diferentes_generan_error(self):
        self._login_admin()
        response = self.client.post(
            self.url,
            {'new_password1': 'NuevaClave987', 'new_password2': 'OtraClave987'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no coinciden')
        self.mesero.refresh_from_db()
        self.assertTrue(self.mesero.check_password('ClaveVieja123'))

    def test_contrasena_que_no_cumple_validaciones_genera_error(self):
        self._login_admin()
        response = self.client.post(
            self.url,
            {'new_password1': '12345678', 'new_password2': '12345678'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertContains(response, 'error-list')
        self.mesero.refresh_from_db()
        self.assertTrue(self.mesero.check_password('ClaveVieja123'))

    def test_contrasena_vacia_genera_error(self):
        self._login_admin()
        response = self.client.post(
            self.url,
            {'new_password1': '', 'new_password2': ''},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)

    def test_usuario_sin_permiso_recibe_403(self):
        self.client.login(username='carlos', password='ClaveVieja123')
        response = self.client.get(
            reverse('cambiar_password_empleado', args=[self.admin.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_visitante_no_autenticado_es_redirigido_al_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('login')}?next={self.url}")

    def test_no_se_expone_la_contrasena_en_las_respuestas_html(self):
        self._login_admin()
        response = self.client.get(self.url)
        self.assertNotContains(response, 'ClaveVieja123')
        self.assertNotContains(response, 'pbkdf2')
        post = self.client.post(
            self.url,
            {'new_password1': 'NuevaClave987', 'new_password2': 'NuevaClave987'},
        )
        self.assertEqual(post.status_code, 302)
        self.assertNotContains(post, 'NuevaClave987', status_code=302)

    def test_lista_de_empleados_sigue_funcionando_y_muestra_la_accion(self):
        self._login_admin()
        response = self.client.get(reverse('lista_empleados'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('cambiar_password_empleado', args=[self.mesero.pk]))


class GestionTrabajadorTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin3', password='ClaveAdmin123', is_staff=True
        )
        PerfilEmpleado.objects.create(
            usuario=self.admin, rol=PerfilEmpleado.Rol.ADMINISTRADOR
        )
        self.mesero = User.objects.create_user(
            username='carlos123',
            password='ClaveVieja123',
            first_name='Carlos',
            last_name='Ramírez',
        )
        PerfilEmpleado.objects.create(
            usuario=self.mesero, rol=PerfilEmpleado.Rol.MESERO
        )
        self.mesa = Mesa.objects.create(numero=1, capacidad=4)
        self.pedido = Pedido.objects.create(
            mesa=self.mesa,
            mesero=self.mesero,
            estado=Pedido.Estado.ABIERTO,
        )
        self.url_usuario = reverse(
            'cambiar_usuario_empleado', args=[self.mesero.pk]
        )
        self.url_estado = reverse(
            'alternar_estado_empleado', args=[self.mesero.pk]
        )

    def _login_admin(self):
        self.client.login(username='admin3', password='ClaveAdmin123')

    def test_administrador_puede_abrir_cambiar_usuario(self):
        self._login_admin()
        response = self.client.get(self.url_usuario)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Carlos Ramírez')
        self.assertContains(response, 'carlos123')

    def test_el_username_se_actualiza_correctamente(self):
        self._login_admin()
        response = self.client.post(
            self.url_usuario, {'username': 'nuevo_carlos'}
        )
        self.assertRedirects(response, reverse('lista_empleados'))
        self.mesero.refresh_from_db()
        self.assertEqual(self.mesero.username, 'nuevo_carlos')

    def test_no_se_permite_username_duplicado(self):
        otro = User.objects.create_user(
            username='juan2026', password='ClaveVieja123'
        )
        PerfilEmpleado.objects.create(
            usuario=otro, rol=PerfilEmpleado.Rol.MESERO
        )
        self._login_admin()
        response = self.client.post(
            self.url_usuario, {'username': 'juan2026'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.mesero.refresh_from_db()
        self.assertEqual(self.mesero.username, 'carlos123')

    def test_no_se_permite_username_vacio(self):
        self._login_admin()
        response = self.client.post(self.url_usuario, {'username': ''})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.mesero.refresh_from_db()
        self.assertEqual(self.mesero.username, 'carlos123')

    def test_el_trabajador_inicia_sesion_con_el_nuevo_username(self):
        self._login_admin()
        self.client.post(self.url_usuario, {'username': 'carlos_nuevo'})
        self.client.logout()
        self.assertTrue(
            self.client.login(
                username='carlos_nuevo', password='ClaveVieja123'
            )
        )

    def test_la_contrasena_sigue_funcionando_despues_de_cambiar_username(self):
        self._login_admin()
        self.client.post(self.url_usuario, {'username': 'carlos_nuevo'})
        self.mesero.refresh_from_db()
        self.assertTrue(self.mesero.check_password('ClaveVieja123'))

    def test_administrador_puede_desactivar_trabajador(self):
        self._login_admin()
        response = self.client.post(self.url_estado)
        self.assertRedirects(response, reverse('lista_empleados'))
        self.mesero.refresh_from_db()
        self.assertFalse(self.mesero.is_active)

    def test_trabajador_desactivado_no_puede_iniciar_sesion(self):
        self._login_admin()
        self.client.post(self.url_estado)
        self.client.logout()
        self.assertFalse(
            self.client.login(username='carlos123', password='ClaveVieja123')
        )

    def test_administrador_puede_reactivar_trabajador(self):
        self._login_admin()
        self.client.post(self.url_estado)
        self.mesero.refresh_from_db()
        self.assertFalse(self.mesero.is_active)
        self.client.post(self.url_estado)
        self.mesero.refresh_from_db()
        self.assertTrue(self.mesero.is_active)

    def test_trabajador_puede_iniciar_sesion_despues_de_activarse(self):
        self._login_admin()
        self.client.post(self.url_estado)
        self.client.post(self.url_estado)
        self.client.logout()
        self.assertTrue(
            self.client.login(username='carlos123', password='ClaveVieja123')
        )

    def test_los_registros_historicos_se_conservan(self):
        self._login_admin()
        self.client.post(self.url_estado)
        self.client.post(self.url_estado)
        self.mesero.refresh_from_db()
        pedido = Pedido.objects.get(pk=self.pedido.pk)
        self.assertEqual(pedido.mesero_id, self.mesero.pk)
        self.assertEqual(User.objects.filter(pk=self.mesero.pk).count(), 1)

    def test_administrador_no_puede_desactivarse_a_si_mismo(self):
        self._login_admin()
        url = reverse('alternar_estado_empleado', args=[self.admin.pk])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('lista_empleados'))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_usuario_sin_permiso_no_puede_cambiar_username(self):
        self.client.login(username='carlos123', password='ClaveVieja123')
        response = self.client.get(self.url_usuario)
        self.assertEqual(response.status_code, 403)

    def test_usuario_sin_permiso_no_puede_cambiar_contrasena(self):
        self.client.login(username='carlos123', password='ClaveVieja123')
        response = self.client.get(
            reverse('cambiar_password_empleado', args=[self.mesero.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_usuario_sin_permiso_no_puede_activar_desactivar(self):
        self.client.login(username='carlos123', password='ClaveVieja123')
        response = self.client.post(self.url_estado)
        self.assertEqual(response.status_code, 403)
        self.mesero.refresh_from_db()
        self.assertTrue(self.mesero.is_active)

    def test_urls_protegidas_devuelven_403(self):
        self.client.login(username='carlos123', password='ClaveVieja123')
        with self.subTest(url='cambiar_usuario'):
            self.assertEqual(self.client.get(self.url_usuario).status_code, 403)
        with self.subTest(url='cambiar_password'):
            self.assertEqual(
                self.client.get(
                    reverse('cambiar_password_empleado', args=[self.mesero.pk])
                ).status_code,
                403,
            )
        with self.subTest(url='alternar_estado'):
            self.assertEqual(self.client.post(self.url_estado).status_code, 403)
