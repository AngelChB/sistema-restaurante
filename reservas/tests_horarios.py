from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from mesas.models import Mesa
from .models import Cliente, Reserva


class HorarioReservasTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username='horario', password='Clave123!')
        self.client.force_login(self.user)
        self.mesa = Mesa.objects.create(numero=1, capacidad=4)
        self.cliente = Cliente.objects.create(nombres='Cliente', telefono='999')
        self.reserva = Reserva.objects.create(cliente=self.cliente, mesa=self.mesa, usuario=self.user,
            fecha_hora=timezone.now()+timedelta(days=1), cantidad_personas=2, estado='CONFIRMADA')

    def mover_horario(self, horas):
        Reserva.objects.filter(pk=self.reserva.pk).update(fecha_hora=timezone.now()+timedelta(hours=horas))
        self.reserva.refresh_from_db()

    def test_reserva_vencida_se_advierte_sin_cambiar_estado(self):
        self.mover_horario(-3)
        self.assertTrue(self.reserva.vencida)
        response = self.client.get(reverse('detalle_reserva', args=[self.reserva.pk]))
        self.assertContains(response, 'horario de esta reserva ya terminó')
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.CONFIRMADA)

    def test_mesas_excluye_reservas_terminadas(self):
        self.mover_horario(-3)
        response = self.client.get(reverse('lista_mesas'))
        self.assertIsNone(response.context['mesas_info'][0]['reserva'])

    def test_mesas_mantiene_reserva_en_curso(self):
        self.mover_horario(-1)
        response = self.client.get(reverse('lista_mesas'))
        self.assertEqual(response.context['mesas_info'][0]['reserva'].pk, self.reserva.pk)

    def test_permite_cerrar_reserva_de_mesa_retirada(self):
        self.mesa.activo = False
        self.mesa.save()
        response = self.client.post(reverse('cancelar_reserva', args=[self.reserva.pk]))
        self.assertEqual(response.status_code, 302)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.CANCELADA)

    def test_atendida_ofrece_crear_pedido_sin_crearlo_vacio(self):
        self.client.post(reverse('atender_reserva', args=[self.reserva.pk]))
        response = self.client.get(reverse('detalle_reserva', args=[self.reserva.pk]))
        self.assertContains(response, 'Crear pedido en esta mesa')
        from pedidos.models import Pedido
        self.assertFalse(Pedido.objects.exists())

    def test_mesa_inactiva_no_ofrece_nuevo_pedido(self):
        self.mesa.activo = False
        self.mesa.save()
        response = self.client.get(reverse('lista_mesas'))
        self.assertNotContains(response, 'Nuevo pedido')
        self.assertEqual(response.context['resumen']['libres'], 0)
