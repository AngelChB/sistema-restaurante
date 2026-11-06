import csv
from datetime import datetime, timezone as dt_timezone
from io import StringIO
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from caja.models import Pago
from catalogo.models import Categoria, Producto
from mesas.models import Mesa
from pedidos.models import Pedido, DetallePedido
from .views import _texto_csv


class ExportacionSeguraTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username='csv', password='Clave123!')
        self.client.force_login(self.user)
        categoria = Categoria.objects.create(nombre='Menu')
        producto = Producto.objects.create(categoria=categoria, nombre='Plato', precio=10)
        mesa = Mesa.objects.create(numero=1, capacidad=4)
        pedido = Pedido.objects.create(mesa=mesa, mesero=self.user, estado=Pedido.Estado.ABIERTO)
        DetallePedido.objects.create(pedido=pedido, producto=producto, cantidad=1)
        pedido.estado = Pedido.Estado.ENTREGADO
        pedido.save()
        self.pago = Pago.objects.create(pedido=pedido, cajero=self.user, metodo='EFECTIVO', monto=10, monto_recibido=10)

    def filas(self, **filtros):
        response = self.client.get(reverse('exportar_ventas_csv'), filtros)
        self.assertEqual(response.status_code, 200)
        return list(csv.reader(StringIO(response.content.decode('utf-8-sig'))))

    def test_textos_parecidos_a_formulas_quedan_como_texto(self):
        for texto in ['=1+1', '+123', '-123', '@SUM(A1)', '  =1+1', '\t=1+1', '\r1', '\n1']:
            with self.subTest(texto=texto):
                self.assertEqual(_texto_csv(texto), "'" + texto)

    def test_exporta_nombres_y_referencias_sin_formulas(self):
        self.user.first_name = '=1+1'; self.user.save()
        self.pago.referencia = '+123'; self.pago.save()
        fila = self.filas()[1]
        self.assertEqual(fila[4], "'=1+1")
        self.assertEqual(fila[5], "'=1+1")
        self.assertEqual(fila[10], "'+123")
        self.pago.refresh_from_db()
        self.assertEqual(self.pago.referencia, '+123')
        self.assertEqual(fila[7], '10.00')

    def test_texto_normal_comillas_y_comas_se_conservan(self):
        self.pago.referencia = 'Operación, "café"'; self.pago.save()
        self.assertEqual(self.filas()[1][10], 'Operación, "café"')
        self.assertEqual(_texto_csv(''), '')

    def test_fecha_exportada_usa_lima_incluso_si_cambia_el_dia_utc(self):
        Pago.objects.filter(pk=self.pago.pk).update(fecha_pago=datetime(2026, 11, 7, 2, 30, tzinfo=dt_timezone.utc))
        filas = self.filas(fecha_desde='2026-11-06', fecha_hasta='2026-11-06')
        self.assertEqual(len(filas), 2)
        self.assertEqual(filas[1][1], '06/11/2026 21:30')
