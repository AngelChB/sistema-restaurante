from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from mesas.models import Mesa
from personal.models import PerfilEmpleado

from .forms import ClienteForm, ReservaForm
from .models import Cliente, Reserva


def _fecha_futura(dias=1, horas=0):
    return timezone.now() + timedelta(days=dias, hours=horas)


def _crear_cliente(**kwargs):
    datos = {'nombres': 'Juan', 'apellidos': 'Pérez', 'telefono': '987654321'}
    datos.update(kwargs)
    return Cliente.objects.create(**datos)


def _crear_mesa(numero=1, capacidad=4, **kwargs):
    return Mesa.objects.create(
        numero=numero, capacidad=capacidad, **kwargs
    )


class ClienteModelTests(TestCase):
    def test_el_documento_es_unico_ignorando_mayusculas(self):
        _crear_cliente(documento='71234567')
        with self.assertRaises(ValidationError):
            _crear_cliente(nombres='María', documento='71234567')
        with self.assertRaises(ValidationError):
            _crear_cliente(nombres='Ana', documento='71234567')

    def test_un_cliente_puede_no_tener_documento(self):
        cliente = _crear_cliente(nombres='Sin documento')
        self.assertIsNone(cliente.documento)

    def test_editar_otro_cliente_no_rompe_la_uniqueness_del_documento(self):
        cliente1 = _crear_cliente(documento='71234567')
        cliente2 = _crear_cliente(nombres='Ana', documento='87654321')
        cliente2.documento = '71234567'
        with self.assertRaises(ValidationError):
            cliente2.validate()

    def test_el_telefono_no_puede_estar_vacio(self):
        form = ClienteForm(
            data={
                'nombres': 'Pedro',
                'apellidos': '',
                'documento': '',
                'telefono': '',
                'email': '',
                'observacion': '',
                'activo': True,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn('telefono', form.errors)


class ReservaModelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.usuario = User.objects.create_user(
            username='mesero1', password='test12345'
        )
        self.cliente = _crear_cliente()
        self.mesa = _crear_mesa()

    def _crear_reserva(self, **kwargs):
        datos = {
            'cliente': self.cliente,
            'mesa': self.mesa,
            'fecha_hora': _fecha_futura(),
            'cantidad_personas': 2,
            'usuario': self.usuario,
        }
        datos.update(kwargs)
        return Reserva.objects.create(**datos)

    def test_la_cantidad_de_personas_debe_ser_mayor_que_cero(self):
        with self.assertRaises(ValidationError):
            self._crear_reserva(cantidad_personas=0)

    def test_la_cantidad_no_puede_superar_la_capacidad_de_la_mesa(self):
        with self.assertRaises(ValidationError):
            self._crear_reserva(cantidad_personas=5)

    def test_no_se_puede_reservar_una_mesa_inactiva(self):
        self.mesa.activo = False
        self.mesa.save()
        with self.assertRaises(ValidationError):
            self._crear_reserva()

    def test_no_se_puede_reservar_una_mesa_fuera_de_servicio(self):
        self.mesa.estado = Mesa.Estado.FUERA_SERVICIO
        self.mesa.save()
        with self.assertRaises(ValidationError):
            self._crear_reserva()

    def test_la_fecha_de_la_reserva_debe_ser_futura(self):
        with self.assertRaises(ValidationError):
            self._crear_reserva(
                fecha_hora=timezone.now() - timedelta(minutes=1)
            )

    def test_la_duracion_debe_ser_mayor_que_cero(self):
        with self.assertRaises(ValidationError):
            self._crear_reserva(duracion_minutos=0)

    def test_la_duracion_define_el_fin_de_la_reserva(self):
        reserva = self._crear_reserva(duracion_minutos=90)
        self.assertEqual(
            reserva.fin, reserva.fecha_hora + timedelta(minutes=90)
        )

    def test_no_se_pueden_solapar_reservas_activas_en_la_misma_mesa(self):
        self._crear_reserva(fecha_hora=_fecha_futura(), duracion_minutos=120)
        with self.assertRaises(ValidationError):
            self._crear_reserva(
                fecha_hora=_fecha_futura(horas=1),
                cantidad_personas=3,
            )

    def test_si_la_reserva_termina_cuando_empieza_otra_no_hay_solapamiento(self):
        self._crear_reserva(fecha_hora=_fecha_futura(), duracion_minutos=120)
        reserva2 = self._crear_reserva(
            fecha_hora=_fecha_futura(horas=2),
            cantidad_personas=3,
        )
        self.assertEqual(reserva2.estado, Reserva.Estado.PENDIENTE)

    def test_se_pueden_solapar_reservas_en_mesas_diferentes(self):
        mesa2 = _crear_mesa(numero=2)
        self._crear_reserva(fecha_hora=_fecha_futura(), duracion_minutos=120)
        reserva2 = self._crear_reserva(
            mesa=mesa2,
            fecha_hora=_fecha_futura(horas=1),
        )
        self.assertEqual(reserva2.estado, Reserva.Estado.PENDIENTE)

    def test_una_reserva_cancelada_no_bloquea_el_horario(self):
        reserva1 = self._crear_reserva(
            fecha_hora=_fecha_futura(), duracion_minutos=120
        )
        reserva1.estado = Reserva.Estado.CANCELADA
        reserva1.save()
        reserva2 = self._crear_reserva(
            fecha_hora=_fecha_futura(horas=1),
            cantidad_personas=3,
        )
        self.assertEqual(reserva2.estado, Reserva.Estado.PENDIENTE)

    def test_una_reserva_futura_no_cambia_el_estado_de_la_mesa(self):
        self._crear_reserva()
        self.mesa.refresh_from_db()
        self.assertEqual(self.mesa.estado, Mesa.Estado.LIBRE)

    def test_no_se_puede_confirmar_una_reserva_de_una_mesa_inactiva(self):
        reserva = self._crear_reserva()
        self.mesa.activo = False
        self.mesa.save()
        reserva.estado = Reserva.Estado.CONFIRMADA
        with self.assertRaises(ValidationError):
            reserva.save()
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE)


class ReservasViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.administrador = User.objects.create_user(
            username='admin1', password='test12345'
        )
        PerfilEmpleado.objects.create(
            usuario=self.administrador, rol=PerfilEmpleado.Rol.ADMINISTRADOR
        )
        self.mesero = User.objects.create_user(
            username='mesero1', password='test12345'
        )
        PerfilEmpleado.objects.create(
            usuario=self.mesero, rol=PerfilEmpleado.Rol.MESERO
        )
        self.cajero = User.objects.create_user(
            username='cajero1', password='test12345'
        )
        PerfilEmpleado.objects.create(
            usuario=self.cajero, rol=PerfilEmpleado.Rol.CAJERO
        )
        self.cocina = User.objects.create_user(
            username='cocina1', password='test12345'
        )
        PerfilEmpleado.objects.create(
            usuario=self.cocina, rol=PerfilEmpleado.Rol.COCINA
        )
        self.cliente = _crear_cliente()
        self.mesa = _crear_mesa()

    def _crear_reserva(self, estado=Reserva.Estado.PENDIENTE, **kwargs):
        datos = {'fecha_hora': _fecha_futura()}
        datos.update(kwargs)
        return Reserva.objects.create(
            cliente=self.cliente,
            mesa=self.mesa,
            cantidad_personas=2,
            estado=estado,
            usuario=self.administrador,
            **datos,
        )

    def test_visitante_no_autenticado_es_redirigido_al_login(self):
        response = self.client.get(reverse('lista_reservas'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('lista_reservas')}",
        )

    def test_cajero_y_cocina_no_pueden_ver_las_reservas(self):
        self.client.login(username='cajero1', password='test12345')
        response = self.client.get(reverse('lista_reservas'))
        self.assertEqual(response.status_code, 403)
        self.client.login(username='cocina1', password='test12345')
        response = self.client.get(reverse('lista_reservas'))
        self.assertEqual(response.status_code, 403)

    def test_mesero_y_administrador_pueden_ver_las_reservas(self):
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('lista_reservas'))
        self.assertEqual(response.status_code, 200)
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(reverse('lista_reservas'))
        self.assertEqual(response.status_code, 200)

    def test_el_mesero_crea_una_reserva(self):
        self.client.login(username='mesero1', password='test12345')
        response = self.client.post(
            reverse('crear_reserva'),
            {
                'cliente': self.cliente.pk,
                'mesa': self.mesa.pk,
                'fecha_hora': _fecha_futura().strftime('%Y-%m-%dT%H:%M'),
                'cantidad_personas': '2',
                'duracion_minutos': '120',
                'observacion': '',
            },
        )
        reserva = Reserva.objects.get()
        self.assertRedirects(
            response, reverse('detalle_reserva', args=[reserva.pk])
        )
        self.assertEqual(reserva.usuario, self.mesero)
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE)

    def test_el_mesero_crea_un_cliente_pero_no_puede_editarlo(self):
        self.client.login(username='mesero1', password='test12345')
        response = self.client.post(
            reverse('crear_cliente'),
            {
                'nombres': 'Nuevo',
                'apellidos': 'Cliente',
                'documento': '',
                'telefono': '999111222',
                'email': '',
                'observacion': '',
                'activo': True,
            },
        )
        self.assertRedirects(response, reverse('lista_clientes'))
        response = self.client.get(
            reverse('editar_cliente', args=[self.cliente.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_el_administrador_edita_un_cliente(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('editar_cliente', args=[self.cliente.pk]),
            {
                'nombres': 'Juan Carlos',
                'apellidos': 'Pérez',
                'documento': '',
                'telefono': '987654321',
                'email': 'juan@example.com',
                'observacion': '',
                'activo': True,
            },
        )
        self.assertRedirects(response, reverse('lista_clientes'))
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.nombres, 'Juan Carlos')

    def test_no_se_puede_crear_un_cliente_con_documento_duplicado(self):
        _crear_cliente(nombres='Otro', documento='71234567')
        form = ClienteForm(
            data={
                'nombres': 'Nuevo',
                'apellidos': 'Cliente',
                'documento': '71234567',
                'telefono': '999111222',
                'email': '',
                'observacion': '',
                'activo': True,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn('documento', form.errors)

    def test_el_administrador_confirma_una_reserva(self):
        reserva = self._crear_reserva()
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('confirmar_reserva', args=[reserva.pk])
        )
        self.assertRedirects(
            response, reverse('detalle_reserva', args=[reserva.pk])
        )
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.CONFIRMADA)

    def test_no_se_puede_confirmar_una_reserva_de_una_mesa_inactiva(self):
        reserva = self._crear_reserva()
        self.mesa.activo = False
        self.mesa.save()
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('confirmar_reserva', args=[reserva.pk]), follow=True
        )
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE)
        self.assertTrue(
            any(
                'inactiva' in str(m).lower()
                for m in response.context.get('messages')
            )
        )

    def test_no_se_puede_cambiar_el_estado_de_una_reserva_cancelada(self):
        reserva = self._crear_reserva(estado=Reserva.Estado.CANCELADA)
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('confirmar_reserva', args=[reserva.pk]), follow=True
        )
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)

    def test_transiciones_validas_e_invalidas(self):
        reserva = self._crear_reserva()
        self.client.login(username='admin1', password='test12345')

        response = self.client.post(
            reverse('confirmar_reserva', args=[reserva.pk])
        )
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.CONFIRMADA)

        response = self.client.post(
            reverse('atender_reserva', args=[reserva.pk])
        )
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.ATENDIDA)

        response = self.client.post(
            reverse('confirmar_reserva', args=[reserva.pk]), follow=True
        )
        self.assertRedirects(
            response, reverse('detalle_reserva', args=[reserva.pk])
        )
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.ATENDIDA)
        self.assertTrue(
            any(
                'No se puede cambiar la reserva a ese estado.' in str(m)
                for m in response.context.get('messages')
            )
        )

    def test_no_se_puede_editar_una_reserva_ya_atendida(self):
        reserva = self._crear_reserva(estado=Reserva.Estado.ATENDIDA)
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(
            reverse('editar_reserva', args=[reserva.pk]), follow=True
        )
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.ATENDIDA)

    def test_el_detalle_muestra_botones_segun_el_estado(self):
        reserva = self._crear_reserva()
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(
            reverse('detalle_reserva', args=[reserva.pk])
        )
        self.assertContains(response, 'Confirmar reserva')
        self.assertContains(response, 'Cancelar reserva')
        self.assertNotContains(response, 'Marcar como atendida')

    def test_la_lista_filtra_por_fecha(self):
        reserva_fecha_a = self._crear_reserva(
            fecha_hora=_fecha_futura(dias=2)
        )
        reserva_fecha_b = self._crear_reserva(
            fecha_hora=_fecha_futura(dias=3)
        )
        self.client.login(username='admin1', password='test12345')
        fecha_local_a = timezone.localtime(reserva_fecha_a.fecha_hora).date()
        response = self.client.get(
            reverse('lista_reservas'),
            {'fecha': fecha_local_a.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        reservas = response.context['reservas']
        self.assertIn(reserva_fecha_a, reservas)
        self.assertNotIn(reserva_fecha_b, reservas)

    def test_el_enlace_reservas_solo_aparece_para_roles_permitidos(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, '>Reservas</a>')
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, '>Reservas</a>')
        self.client.login(username='cajero1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, '>Reservas</a>')
        self.client.login(username='cocina1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, '>Reservas</a>')
