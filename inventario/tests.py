from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from catalogo.models import Categoria, Producto
from mesas.models import Mesa
from pedidos.models import DetallePedido, Pedido
from personal.models import PerfilEmpleado

from .models import Ingrediente, MovimientoInventario, RecetaProducto, UnidadMedida
from .services import iniciar_preparacion_con_descuento


class InventarioModelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.usuario = User.objects.create_user(
            username='usuario1', password='test12345'
        )
        self.unidad = UnidadMedida.objects.create(nombre='Kilogramo', abreviatura='kg')
        self.ingrediente = Ingrediente.objects.create(
            nombre='Harina',
            unidad_medida=self.unidad,
            stock_actual=Decimal('0'),
            stock_minimo=Decimal('10'),
            costo_unitario=Decimal('5.00'),
        )
        self.categoria = Categoria.objects.create(nombre='Bebidas')
        self.producto = Producto.objects.create(
            categoria=self.categoria,
            nombre='Café',
            precio=Decimal('12.50'),
            disponible=True,
        )

    def _crear_movimiento(self, tipo, cantidad, **extra):
        valores = {
            'ingrediente': self.ingrediente,
            'tipo': tipo,
            'cantidad': cantidad,
            'motivo': 'Prueba',
            'usuario': self.usuario,
        }
        valores.update(extra)
        return MovimientoInventario.objects.create(**valores)

    def test_una_entrada_aumenta_el_stock(self):
        self._crear_movimiento(MovimientoInventario.Tipo.ENTRADA, Decimal('50'))
        self.ingrediente.refresh_from_db()
        self.assertEqual(self.ingrediente.stock_actual, Decimal('50'))

    def test_una_salida_disminuye_el_stock(self):
        self._crear_movimiento(MovimientoInventario.Tipo.ENTRADA, Decimal('50'))
        self._crear_movimiento(MovimientoInventario.Tipo.SALIDA, Decimal('20'))
        self.ingrediente.refresh_from_db()
        self.assertEqual(self.ingrediente.stock_actual, Decimal('30'))

    def test_un_ajuste_positivo_aumenta_el_stock(self):
        self._crear_movimiento(MovimientoInventario.Tipo.AJUSTE_POSITIVO, Decimal('15'))
        self.ingrediente.refresh_from_db()
        self.assertEqual(self.ingrediente.stock_actual, Decimal('15'))

    def test_un_ajuste_negativo_disminuye_el_stock(self):
        self._crear_movimiento(MovimientoInventario.Tipo.ENTRADA, Decimal('40'))
        self._crear_movimiento(MovimientoInventario.Tipo.AJUSTE_NEGATIVO, Decimal('10'))
        self.ingrediente.refresh_from_db()
        self.assertEqual(self.ingrediente.stock_actual, Decimal('30'))

    def test_no_se_permite_una_salida_mayor_al_stock_disponible(self):
        with self.assertRaises(ValidationError):
            self._crear_movimiento(MovimientoInventario.Tipo.SALIDA, Decimal('5'))
        self.ingrediente.refresh_from_db()
        self.assertEqual(self.ingrediente.stock_actual, Decimal('0'))
        self.assertEqual(MovimientoInventario.objects.count(), 0)

    def test_no_se_permite_un_ajuste_negativo_mayor_al_stock_disponible(self):
        self._crear_movimiento(MovimientoInventario.Tipo.ENTRADA, Decimal('5'))
        with self.assertRaises(ValidationError):
            self._crear_movimiento(
                MovimientoInventario.Tipo.AJUSTE_NEGATIVO, Decimal('10')
            )
        self.ingrediente.refresh_from_db()
        self.assertEqual(self.ingrediente.stock_actual, Decimal('5'))

    def test_no_se_permite_cantidad_cero_ni_negativa(self):
        for cantidad in (Decimal('0'), Decimal('-1')):
            with self.assertRaises(ValidationError):
                self._crear_movimiento(MovimientoInventario.Tipo.ENTRADA, cantidad)
        self.ingrediente.refresh_from_db()
        self.assertEqual(self.ingrediente.stock_actual, Decimal('0'))
        self.assertEqual(MovimientoInventario.objects.count(), 0)

    def test_se_guardan_correctamente_stock_anterior_y_stock_resultante(self):
        entrada = self._crear_movimiento(
            MovimientoInventario.Tipo.ENTRADA, Decimal('50')
        )
        self.assertEqual(entrada.stock_anterior, Decimal('0'))
        self.assertEqual(entrada.stock_resultante, Decimal('50'))
        salida = self._crear_movimiento(MovimientoInventario.Tipo.SALIDA, Decimal('20'))
        self.assertEqual(salida.stock_anterior, Decimal('50'))
        self.assertEqual(salida.stock_resultante, Decimal('30'))

    def test_un_movimiento_ya_creado_no_puede_modificarse(self):
        movimiento = self._crear_movimiento(
            MovimientoInventario.Tipo.ENTRADA, Decimal('10')
        )
        movimiento.motivo = 'Cambio'
        with self.assertRaises(ValidationError):
            movimiento.save()

    def test_un_movimiento_no_puede_eliminarse(self):
        self._crear_movimiento(MovimientoInventario.Tipo.ENTRADA, Decimal('10'))
        movimiento = MovimientoInventario.objects.get()
        with self.assertRaises(ValidationError):
            movimiento.delete()
        self.assertEqual(MovimientoInventario.objects.count(), 1)

    def test_no_se_permite_repetir_un_ingrediente_en_la_receta_del_mismo_producto(self):
        RecetaProducto.objects.create(
            producto=self.producto,
            ingrediente=self.ingrediente,
            cantidad=Decimal('1'),
        )
        with self.assertRaises(ValidationError):
            RecetaProducto.objects.create(
                producto=self.producto,
                ingrediente=self.ingrediente,
                cantidad=Decimal('2'),
            )

    def test_la_cantidad_de_una_receta_debe_ser_mayor_que_cero(self):
        with self.assertRaises(ValidationError):
            RecetaProducto.objects.create(
                producto=self.producto,
                ingrediente=self.ingrediente,
                cantidad=Decimal('0'),
            )

    def test_bajo_stock_funciona_correctamente(self):
        self.assertTrue(self.ingrediente.bajo_stock)
        self._crear_movimiento(MovimientoInventario.Tipo.ENTRADA, Decimal('50'))
        self.ingrediente.refresh_from_db()
        self.assertFalse(self.ingrediente.bajo_stock)

    def test_bajo_stock_es_cierto_cuando_el_stock_iguala_al_minimo(self):
        self.ingrediente.stock_minimo = Decimal('0')
        self.ingrediente.save()
        self.assertTrue(self.ingrediente.bajo_stock)

    def test_no_se_permiten_valores_negativos_en_stock_actual(self):
        with self.assertRaises(ValidationError):
            Ingrediente.objects.create(
                nombre='Levadura',
                unidad_medida=self.unidad,
                stock_actual=Decimal('-1'),
            )

    def test_no_se_permiten_valores_negativos_en_stock_minimo(self):
        with self.assertRaises(ValidationError):
            Ingrediente.objects.create(
                nombre='Sal',
                unidad_medida=self.unidad,
                stock_minimo=Decimal('-1'),
            )

    def test_no_se_permiten_valores_negativos_en_costo_unitario(self):
        with self.assertRaises(ValidationError):
            Ingrediente.objects.create(
                nombre='Azúcar',
                unidad_medida=self.unidad,
                costo_unitario=Decimal('-1'),
            )


