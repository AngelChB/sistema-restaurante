from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from unittest.mock import patch
from io import StringIO
from pedidos.models import Pedido
from caja.models import Pago
from inventario.models import MovimientoInventario


class CargarDemoTests(TestCase):
    def test_rechaza_configuracion_habitual(self):
        with self.assertRaises(CommandError):
            call_command('cargar_demo', stdout=StringIO())
        self.assertFalse(Pedido.objects.exists())

    @patch('core.management.commands.cargar_demo.es_base_demo', return_value=True)
    def test_demo_completa_y_segunda_ejecucion_no_sobrescribe(self, _):
        call_command('cargar_demo', stdout=StringIO())
        self.assertEqual(Pedido.objects.count(), 8)
        self.assertEqual(Pago.objects.count(), 4)
        self.assertTrue(MovimientoInventario.objects.exists())
        self.assertEqual(Pedido.objects.filter(estado='PAGADO').count(), 4)
        before = MovimientoInventario.objects.count()
        with self.assertRaises(CommandError):
            call_command('cargar_demo', stdout=StringIO())
        self.assertEqual(MovimientoInventario.objects.count(), before)
        self.assertEqual(Pago.objects.count(), 4)
