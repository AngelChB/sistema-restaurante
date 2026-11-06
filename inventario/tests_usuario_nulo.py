from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Ingrediente, MovimientoInventario, UnidadMedida


class MovimientoSinUsuarioTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username='inventario', password='Clave123!'
        )
        self.client.force_login(self.admin)
        unidad = UnidadMedida.objects.create(nombre='Kilo', abreviatura='kg')
        ingrediente = Ingrediente.objects.create(nombre='Arroz', unidad_medida=unidad)
        self.movimiento = MovimientoInventario.objects.create(
            ingrediente=ingrediente,
            tipo='ENTRADA',
            cantidad=5,
            motivo='Stock inicial',
            usuario=None,
        )

    def test_panel_muestra_movimiento_sin_usuario(self):
        response = self.client.get(reverse('panel_inventario'))
        self.assertContains(response, 'Sin usuario')
        self.assertContains(response, 'Arroz')

    def test_historial_muestra_movimiento_sin_usuario(self):
        response = self.client.get(reverse('historial_movimientos'))
        self.assertContains(response, 'Sin usuario')
        self.assertContains(response, 'Stock inicial')

    def test_sigue_funcionando_con_usuario_asociado(self):
        # Actualización de fixture: no cambia el stock ni edita un movimiento real.
        MovimientoInventario.objects.filter(pk=self.movimiento.pk).update(
            usuario=self.admin
        )
        for ruta in ['panel_inventario', 'historial_movimientos']:
            with self.subTest(ruta=ruta):
                response = self.client.get(reverse(ruta))
                self.assertContains(response, 'inventario')
                self.assertNotContains(response, 'Sin usuario')
