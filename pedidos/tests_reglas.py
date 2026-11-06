from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from caja.models import Pago
from catalogo.models import Categoria, Producto
from inventario.models import UnidadMedida, Ingrediente, RecetaProducto, MovimientoInventario
from inventario.services import iniciar_preparacion_con_descuento
from mesas.models import Mesa
from .models import Pedido, DetallePedido


class ReglasPedidoTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_superuser(username='reglas', password='Clave123!')
        self.client.force_login(self.usuario)
        self.mesa = Mesa.objects.create(numero=1, capacidad=4)
        categoria = Categoria.objects.create(nombre='Menú')
        self.producto = Producto.objects.create(categoria=categoria, nombre='Arroz con pollo', precio=15)
        unidad = UnidadMedida.objects.create(nombre='Kilo', abreviatura='kg')
        self.ingrediente = Ingrediente.objects.create(nombre='Arroz', unidad_medida=unidad, stock_actual=10)
        RecetaProducto.objects.create(producto=self.producto, ingrediente=self.ingrediente, cantidad=Decimal('0.25'))
        self.pedido = Pedido.objects.create(mesa=self.mesa, mesero=self.usuario)
        self.detalle = DetallePedido.objects.create(pedido=self.pedido, producto=self.producto, cantidad=2)

    def test_preparacion_bloquea_edicion_alta_y_eliminacion(self):
        iniciar_preparacion_con_descuento(self.pedido.pk, self.usuario)
        self.detalle.cantidad = 3
        with self.assertRaises(ValidationError): self.detalle.save()
        with self.assertRaises(ValidationError): self.detalle.delete()
        with self.assertRaises(ValidationError):
            DetallePedido.objects.create(pedido=self.pedido, producto=self.producto, cantidad=1)
        self.detalle.refresh_from_db()
        self.assertEqual(self.detalle.cantidad, 2)
        self.ingrediente.refresh_from_db()
        self.assertEqual(self.ingrediente.stock_actual, Decimal('9.5'))

    def test_no_puede_reabrirse_para_evitar_bloqueo(self):
        iniciar_preparacion_con_descuento(self.pedido.pk, self.usuario)
        self.pedido.estado = Pedido.Estado.ABIERTO
        with self.assertRaises(ValidationError): self.pedido.save()

    def test_pagado_sin_cobro_es_rechazado(self):
        self.pedido.estado = Pedido.Estado.PAGADO
        with self.assertRaises(ValidationError): self.pedido.save()
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estado, Pedido.Estado.ABIERTO)

    def test_no_se_puede_crear_pagado_sin_cobro(self):
        mesa = Mesa.objects.create(numero=2, capacidad=4)
        with self.assertRaises(ValidationError):
            Pedido.objects.create(mesa=mesa, mesero=self.usuario, estado='PAGADO')

    def test_pedido_cobrado_no_puede_cancelarse(self):
        self.pedido.estado = Pedido.Estado.ENTREGADO; self.pedido.save()
        Pago.objects.create(pedido=self.pedido, cajero=self.usuario, metodo='EFECTIVO', monto=30, monto_recibido=30)
        self.pedido.estado = Pedido.Estado.CANCELADO
        with self.assertRaises(ValidationError): self.pedido.save()

    def test_flujo_completo_por_pantallas(self):
        # Retirar el pedido abierto del setup antes de crear otro en esa mesa.
        self.pedido.delete()
        datos = {'mesa': self.mesa.pk, 'observacion': 'Prueba de recorrido',
            'detalles-TOTAL_FORMS': '1', 'detalles-INITIAL_FORMS': '0',
            'detalles-MIN_NUM_FORMS': '1', 'detalles-MAX_NUM_FORMS': '1000',
            'detalles-0-producto': self.producto.pk, 'detalles-0-cantidad': '2',
            'detalles-0-observacion': ''}
        response = self.client.post(reverse('crear_pedido'), datos)
        self.assertEqual(response.status_code, 302)
        pedido = Pedido.objects.get(observacion='Prueba de recorrido')
        self.mesa.refresh_from_db(); self.assertEqual(self.mesa.estado, 'OCUPADA')
        self.assertEqual(pedido.total, Decimal('30'))
        for ruta in ['panel_cocina', 'detalle_pedido']:
            response = self.client.get(reverse(ruta, args=[pedido.pk] if ruta=='detalle_pedido' else []))
            self.assertEqual(response.status_code, 200)
        self.client.post(reverse('actualizar_estado_cocina', args=[pedido.pk]))
        pedido.refresh_from_db(); self.assertEqual(pedido.estado, 'EN_PREPARACION')
        self.ingrediente.refresh_from_db(); self.assertEqual(self.ingrediente.stock_actual, Decimal('9.5'))
        self.assertEqual(MovimientoInventario.objects.filter(pedido=pedido).count(), 1)
        self.client.post(reverse('actualizar_estado_cocina', args=[pedido.pk]))
        pedido.refresh_from_db(); self.assertEqual(pedido.estado, 'LISTO')
        self.assertContains(self.client.get(reverse('panel_sala')), 'Arroz con pollo')
        self.client.post(reverse('marcar_pedido_entregado', args=[pedido.pk]))
        pedido.refresh_from_db(); self.assertEqual(pedido.estado, 'ENTREGADO')
        self.assertEqual(self.client.get(reverse('registrar_pago', args=[pedido.pk])).status_code, 200)
        response = self.client.post(reverse('registrar_pago', args=[pedido.pk]),
            {'metodo':'EFECTIVO', 'monto_recibido':'50', 'referencia':'', 'observacion':''})
        self.assertEqual(response.status_code, 302)
        pedido.refresh_from_db(); self.mesa.refresh_from_db()
        self.assertEqual(pedido.estado, 'PAGADO'); self.assertEqual(self.mesa.estado, 'LIBRE')
        self.assertEqual(pedido.pago.vuelto, Decimal('20'))
        self.assertEqual(self.client.get(reverse('detalle_pago', args=[pedido.pago.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('reporte_ventas')).context['total_vendido'], Decimal('30'))
