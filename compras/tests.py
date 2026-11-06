from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from inventario.models import Ingrediente, MovimientoInventario, UnidadMedida
from personal.models import PerfilEmpleado

from .forms import ProveedorForm
from .models import Compra, DetalleCompra, Proveedor
from .services import recibir_compra


class ComprasModelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.usuario = User.objects.create_user(
            username='admin1', password='test12345'
        )
        self.unidad = UnidadMedida.objects.create(
            nombre='Kilogramo', abreviatura='kg'
        )
        self.harina = Ingrediente.objects.create(
            nombre='Harina',
            unidad_medida=self.unidad,
            stock_actual=Decimal('0'),
            stock_minimo=Decimal('10'),
            costo_unitario=Decimal('5.00'),
        )
        self.proveedor = Proveedor.objects.create(
            razon_social='Distribuidora del Norte',
            ruc='20123456789',
        )

    def _crear_compra(self):
        compra = Compra.objects.create(
            proveedor=self.proveedor,
            usuario=self.usuario,
            numero_documento='F001-000001',
            fecha_documento=date.today(),
        )
        DetalleCompra.objects.create(
            compra=compra,
            ingrediente=self.harina,
            cantidad=Decimal('50'),
            costo_unitario=Decimal('5.0000'),
        )
        return compra

    def test_el_subtotal_es_cantidad_por_costo(self):
        compra = self._crear_compra()
        detalle = compra.detalles.get()
        self.assertEqual(detalle.subtotal, Decimal('250.0000'))

    def test_el_total_es_la_suma_de_los_subtotales(self):
        compra = self._crear_compra()
        DetalleCompra.objects.create(
            compra=compra,
            ingrediente=Ingrediente.objects.create(
                nombre='Azúcar',
                unidad_medida=self.unidad,
                stock_actual=Decimal('0'),
                costo_unitario=Decimal('4.00'),
            ),
            cantidad=Decimal('10'),
            costo_unitario=Decimal('4.0000'),
        )
        self.assertEqual(compra.total, Decimal('290.0000'))

    def test_no_se_puede_repetir_un_ingrediente_en_la_misma_compra(self):
        compra = self._crear_compra()
        with self.assertRaises((ValidationError, IntegrityError)):
            with transaction.atomic():
                DetalleCompra.objects.create(
                    compra=compra,
                    ingrediente=self.harina,
                    cantidad=Decimal('20'),
                    costo_unitario=Decimal('6.0000'),
                )

    def test_la_cantidad_de_un_detalle_debe_ser_mayor_que_cero(self):
        compra = self._crear_compra()
        with self.assertRaises(ValidationError):
            DetalleCompra.objects.create(
                compra=compra,
                ingrediente=Ingrediente.objects.create(
                    nombre='Sal',
                    unidad_medida=self.unidad,
                    stock_actual=Decimal('0'),
                ),
                cantidad=Decimal('0'),
                costo_unitario=Decimal('1.0000'),
            )

    def test_el_costo_unitario_de_un_detalle_no_puede_ser_negativo(self):
        compra = self._crear_compra()
        with self.assertRaises(ValidationError):
            DetalleCompra.objects.create(
                compra=compra,
                ingrediente=Ingrediente.objects.create(
                    nombre='Sal',
                    unidad_medida=self.unidad,
                    stock_actual=Decimal('0'),
                ),
                cantidad=Decimal('5'),
                costo_unitario=Decimal('-1.0000'),
            )

    def test_una_compra_cancelada_no_puede_recibirse_directamente(self):
        compra = self._crear_compra()
        compra.estado = Compra.Estado.CANCELADA
        compra.save()
        compra.estado = Compra.Estado.RECIBIDA
        with self.assertRaises(ValidationError):
            compra.save()

    def test_el_formulario_rechaza_un_ruc_invalido(self):
        form = ProveedorForm(
            data={
                'razon_social': 'Nuevo proveedor',
                'ruc': '1234',
                'contacto': '',
                'telefono': '',
                'email': '',
                'direccion': '',
                'activo': True,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn('ruc', form.errors)

    def test_el_formulario_acepta_un_proveedor_sin_ruc(self):
        form = ProveedorForm(
            data={
                'razon_social': 'Nuevo proveedor',
                'ruc': '',
                'contacto': '',
                'telefono': '',
                'email': '',
                'direccion': '',
                'activo': True,
            }
        )
        self.assertTrue(form.is_valid())


class RecibirCompraTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.usuario = User.objects.create_user(
            username='admin1', password='test12345'
        )
        self.unidad = UnidadMedida.objects.create(
            nombre='Kilogramo', abreviatura='kg'
        )
        self.harina = Ingrediente.objects.create(
            nombre='Harina',
            unidad_medida=self.unidad,
            stock_actual=Decimal('100'),
            stock_minimo=Decimal('10'),
            costo_unitario=Decimal('5.00'),
        )
        self.azucar = Ingrediente.objects.create(
            nombre='Azúcar',
            unidad_medida=self.unidad,
            stock_actual=Decimal('100'),
            stock_minimo=Decimal('10'),
            costo_unitario=Decimal('4.00'),
        )
        self.proveedor = Proveedor.objects.create(
            razon_social='Distribuidora del Norte',
            ruc='20123456789',
        )

    def _crear_compra(self, estado=Compra.Estado.BORRADOR):
        compra = Compra.objects.create(
            proveedor=self.proveedor,
            usuario=self.usuario,
            estado=Compra.Estado.BORRADOR,
            numero_documento='F001-000001',
            fecha_documento=date.today(),
        )
        if estado != Compra.Estado.BORRADOR:
            compra.estado = estado
            compra.save()
        return compra

    def _agregar_detalle(self, compra, ingrediente, cantidad, costo):
        DetalleCompra.objects.create(
            compra=compra,
            ingrediente=ingrediente,
            cantidad=cantidad,
            costo_unitario=costo,
        )

    def test_recibir_una_compra_aumenta_el_stock(self):
        compra = self._crear_compra()
        self._agregar_detalle(
            compra, self.harina, Decimal('50'), Decimal('5.0000')
        )
        recibir_compra(compra.pk, self.usuario)
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock_actual, Decimal('150'))

    def test_recibir_una_compra_crea_movimientos_de_entrada(self):
        compra = self._crear_compra()
        self._agregar_detalle(
            compra, self.harina, Decimal('50'), Decimal('5.0000')
        )
        self._agregar_detalle(
            compra, self.azucar, Decimal('20'), Decimal('4.0000')
        )
        recibir_compra(compra.pk, self.usuario)
        movimientos = MovimientoInventario.objects.filter(compra=compra)
        self.assertEqual(movimientos.count(), 2)
        self.assertEqual(
            set(movimientos.values_list('tipo', flat=True)),
            {MovimientoInventario.Tipo.ENTRADA},
        )
        self.assertEqual(
            set(movimientos.values_list('ingrediente_id', flat=True)),
            {self.harina.pk, self.azucar.pk},
        )

    def test_el_movimiento_guarda_compra_usuario_y_stocks(self):
        compra = self._crear_compra()
        self._agregar_detalle(
            compra, self.harina, Decimal('50'), Decimal('5.0000')
        )
        recibir_compra(compra.pk, self.usuario)
        movimiento = MovimientoInventario.objects.get(compra=compra)
        self.assertEqual(movimiento.compra, compra)
        self.assertEqual(movimiento.usuario, self.usuario)
        self.assertEqual(movimiento.stock_anterior, Decimal('100'))
        self.assertEqual(movimiento.stock_resultante, Decimal('150'))
        self.assertEqual(movimiento.referencia, f'COMPRA-{compra.id}')
        self.assertEqual(
            movimiento.motivo, f'Ingreso por compra #{compra.id}'
        )

    def test_recibir_una_compra_actualiza_el_costo_unitario(self):
        compra = self._crear_compra()
        self._agregar_detalle(
            compra, self.harina, Decimal('50'), Decimal('4.5000')
        )
        recibir_compra(compra.pk, self.usuario)
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.costo_unitario, Decimal('4.5000'))

    def test_la_compra_cambia_a_recibida_y_guarda_la_fecha(self):
        compra = self._crear_compra()
        self._agregar_detalle(
            compra, self.harina, Decimal('50'), Decimal('5.0000')
        )
        recibir_compra(compra.pk, self.usuario)
        compra.refresh_from_db()
        self.assertEqual(compra.estado, Compra.Estado.RECIBIDA)
        self.assertIsNotNone(compra.fecha_recepcion)

    def test_una_compra_no_puede_recibirse_dos_veces(self):
        compra = self._crear_compra()
        self._agregar_detalle(
            compra, self.harina, Decimal('50'), Decimal('5.0000')
        )
        recibir_compra(compra.pk, self.usuario)
        with self.assertRaises(ValidationError):
            recibir_compra(compra.pk, self.usuario)
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock_actual, Decimal('150'))
        self.assertEqual(
            MovimientoInventario.objects.filter(compra=compra).count(), 1
        )

    def test_una_compra_cancelada_no_puede_recibirse(self):
        compra = self._crear_compra()
        self._agregar_detalle(
            compra, self.harina, Decimal('50'), Decimal('5.0000')
        )
        compra.estado = Compra.Estado.CANCELADA
        compra.save()
        with self.assertRaises(ValidationError):
            recibir_compra(compra.pk, self.usuario)
        compra.refresh_from_db()
        self.assertEqual(compra.estado, Compra.Estado.CANCELADA)
        self.assertEqual(MovimientoInventario.objects.count(), 0)

    def test_una_compra_sin_detalles_no_puede_recibirse(self):
        compra = self._crear_compra()
        with self.assertRaises(ValidationError):
            recibir_compra(compra.pk, self.usuario)
        compra.refresh_from_db()
        self.assertEqual(compra.estado, Compra.Estado.BORRADOR)
        self.assertEqual(MovimientoInventario.objects.count(), 0)

    def test_un_ingrediente_inactivo_impide_la_recepcion(self):
        self.harina.activo = False
        self.harina.save()
        compra = self._crear_compra()
        self._agregar_detalle(
            compra, self.harina, Decimal('50'), Decimal('5.0000')
        )
        self._agregar_detalle(
            compra, self.azucar, Decimal('20'), Decimal('4.0000')
        )
        with self.assertRaises(ValidationError):
            recibir_compra(compra.pk, self.usuario)
        compra.refresh_from_db()
        self.assertEqual(compra.estado, Compra.Estado.BORRADOR)
        self.harina.refresh_from_db()
        self.azucar.refresh_from_db()
        self.assertEqual(self.harina.stock_actual, Decimal('100'))
        self.assertEqual(self.azucar.stock_actual, Decimal('100'))
        self.assertEqual(MovimientoInventario.objects.count(), 0)


class ComprasViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.administrador = User.objects.create_user(
            username='admin1', password='test12345', is_staff=True
        )
        PerfilEmpleado.objects.create(
            usuario=self.administrador, rol=PerfilEmpleado.Rol.ADMINISTRADOR
        )
        self.superusuario = User.objects.create_user(
            username='super1', password='test12345', is_superuser=True
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
        self.unidad = UnidadMedida.objects.create(
            nombre='Kilogramo', abreviatura='kg'
        )
        self.harina = Ingrediente.objects.create(
            nombre='Harina',
            unidad_medida=self.unidad,
            stock_actual=Decimal('0'),
            stock_minimo=Decimal('10'),
            costo_unitario=Decimal('5.00'),
        )
        self.proveedor = Proveedor.objects.create(
            razon_social='Distribuidora del Norte',
            ruc='20123456789',
        )

    def _crear_compra(self, estado=Compra.Estado.BORRADOR):
        compra = Compra.objects.create(
            proveedor=self.proveedor,
            usuario=self.administrador,
            estado=Compra.Estado.BORRADOR,
            numero_documento='F001-000001',
            fecha_documento=date.today(),
        )
        DetalleCompra.objects.create(
            compra=compra,
            ingrediente=self.harina,
            cantidad=Decimal('50'),
            costo_unitario=Decimal('5.0000'),
        )
        if estado == Compra.Estado.RECIBIDA:
            compra = recibir_compra(compra.pk, self.administrador)
        elif estado == Compra.Estado.CANCELADA:
            compra.estado = estado
            compra.save()
        return compra

    def test_visitante_no_autenticado_es_redirigido_al_login(self):
        response = self.client.get(reverse('lista_compras'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('lista_compras')}",
        )

    def test_mesero_y_cajero_no_pueden_ver_las_compras(self):
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('lista_compras'))
        self.assertEqual(response.status_code, 403)
        self.client.login(username='cajero1', password='test12345')
        response = self.client.get(reverse('lista_compras'))
        self.assertEqual(response.status_code, 403)

    def test_cocina_puede_ver_las_compras(self):
        self.client.login(username='cocina1', password='test12345')
        response = self.client.get(reverse('lista_compras'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Compras')

    def test_cocina_no_puede_crear_una_compra(self):
        self.client.login(username='cocina1', password='test12345')
        response = self.client.post(reverse('crear_compra'))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Compra.objects.count(), 0)

    def test_cocina_no_puede_recibir_una_compra(self):
        compra = self._crear_compra()
        self.client.login(username='cocina1', password='test12345')
        response = self.client.post(reverse('recibir_compra', args=[compra.pk]))
        self.assertEqual(response.status_code, 403)
        compra.refresh_from_db()
        self.assertEqual(compra.estado, Compra.Estado.BORRADOR)
        self.assertEqual(MovimientoInventario.objects.count(), 0)

    def test_el_administrador_crea_un_proveedor(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('crear_proveedor'),
            {
                'razon_social': 'Proveedor Nuevo',
                'ruc': '20123456788',
                'contacto': 'Juan',
                'telefono': '999999999',
                'email': 'juan@example.com',
                'direccion': 'Av. Principal 123',
                'activo': 'on',
            },
        )
        self.assertRedirects(response, reverse('lista_proveedores'))
        self.assertTrue(
            Proveedor.objects.filter(razon_social='Proveedor Nuevo').exists()
        )

    def test_el_administrador_no_puede_crear_un_proveedor_con_ruc_invalido(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('crear_proveedor'),
            {
                'razon_social': 'Proveedor Nuevo',
                'ruc': '1234',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Proveedor.objects.count(), 1)

    def test_el_administrador_crea_una_compra_con_ingredientes(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('crear_compra'),
            {
                'proveedor': self.proveedor.pk,
                'numero_documento': 'F001-000001',
                'fecha_documento': '2026-08-07',
                'observacion': '',
                'detalles-TOTAL_FORMS': '1',
                'detalles-INITIAL_FORMS': '0',
                'detalles-MIN_NUM_FORMS': '1',
                'detalles-MAX_NUM_FORMS': '1000',
                'detalles-0-ingrediente': self.harina.pk,
                'detalles-0-cantidad': '50',
                'detalles-0-costo_unitario': '5.0000',
                'detalles-0-id': '',
            },
        )
        compra = Compra.objects.get()
        self.assertRedirects(response, reverse('detalle_compra', args=[compra.pk]))
        self.assertEqual(compra.usuario, self.administrador)
        self.assertEqual(compra.estado, Compra.Estado.BORRADOR)
        self.assertEqual(compra.detalles.count(), 1)
        self.assertEqual(compra.total, Decimal('250.0000'))

    def test_el_administrador_crea_una_compra_sin_numero_de_documento(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('crear_compra'),
            {
                'proveedor': self.proveedor.pk,
                'numero_documento': '',
                'fecha_documento': '2026-08-07',
                'observacion': '',
                'detalles-TOTAL_FORMS': '1',
                'detalles-INITIAL_FORMS': '0',
                'detalles-MIN_NUM_FORMS': '1',
                'detalles-MAX_NUM_FORMS': '1000',
                'detalles-0-ingrediente': self.harina.pk,
                'detalles-0-cantidad': '50',
                'detalles-0-costo_unitario': '5.0000',
                'detalles-0-id': '',
            },
        )
        compra = Compra.objects.get()
        self.assertRedirects(response, reverse('detalle_compra', args=[compra.pk]))
        self.assertEqual(compra.numero_documento, '')

    def test_el_administrador_edita_una_compra_en_borrador(self):
        compra = self._crear_compra()
        detalle = compra.detalles.get()
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('editar_compra', args=[compra.pk]),
            {
                'proveedor': self.proveedor.pk,
                'numero_documento': 'F001-000002',
                'fecha_documento': '2026-08-07',
                'observacion': 'Actualizada',
                'detalles-TOTAL_FORMS': '1',
                'detalles-INITIAL_FORMS': '1',
                'detalles-MIN_NUM_FORMS': '1',
                'detalles-MAX_NUM_FORMS': '1000',
                'detalles-0-id': detalle.pk,
                'detalles-0-ingrediente': self.harina.pk,
                'detalles-0-cantidad': '75',
                'detalles-0-costo_unitario': '4.0000',
            },
        )
        self.assertRedirects(response, reverse('detalle_compra', args=[compra.pk]))
        compra.refresh_from_db()
        self.assertEqual(compra.numero_documento, 'F001-000002')
        self.assertEqual(compra.observacion, 'Actualizada')
        detalle.refresh_from_db()
        self.assertEqual(detalle.cantidad, Decimal('75'))
        self.assertEqual(detalle.costo_unitario, Decimal('4.0000'))
        self.assertEqual(compra.estado, Compra.Estado.BORRADOR)

    def test_no_se_puede_editar_una_compra_recibida(self):
        compra = self._crear_compra(estado=Compra.Estado.RECIBIDA)
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(
            reverse('editar_compra', args=[compra.pk]), follow=True
        )
        mensajes = [str(m) for m in response.context.get('messages')]
        self.assertTrue(any('borrador' in mensaje.lower() for mensaje in mensajes))
        compra.refresh_from_db()
        self.assertEqual(compra.estado, Compra.Estado.RECIBIDA)

    def test_cocina_no_puede_editar_una_compra(self):
        compra = self._crear_compra()
        self.client.login(username='cocina1', password='test12345')
        response = self.client.get(
            reverse('editar_compra', args=[compra.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_no_se_puede_crear_una_compra_con_ingrediente_repetido(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('crear_compra'),
            {
                'proveedor': self.proveedor.pk,
                'numero_documento': 'F001-000001',
                'fecha_documento': '2026-08-07',
                'detalles-TOTAL_FORMS': '2',
                'detalles-INITIAL_FORMS': '0',
                'detalles-MIN_NUM_FORMS': '1',
                'detalles-MAX_NUM_FORMS': '1000',
                'detalles-0-ingrediente': self.harina.pk,
                'detalles-0-cantidad': '50',
                'detalles-0-costo_unitario': '5.0000',
                'detalles-0-id': '',
                'detalles-1-ingrediente': self.harina.pk,
                'detalles-1-cantidad': '10',
                'detalles-1-costo_unitario': '6.0000',
                'detalles-1-id': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Compra.objects.count(), 0)

    def test_el_administrador_recibe_una_compra(self):
        compra = self._crear_compra()
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('recibir_compra', args=[compra.pk])
        )
        self.assertRedirects(response, reverse('detalle_compra', args=[compra.pk]))
        compra.refresh_from_db()
        self.assertEqual(compra.estado, Compra.Estado.RECIBIDA)
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock_actual, Decimal('50'))

    def test_el_administrador_cancela_una_compra(self):
        compra = self._crear_compra()
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('cancelar_compra', args=[compra.pk])
        )
        self.assertRedirects(response, reverse('detalle_compra', args=[compra.pk]))
        compra.refresh_from_db()
        self.assertEqual(compra.estado, Compra.Estado.CANCELADA)
        self.assertEqual(MovimientoInventario.objects.count(), 0)

    def test_no_se_puede_cancelar_una_compra_recibida(self):
        compra = self._crear_compra(estado=Compra.Estado.RECIBIDA)
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('cancelar_compra', args=[compra.pk]), follow=True
        )
        mensajes = [str(m) for m in response.context.get('messages')]
        self.assertTrue(
            any('borrador' in mensaje.lower() for mensaje in mensajes)
        )
        compra.refresh_from_db()
        self.assertEqual(compra.estado, Compra.Estado.RECIBIDA)

    def test_no_se_puede_recibir_una_compra_cancelada(self):
        compra = self._crear_compra(estado=Compra.Estado.CANCELADA)
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('recibir_compra', args=[compra.pk]), follow=True
        )
        mensajes = [str(m) for m in response.context.get('messages')]
        self.assertTrue(any('borrador' in mensaje.lower() for mensaje in mensajes))
        compra.refresh_from_db()
        self.assertEqual(compra.estado, Compra.Estado.CANCELADA)
        self.assertEqual(MovimientoInventario.objects.count(), 0)

    def test_el_superusuario_crea_y_recibe_una_compra(self):
        self.client.login(username='super1', password='test12345')
        response = self.client.get(reverse('lista_compras'))
        self.assertEqual(response.status_code, 200)
        compra = self._crear_compra()
        response = self.client.post(
            reverse('recibir_compra', args=[compra.pk])
        )
        self.assertRedirects(response, reverse('detalle_compra', args=[compra.pk]))
        compra.refresh_from_db()
        self.assertEqual(compra.estado, Compra.Estado.RECIBIDA)

    def test_el_detalle_muestra_total_y_botones_segun_el_estado(self):
        compra = self._crear_compra()
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(reverse('detalle_compra', args=[compra.pk]))
        self.assertContains(response, 'Recibir compra')
        self.assertContains(response, 'Cancelar compra')
        self.assertContains(response, 'Editar compra')
        self.assertContains(response, 'S/ 250.00')

    def test_el_enlace_compras_solo_aparece_para_roles_permitidos(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, '>Compras</a>')
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, '>Compras</a>')
        self.client.login(username='cajero1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, '>Compras</a>')
        self.client.login(username='cocina1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, '>Compras</a>')
