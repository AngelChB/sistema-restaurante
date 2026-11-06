from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from catalogo.models import Categoria, Producto
from mesas.models import Mesa
from pedidos.models import Pedido, DetallePedido
from inventario.models import UnidadMedida, Ingrediente, RecetaProducto, MovimientoInventario
from caja.models import Pago


class IntegridadFlujoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username='flujo', password='Prueba123!')
        self.client.force_login(self.user)
        categoria = Categoria.objects.create(nombre='Menu')
        self.producto = Producto.objects.create(categoria=categoria, nombre='Plato', precio=Decimal('10'))
        mesa = Mesa.objects.create(numero=1, capacidad=4)
        self.pedido = Pedido.objects.create(mesa=mesa, mesero=self.user)
        self.detalle = DetallePedido.objects.create(pedido=self.pedido, producto=self.producto, cantidad=2)
        unidad = UnidadMedida.objects.create(nombre='Kilo', abreviatura='kg')
        self.ingrediente = Ingrediente.objects.create(nombre='Arroz', unidad_medida=unidad, stock_actual=10)
        RecetaProducto.objects.create(producto=self.producto, ingrediente=self.ingrediente, cantidad=1)

    def preparar(self):
        return self.client.post(reverse('cambiar_estado_pedido', args=[self.pedido.pk]), {'estado': Pedido.Estado.EN_PREPARACION})

    def cobrar(self):
        self.pedido.estado = Pedido.Estado.ENTREGADO
        self.pedido.save()
        return Pago.objects.create(pedido=self.pedido, cajero=self.user, metodo=Pago.Metodo.EFECTIVO, monto=20, monto_recibido=20)

    def test_preparar_desde_pedidos_descuenta_stock_una_vez(self):
        self.assertEqual(self.preparar().status_code, 302)
        self.preparar()
        self.ingrediente.refresh_from_db()
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estado, Pedido.Estado.EN_PREPARACION)
        self.assertEqual(self.ingrediente.stock_actual, Decimal('8'))
        self.assertEqual(MovimientoInventario.objects.filter(pedido=self.pedido).count(), 1)

    def test_stock_insuficiente_no_cambia_pedido_ni_inventario(self):
        self.ingrediente.stock_actual = 1
        self.ingrediente.save()
        self.preparar()
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estado, Pedido.Estado.ABIERTO)
        self.assertFalse(MovimientoInventario.objects.exists())

    def test_sin_receta_no_inicia_preparacion(self):
        RecetaProducto.objects.all().delete()
        self.preparar()
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estado, Pedido.Estado.ABIERTO)

    def test_pago_existente_permite_observacion_sin_error(self):
        pago = self.cobrar()
        pago.full_clean()
        pago.observacion = 'Nota de caja'
        pago.save()
        pago.refresh_from_db()
        self.assertEqual(pago.observacion, 'Nota de caja')

    def test_no_se_pueden_cambiar_importes_de_pago(self):
        pago = self.cobrar()
        pago.monto = Decimal('30')
        with self.assertRaises(ValidationError):
            pago.save()
        pago.refresh_from_db()
        self.assertEqual(pago.monto, Decimal('20'))

    def test_no_se_puede_editar_detalle_pagado(self):
        self.cobrar()
        self.detalle.cantidad = 5
        with self.assertRaises(ValidationError):
            self.detalle.save()
        self.detalle.refresh_from_db()
        self.assertEqual(self.detalle.cantidad, 2)

    def test_no_se_puede_agregar_o_eliminar_detalle_pagado(self):
        self.cobrar()
        with self.assertRaises(ValidationError):
            self.detalle.delete()
        with self.assertRaises(ValidationError):
            DetallePedido.objects.create(pedido=self.pedido, producto=self.producto, cantidad=1)

    def test_no_se_puede_mover_detalle_desde_pedido_pagado(self):
        self.cobrar()
        mesa = Mesa.objects.create(numero=2, capacidad=4)
        otro = Pedido.objects.create(mesa=mesa, mesero=self.user)
        self.detalle.pedido = otro
        with self.assertRaises(ValidationError):
            self.detalle.save()

    def test_admin_no_permite_editar_estado_ni_pedido_pagado(self):
        from django.contrib import admin
        from django.test import RequestFactory
        request = RequestFactory().get('/admin/')
        request.user = self.user
        model_admin = admin.site._registry[Pedido]
        self.assertIn('estado', model_admin.get_readonly_fields(request, self.pedido))
        self.cobrar()
        self.assertFalse(model_admin.has_change_permission(request, self.pedido))
        self.assertFalse(model_admin.has_delete_permission(request, self.pedido))