class InventarioViewsTests(TestCase):
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
        self.mesero = User.objects.create_user(username='mesero1', password='test12345')
        PerfilEmpleado.objects.create(
            usuario=self.mesero, rol=PerfilEmpleado.Rol.MESERO
        )
        self.cajero = User.objects.create_user(username='cajero1', password='test12345')
        PerfilEmpleado.objects.create(
            usuario=self.cajero, rol=PerfilEmpleado.Rol.CAJERO
        )
        self.cocina = User.objects.create_user(username='cocina1', password='test12345')
        PerfilEmpleado.objects.create(
            usuario=self.cocina, rol=PerfilEmpleado.Rol.COCINA
        )
        self.unidad = UnidadMedida.objects.create(nombre='Kilogramo', abreviatura='kg')
        self.ingrediente = Ingrediente.objects.create(
            nombre='Harina',
            unidad_medida=self.unidad,
            stock_actual=Decimal('0'),
            stock_minimo=Decimal('10'),
            costo_unitario=Decimal('5.00'),
        )
        self.categoria = Categoria.objects.create(nombre='Bebidas')
        self.producto = Producto.objects.create(
            categoria=self.categoria,
            nombre='Café',
            precio=Decimal('12.50'),
            disponible=True,
        )

    def _registrar_entrada(self, cantidad=50):
        return MovimientoInventario.objects.create(
            ingrediente=self.ingrediente,
            tipo=MovimientoInventario.Tipo.ENTRADA,
            cantidad=cantidad,
            motivo='Compra',
            usuario=self.administrador,
        )

    def test_visitante_no_autenticado_es_redirigido_al_login(self):
        response = self.client.get(reverse('panel_inventario'))
        self.assertRedirects(
            response,
            f'{reverse("login")}?next={reverse("panel_inventario")}',
        )

    def test_mesero_y_cajero_no_pueden_ver_el_panel(self):
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('panel_inventario'))
        self.assertEqual(response.status_code, 403)
        self.client.login(username='cajero1', password='test12345')
        response = self.client.get(reverse('panel_inventario'))
        self.assertEqual(response.status_code, 403)

    def test_cocina_puede_ver_el_panel(self):
        self.client.login(username='cocina1', password='test12345')
        response = self.client.get(reverse('panel_inventario'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Panel de inventario')

    def test_el_panel_muestra_el_resumen_del_inventario(self):
        self._registrar_entrada(50)
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(reverse('panel_inventario'))
        self.assertContains(response, 'Ingredientes activos')
        self.assertContains(response, 'S/ 250.00')

    def test_el_panel_muestra_los_ingredientes_con_bajo_stock(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(reverse('panel_inventario'))
        self.assertContains(response, 'Harina')
        self.assertContains(response, 'Con bajo stock')
        self.assertContains(response, 'Sin stock')

    def test_cocina_no_puede_registrar_movimientos(self):
        self.client.login(username='cocina1', password='test12345')
        response = self.client.post(
            reverse('registrar_movimiento'),
            {
                'ingrediente': self.ingrediente.pk,
                'tipo': MovimientoInventario.Tipo.ENTRADA,
                'cantidad': '10',
                'motivo': 'Compra',
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(MovimientoInventario.objects.count(), 0)

    def test_el_administrador_registra_una_entrada(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('registrar_movimiento'),
            {
                'ingrediente': self.ingrediente.pk,
                'tipo': MovimientoInventario.Tipo.ENTRADA,
                'cantidad': '25',
                'motivo': 'Compra a proveedor',
            },
        )
        self.assertRedirects(response, reverse('historial_movimientos'))
        self.ingrediente.refresh_from_db()
        self.assertEqual(self.ingrediente.stock_actual, Decimal('25'))

    def test_el_administrador_registra_una_salida(self):
        self._registrar_entrada(30)
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('registrar_movimiento'),
            {
                'ingrediente': self.ingrediente.pk,
                'tipo': MovimientoInventario.Tipo.SALIDA,
                'cantidad': '10',
                'motivo': 'Uso en cocina',
            },
        )
        self.assertRedirects(response, reverse('historial_movimientos'))
        self.ingrediente.refresh_from_db()
        self.assertEqual(self.ingrediente.stock_actual, Decimal('20'))

    def test_el_movimiento_registra_al_usuario_autenticado(self):
        self.client.login(username='admin1', password='test12345')
        self.client.post(
            reverse('registrar_movimiento'),
            {
                'ingrediente': self.ingrediente.pk,
                'tipo': MovimientoInventario.Tipo.ENTRADA,
                'cantidad': '25',
                'motivo': 'Compra',
            },
        )
        movimiento = MovimientoInventario.objects.get()
        self.assertEqual(movimiento.usuario, self.administrador)

    def test_no_se_registra_una_salida_mayor_al_stock_disponible(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('registrar_movimiento'),
            {
                'ingrediente': self.ingrediente.pk,
                'tipo': MovimientoInventario.Tipo.SALIDA,
                'cantidad': '5',
                'motivo': 'Uso',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MovimientoInventario.objects.count(), 0)

    def test_el_superusuario_gestiona_el_inventario(self):
        self.client.login(username='super1', password='test12345')
        response = self.client.get(reverse('panel_inventario'))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            reverse('registrar_movimiento'),
            {
                'ingrediente': self.ingrediente.pk,
                'tipo': MovimientoInventario.Tipo.ENTRADA,
                'cantidad': '10',
                'motivo': 'Compra',
            },
        )
        self.assertRedirects(response, reverse('historial_movimientos'))
        self.ingrediente.refresh_from_db()
        self.assertEqual(self.ingrediente.stock_actual, Decimal('10'))

    def test_el_formulario_no_modifica_el_stock_actual_al_crear(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('crear_ingrediente'),
            {
                'nombre': 'Sal',
                'unidad_medida': self.unidad.pk,
                'stock_minimo': '5',
                'costo_unitario': '1.50',
                'activo': 'on',
                'stock_actual': '999',
            },
        )
        self.assertRedirects(response, reverse('lista_ingredientes'))
        sal = Ingrediente.objects.get(nombre='Sal')
        self.assertEqual(sal.stock_actual, Decimal('0'))

    def test_el_filtro_de_bajo_stock_funciona(self):
        Ingrediente.objects.create(
            nombre='Azúcar',
            unidad_medida=self.unidad,
            stock_actual=Decimal('50'),
            stock_minimo=Decimal('10'),
        )
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(reverse('lista_ingredientes'), {'stock': 'bajo'})
        self.assertContains(response, 'Harina')
        self.assertNotContains(response, 'Azúcar')

    def test_la_busqueda_por_nombre_funciona(self):
        self.client.login(username='cocina1', password='test12345')
        response = self.client.get(reverse('lista_ingredientes'), {'buscar': 'Har'})
        self.assertContains(response, 'Harina')

    def test_el_historial_muestra_stock_anterior_y_resultante(self):
        self._registrar_entrada(50)
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(reverse('historial_movimientos'))
        self.assertContains(response, 'Stock anterior')
        self.assertContains(response, 'Stock resultante')
        self.assertContains(response, 'Harina')
        self.assertContains(response, 'Compra')

    def test_el_historial_filtra_por_tipo(self):
        self._registrar_entrada(50)
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(
            reverse('historial_movimientos'),
            {'tipo': MovimientoInventario.Tipo.SALIDA},
        )
        self.assertContains(response, 'No se encontraron movimientos')

    def test_el_administrador_crea_una_unidad_de_medida(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('crear_unidad'),
            {'nombre': 'Litro', 'abreviatura': 'L'},
        )
        self.assertRedirects(response, reverse('lista_unidades'))
        self.assertTrue(UnidadMedida.objects.filter(nombre='Litro').exists())

    def test_el_administrador_agrega_ingrediente_a_una_receta(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('crear_receta'),
            {
                'producto': self.producto.pk,
                'ingrediente': self.ingrediente.pk,
                'cantidad': '0.5',
            },
        )
        self.assertRedirects(response, reverse('lista_recetas'))
        self.assertTrue(
            RecetaProducto.objects.filter(
                producto=self.producto,
                ingrediente=self.ingrediente,
            ).exists()
        )

    def test_no_se_repite_un_ingrediente_en_la_receta_de_un_producto(self):
        RecetaProducto.objects.create(
            producto=self.producto,
            ingrediente=self.ingrediente,
            cantidad=Decimal('0.5'),
        )
        self.client.login(username='admin1', password='test12345')
        response = self.client.post(
            reverse('crear_receta'),
            {
                'producto': self.producto.pk,
                'ingrediente': self.ingrediente.pk,
                'cantidad': '1',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(RecetaProducto.objects.count(), 1)

    def test_cocina_consulta_las_recetas(self):
        RecetaProducto.objects.create(
            producto=self.producto,
            ingrediente=self.ingrediente,
            cantidad=Decimal('0.5'),
        )
        self.client.login(username='cocina1', password='test12345')
        response = self.client.get(reverse('lista_recetas'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Café')
        self.assertContains(response, 'Harina')

    def test_el_enlace_inventario_solo_aparece_para_roles_permitidos(self):
        self.client.login(username='admin1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, '>Inventario</a>')
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, '>Inventario</a>')
        self.client.login(username='cajero1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, '>Inventario</a>')
        self.client.login(username='cocina1', password='test12345')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, '>Inventario</a>')


class DescuentoPreparacionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.cocinero = User.objects.create_user(
            username='cocinero1', password='test12345'
        )
        PerfilEmpleado.objects.create(
            usuario=self.cocinero, rol=PerfilEmpleado.Rol.COCINA
        )
        self.mesero = User.objects.create_user(username='mesero1', password='test12345')
        self.unidad = UnidadMedida.objects.create(nombre='Kilogramo', abreviatura='kg')
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
        self.categoria = Categoria.objects.create(nombre='Bebidas')
        self.cafe = Producto.objects.create(
            categoria=self.categoria,
            nombre='Café',
            precio=Decimal('12.50'),
            disponible=True,
        )
        self.sandwich = Producto.objects.create(
            categoria=self.categoria,
            nombre='Sandwich',
            precio=Decimal('18.00'),
            disponible=True,
        )
        self.mesa = Mesa.objects.create(numero=1, capacidad=4)

    def _receta(self, producto, ingrediente, cantidad):
        return RecetaProducto.objects.create(
            producto=producto, ingrediente=ingrediente, cantidad=cantidad
        )

    def _crear_pedido_abierto(self, productos):
        pedido = Pedido.objects.create(mesa=self.mesa, mesero=self.mesero)
        for producto, cantidad in productos:
            DetallePedido.objects.create(
                pedido=pedido, producto=producto, cantidad=cantidad
            )
        return pedido

    def test_un_pedido_con_receta_descuenta_el_stock(self):
        self._receta(self.cafe, self.harina, Decimal('0.5'))
        pedido = self._crear_pedido_abierto([(self.cafe, 1)])
        iniciar_preparacion_con_descuento(pedido.pk, self.cocinero)
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock_actual, Decimal('99.5'))

    def test_la_cantidad_descontada_considera_la_cantidad_pedida(self):
        self._receta(self.cafe, self.harina, Decimal('0.5'))
        pedido = self._crear_pedido_abierto([(self.cafe, 3)])
        iniciar_preparacion_con_descuento(pedido.pk, self.cocinero)
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock_actual, Decimal('98.5'))

    def test_dos_productos_con_el_mismo_ingrediente_generan_un_solo_movimiento(self):
        self._receta(self.cafe, self.harina, Decimal('0.5'))
        self._receta(self.sandwich, self.harina, Decimal('1'))
        pedido = self._crear_pedido_abierto(
            [
                (self.cafe, 2),
                (self.sandwich, 3),
            ]
        )
        iniciar_preparacion_con_descuento(pedido.pk, self.cocinero)
        movimientos = MovimientoInventario.objects.filter(pedido=pedido)
        self.assertEqual(movimientos.count(), 1)
        movimiento = movimientos.get()
        self.assertEqual(movimiento.cantidad, Decimal('4'))
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock_actual, Decimal('96'))

    def test_se_crea_un_movimiento_salida_por_ingrediente(self):
        self._receta(self.cafe, self.harina, Decimal('0.5'))
        self._receta(self.sandwich, self.harina, Decimal('1'))
        self._receta(self.sandwich, self.azucar, Decimal('0.25'))
        pedido = self._crear_pedido_abierto(
            [
                (self.cafe, 1),
                (self.sandwich, 1),
            ]
        )
        iniciar_preparacion_con_descuento(pedido.pk, self.cocinero)
        movimientos = MovimientoInventario.objects.filter(pedido=pedido)
        self.assertEqual(movimientos.count(), 2)
        self.assertEqual(
            set(movimientos.values_list('tipo', flat=True)),
            {MovimientoInventario.Tipo.SALIDA},
        )
        self.assertEqual(
            set(movimientos.values_list('ingrediente_id', flat=True)),
            {self.harina.pk, self.azucar.pk},
        )

    def test_el_movimiento_guarda_pedido_usuario_y_stocks(self):
        self._receta(self.cafe, self.harina, Decimal('0.5'))
        pedido = self._crear_pedido_abierto([(self.cafe, 1)])
        iniciar_preparacion_con_descuento(pedido.pk, self.cocinero)
        movimiento = MovimientoInventario.objects.get(pedido=pedido)
        self.assertEqual(movimiento.pedido, pedido)
        self.assertEqual(movimiento.usuario, self.cocinero)
        self.assertEqual(movimiento.stock_anterior, Decimal('100'))
        self.assertEqual(movimiento.stock_resultante, Decimal('99.5'))
        self.assertEqual(movimiento.referencia, f'PEDIDO-{pedido.id}')
        self.assertEqual(
            movimiento.motivo, f'Consumo por preparación del pedido #{pedido.id}'
        )

    def test_el_pedido_cambia_a_en_preparacion_despues_del_descuento(self):
        self._receta(self.cafe, self.harina, Decimal('0.5'))
        pedido = self._crear_pedido_abierto([(self.cafe, 1)])
        resultado = iniciar_preparacion_con_descuento(pedido.pk, self.cocinero)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.EN_PREPARACION)
        self.assertEqual(resultado.pk, pedido.pk)

    def test_un_pedido_no_puede_descontar_inventario_dos_veces(self):
        self._receta(self.cafe, self.harina, Decimal('0.5'))
        pedido = self._crear_pedido_abierto([(self.cafe, 1)])
        iniciar_preparacion_con_descuento(pedido.pk, self.cocinero)
        with self.assertRaises(ValidationError):
            iniciar_preparacion_con_descuento(pedido.pk, self.cocinero)
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock_actual, Decimal('99.5'))
        self.assertEqual(MovimientoInventario.objects.count(), 1)

    def test_cambiar_en_preparacion_a_listo_no_vuelve_a_descontar(self):
        self._receta(self.cafe, self.harina, Decimal('0.5'))
        pedido = self._crear_pedido_abierto([(self.cafe, 1)])
        iniciar_preparacion_con_descuento(pedido.pk, self.cocinero)
        pedido.estado = Pedido.Estado.LISTO
        pedido.save()
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock_actual, Decimal('99.5'))
        self.assertEqual(MovimientoInventario.objects.count(), 1)

    def test_un_pedido_sin_productos_no_puede_prepararse(self):
        pedido = Pedido.objects.create(mesa=self.mesa, mesero=self.mesero)
        with self.assertRaises(ValidationError):
            iniciar_preparacion_con_descuento(pedido.pk, self.cocinero)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.ABIERTO)
        self.assertEqual(MovimientoInventario.objects.count(), 0)

    def test_un_producto_sin_receta_impide_comenzar_la_preparacion(self):
        self._receta(self.cafe, self.harina, Decimal('0.5'))
        jugo = Producto.objects.create(
            categoria=self.categoria,
            nombre='Jugo',
            precio=Decimal('9.00'),
            disponible=True,
        )
        pedido = self._crear_pedido_abierto([(jugo, 1)])
        with self.assertRaises(ValidationError) as contexto:
            iniciar_preparacion_con_descuento(pedido.pk, self.cocinero)
        self.assertIn('Jugo', str(contexto.exception))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.ABIERTO)
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock_actual, Decimal('100'))
        self.assertEqual(MovimientoInventario.objects.count(), 0)

    def test_el_stock_insuficiente_impide_comenzar_la_preparacion(self):
        self._receta(self.cafe, self.harina, Decimal('2'))
        self.harina.stock_actual = Decimal('1')
        self.harina.save()
        pedido = self._crear_pedido_abierto([(self.cafe, 1)])
        with self.assertRaises(ValidationError) as contexto:
            iniciar_preparacion_con_descuento(pedido.pk, self.cocinero)
        self.assertIn('Harina', str(contexto.exception))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.ABIERTO)
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock_actual, Decimal('1'))
        self.assertEqual(MovimientoInventario.objects.count(), 0)

    def test_cuando_falta_un_ingrediente_ningun_otro_es_descontado(self):
        self._receta(self.cafe, self.harina, Decimal('2'))
        self._receta(self.cafe, self.azucar, Decimal('1'))
        self.azucar.stock_actual = Decimal('0')
        self.azucar.save()
        pedido = self._crear_pedido_abierto([(self.cafe, 1)])
        with self.assertRaises(ValidationError):
            iniciar_preparacion_con_descuento(pedido.pk, self.cocinero)
        self.harina.refresh_from_db()
        self.azucar.refresh_from_db()
        self.assertEqual(self.harina.stock_actual, Decimal('100'))
        self.assertEqual(self.azucar.stock_actual, Decimal('0'))
        self.assertEqual(MovimientoInventario.objects.count(), 0)

    def test_un_ingrediente_inactivo_impide_comenzar_la_preparacion(self):
        self._receta(self.cafe, self.harina, Decimal('0.5'))
        self.harina.activo = False
        self.harina.save()
        pedido = self._crear_pedido_abierto([(self.cafe, 1)])
        with self.assertRaises(ValidationError) as contexto:
            iniciar_preparacion_con_descuento(pedido.pk, self.cocinero)
        self.assertIn('inactivos', str(contexto.exception))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.ABIERTO)
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock_actual, Decimal('100'))
        self.assertEqual(MovimientoInventario.objects.count(), 0)

    def test_cancelar_un_pedido_abierto_no_descuenta_inventario(self):
        self._receta(self.cafe, self.harina, Decimal('0.5'))
        pedido = self._crear_pedido_abierto([(self.cafe, 1)])
        pedido.estado = Pedido.Estado.CANCELADO
        pedido.save()
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock_actual, Decimal('100'))
        self.assertEqual(MovimientoInventario.objects.count(), 0)

    def test_una_cancelacion_posterior_no_devuelve_los_ingredientes(self):
        self._receta(self.cafe, self.harina, Decimal('0.5'))
        pedido = self._crear_pedido_abierto([(self.cafe, 1)])
        iniciar_preparacion_con_descuento(pedido.pk, self.cocinero)
        pedido.estado = Pedido.Estado.CANCELADO
        pedido.save()
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock_actual, Decimal('99.5'))
        self.assertEqual(MovimientoInventario.objects.count(), 1)
