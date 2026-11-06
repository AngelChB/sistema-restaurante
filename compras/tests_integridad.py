from datetime import date
from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from inventario.models import Ingrediente, MovimientoInventario, UnidadMedida

from .models import Compra, DetalleCompra, Proveedor
from .services import recibir_compra


class ComprasIntegridadTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='compras', password='Clave123!'
        )
        proveedor = Proveedor.objects.create(razon_social='Proveedor')
        self.compra = Compra.objects.create(
            proveedor=proveedor, usuario=self.user, fecha_documento=date.today()
        )
        unidad = UnidadMedida.objects.create(nombre='Kilo', abreviatura='kg')
        self.ingrediente = Ingrediente.objects.create(
            nombre='Arroz', unidad_medida=unidad
        )
        self.detalle = DetalleCompra.objects.create(
            compra=self.compra,
            ingrediente=self.ingrediente,
            cantidad=5,
            costo_unitario=2,
        )

    def test_recepcion_actualiza_stock_solo_una_vez(self):
        recibir_compra(self.compra.pk, self.user)
        with self.assertRaises(ValidationError):
            recibir_compra(self.compra.pk, self.user)
        self.ingrediente.refresh_from_db()
        self.assertEqual(self.ingrediente.stock_actual, Decimal('5'))
        self.assertEqual(MovimientoInventario.objects.count(), 1)

    def test_no_se_puede_marcar_recibida_directamente(self):
        self.compra.estado = Compra.Estado.RECIBIDA
        with self.assertRaises(ValidationError):
            self.compra.save()
        self.compra.refresh_from_db()
        self.assertEqual(self.compra.estado, Compra.Estado.BORRADOR)
        self.assertFalse(MovimientoInventario.objects.exists())

    def test_no_se_puede_crear_compra_ya_recibida(self):
        self.compra.pk = None
        self.compra.estado = Compra.Estado.RECIBIDA
        with self.assertRaises(ValidationError):
            self.compra.save()

    def test_no_se_puede_editar_cabecera_recibida(self):
        recibir_compra(self.compra.pk, self.user)
        self.compra.refresh_from_db()
        self.compra.numero_documento = 'OTRO'
        with self.assertRaises(ValidationError):
            self.compra.save()

    def test_no_se_puede_editar_eliminar_o_mover_detalle_recibido(self):
        recibir_compra(self.compra.pk, self.user)
        self.detalle.cantidad = 8
        with self.assertRaises(ValidationError):
            self.detalle.save()
        with self.assertRaises(ValidationError):
            self.detalle.delete()
        otro = Compra.objects.create(
            proveedor=self.compra.proveedor,
            usuario=self.user,
            fecha_documento=date.today(),
        )
        self.detalle.compra = otro
        with self.assertRaises(ValidationError):
            self.detalle.save()
        self.detalle.refresh_from_db()
        self.assertEqual(self.detalle.cantidad, Decimal('5'))

    def test_no_se_puede_agregar_detalle_a_compra_cancelada(self):
        self.compra.estado = Compra.Estado.CANCELADA
        self.compra.save()
        with self.assertRaises(ValidationError):
            DetalleCompra.objects.create(
                compra=self.compra,
                ingrediente=self.ingrediente,
                cantidad=3,
                costo_unitario=2,
            )

    def test_no_se_puede_eliminar_compra_recibida(self):
        recibir_compra(self.compra.pk, self.user)
        with self.assertRaises(ValidationError):
            self.compra.delete()

    def test_admin_protege_estado_y_eliminacion_masiva(self):
        request = RequestFactory().get('/admin/')
        request.user = self.user
        compra_admin = admin.site._registry[Compra]
        self.assertIn('estado', compra_admin.get_readonly_fields(request, self.compra))
        self.assertFalse(compra_admin.has_delete_permission(request))
        detalle_admin = admin.site._registry[DetalleCompra]
        self.assertFalse(detalle_admin.has_add_permission(request))
        self.assertFalse(detalle_admin.has_change_permission(request, self.detalle))
        self.assertFalse(detalle_admin.has_delete_permission(request))
