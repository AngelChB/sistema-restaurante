from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalogo.models import Categoria, Producto
from mesas.models import Mesa
from pedidos.models import DetallePedido, Pedido
from personal.models import PerfilEmpleado

from .models import CierreCaja, Pago


class PagoModelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.cajero = User.objects.create_user(
            username='cajero1', password='test12345', is_staff=True
        )
        self.mesero = User.objects.create_user(
            username='mesero1', password='test12345'
        )
        self.categoria = Categoria.objects.create(nombre='Bebidas')
        self.producto = Producto.objects.create(
            categoria=self.categoria,
            nombre='Café',
            precio=Decimal('12.50'),
            disponible=True,
        )
        self.mesa = Mesa.objects.create(numero=1, capacidad=4)

    def _pedido_entregado(self, cantidad=1):
        pedido = Pedido.objects.create(
            mesa=self.mesa,
            mesero=self.mesero,
            estado=Pedido.Estado.ABIERTO,
        )
        DetallePedido.objects.create(
            pedido=pedido, producto=self.producto, cantidad=cantidad
        )
        pedido.estado = Pedido.Estado.ENTREGADO
        pedido.save()
        return pedido

    def test_el_pago_cambia_el_pedido_a_pagado_y_libera_la_mesa(self):
        pedido = self._pedido_entregado()
        Pago.objects.create(
            pedido=pedido,
            cajero=self.cajero,
            metodo=Pago.Metodo.EFECTIVO,
            monto=pedido.total,
            monto_recibido=pedido.total,
        )
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.PAGADO)
        self.mesa.refresh_from_db()
        self.assertEqual(self.mesa.estado, Mesa.Estado.LIBRE)

    def test_el_vuelto_se_calcula_correctamente_en_efectivo(self):
        pedido = self._pedido_entregado()
        pago = Pago.objects.create(
            pedido=pedido,
            cajero=self.cajero,
            metodo=Pago.Metodo.EFECTIVO,
            monto=pedido.total,
            monto_recibido=Decimal('50.00'),
        )
        self.assertEqual(pago.vuelto, Decimal('37.50'))

    def test_el_vuelto_es_cero_para_tarjeta_yape_o_plin(self):
        for metodo in (
            Pago.Metodo.TARJETA,
            Pago.Metodo.YAPE,
            Pago.Metodo.PLIN,
        ):
            pedido = Pedido.objects.create(
                mesa=self.mesa,
                mesero=self.mesero,
                estado=Pedido.Estado.ABIERTO,
            )
            DetallePedido.objects.create(
                pedido=pedido, producto=self.producto, cantidad=1
            )
            pedido.estado = Pedido.Estado.ENTREGADO
            pedido.save()
            pago = Pago.objects.create(
                pedido=pedido,
                cajero=self.cajero,
                metodo=metodo,
                monto=pedido.total,
            )
            self.assertEqual(pago.vuelto, Decimal('0'))

    def test_no_se_puede_pagar_un_pedido_no_entregado(self):
        pedido = Pedido.objects.create(
            mesa=self.mesa,
            mesero=self.mesero,
            estado=Pedido.Estado.ABIERTO,
        )
        with self.assertRaises(ValidationError):
            Pago.objects.create(
                pedido=pedido,
                cajero=self.cajero,
                metodo=Pago.Metodo.EFECTIVO,
                monto=Decimal('12.50'),
                monto_recibido=Decimal('12.50'),
            )

    def test_no_se_pueden_registrar_dos_pagos_para_el_mismo_pedido(self):
        pedido = self._pedido_entregado()
        Pago.objects.create(
            pedido=pedido,
            cajero=self.cajero,
            metodo=Pago.Metodo.EFECTIVO,
            monto=pedido.total,
            monto_recibido=pedido.total,
        )
        with self.assertRaises(ValidationError):
            Pago.objects.create(
                pedido=pedido,
                cajero=self.cajero,
                metodo=Pago.Metodo.TARJETA,
                monto=pedido.total,
            )

    def test_el_monto_del_pago_debe_coincidir_con_el_total(self):
        pedido = self._pedido_entregado()
        with self.assertRaises(ValidationError):
            Pago.objects.create(
                pedido=pedido,
                cajero=self.cajero,
                metodo=Pago.Metodo.EFECTIVO,
                monto=pedido.total + Decimal('1.00'),
                monto_recibido=pedido.total,
            )

    def test_el_efectivo_requiere_monto_recibido(self):
        pedido = self._pedido_entregado()
        with self.assertRaises(ValidationError):
            Pago.objects.create(
                pedido=pedido,
                cajero=self.cajero,
                metodo=Pago.Metodo.EFECTIVO,
                monto=pedido.total,
            )

    def test_el_efectivo_no_puede_recibir_menos_que_el_total(self):
        pedido = self._pedido_entregado()
        with self.assertRaises(ValidationError):
            Pago.objects.create(
                pedido=pedido,
                cajero=self.cajero,
                metodo=Pago.Metodo.EFECTIVO,
                monto=pedido.total,
                monto_recibido=pedido.total - Decimal('1.00'),
            )


class CajaViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.cajero = User.objects.create_user(
            username='cajero1', password='test12345', is_staff=True
        )
        PerfilEmpleado.objects.create(
            usuario=self.cajero, rol=PerfilEmpleado.Rol.CAJERO
        )
        self.mesero = User.objects.create_user(
            username='mesero1', password='test12345'
        )
        self.mesa = Mesa.objects.create(numero=1, capacidad=4)
        self.categoria = Categoria.objects.create(nombre='Bebidas')
        self.producto = Producto.objects.create(
            categoria=self.categoria,
            nombre='Café',
            precio=Decimal('12.50'),
            disponible=True,
        )

    def _pedido_entregado(self, mesa=None, cantidad=1):
        mesa = mesa or self.mesa
        pedido = Pedido.objects.create(
            mesa=mesa,
            mesero=self.mesero,
            estado=Pedido.Estado.ABIERTO,
        )
        DetallePedido.objects.create(
            pedido=pedido, producto=self.producto, cantidad=cantidad
        )
        pedido.estado = Pedido.Estado.ENTREGADO
        pedido.save()
        return pedido

    def _crear_pago(self, pedido, metodo=Pago.Metodo.EFECTIVO):
        return Pago.objects.create(
            pedido=pedido,
            cajero=self.cajero,
            metodo=metodo,
            monto=pedido.total,
            monto_recibido=pedido.total,
        )

    def test_visitante_no_autenticado_es_redirigido_al_login(self):
        response = self.client.get(reverse('panel_caja'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('panel_caja')}",
        )

    def test_usuario_no_staff_no_puede_ver_el_panel(self):
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('panel_caja'))
        self.assertEqual(response.status_code, 403)

    def test_el_panel_muestra_el_resumen_del_dia(self):
        self.client.login(username='cajero1', password='test12345')
        pedido = self._pedido_entregado()
        self._crear_pago(pedido)
        response = self.client.get(reverse('panel_caja'))
        self.assertContains(response, 'S/ 12.50')
        self.assertContains(response, 'Pagos registrados')

    def test_el_panel_muestra_los_totales_por_metodo(self):
        self.client.login(username='cajero1', password='test12345')
        mesa2 = Mesa.objects.create(numero=2, capacidad=4)
        pedido1 = self._pedido_entregado(cantidad=2)
        pedido2 = self._pedido_entregado(mesa=mesa2)
        self._crear_pago(pedido1, metodo=Pago.Metodo.EFECTIVO)
        self._crear_pago(pedido2, metodo=Pago.Metodo.TARJETA)
        response = self.client.get(reverse('panel_caja'))
        self.assertContains(response, 'S/ 37.50')
        self.assertContains(response, 'Efectivo')
        self.assertContains(response, 'Tarjeta')

    def test_el_panel_muestra_los_pedidos_pendientes_de_pago(self):
        self.client.login(username='cajero1', password='test12345')
        self._pedido_entregado()
        response = self.client.get(reverse('panel_caja'))
        self.assertContains(response, 'Pedidos pendientes de pago')
        self.assertContains(response, 'Mesa 1')

    def test_el_panel_no_muestra_pagos_de_otros_dias(self):
        self.client.login(username='cajero1', password='test12345')
        pedido = self._pedido_entregado()
        pago = self._crear_pago(pedido)
        ayer = timezone.now() - timedelta(days=1)
        Pago.objects.filter(pk=pago.pk).update(fecha_pago=ayer)
        response = self.client.get(reverse('panel_caja'))
        self.assertContains(response, 'S/ 0.00')
        self.assertNotContains(response, 'S/ 12.50')

    def test_se_puede_registrar_un_pago_para_un_pedido_entregado(self):
        self.client.login(username='cajero1', password='test12345')
        pedido = self._pedido_entregado()
        response = self.client.post(
            reverse('registrar_pago', args=[pedido.pk]),
            {'metodo': Pago.Metodo.EFECTIVO, 'monto_recibido': '20.00'},
        )
        pago = Pago.objects.get(pedido=pedido)
        self.assertRedirects(response, reverse('detalle_pago', args=[pago.pk]))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.PAGADO)
        self.mesa.refresh_from_db()
        self.assertEqual(self.mesa.estado, Mesa.Estado.LIBRE)

    def test_el_pago_registra_al_cajero_autenticado(self):
        self.client.login(username='cajero1', password='test12345')
        pedido = self._pedido_entregado()
        self.client.post(
            reverse('registrar_pago', args=[pedido.pk]),
            {'metodo': Pago.Metodo.EFECTIVO, 'monto_recibido': '20.00'},
        )
        pago = Pago.objects.get(pedido=pedido)
        self.assertEqual(pago.cajero, self.cajero)

    def test_el_monto_del_pago_coincide_con_el_total_del_pedido(self):
        self.client.login(username='cajero1', password='test12345')
        pedido = self._pedido_entregado()
        self.client.post(
            reverse('registrar_pago', args=[pedido.pk]),
            {'metodo': Pago.Metodo.EFECTIVO, 'monto_recibido': '20.00'},
        )
        pago = Pago.objects.get(pedido=pedido)
        self.assertEqual(pago.monto, pedido.total)
        self.assertEqual(pago.vuelto, Decimal('7.50'))

    def test_no_se_puede_pagar_un_pedido_que_no_esta_entregado(self):
        self.client.login(username='cajero1', password='test12345')
        pedido = Pedido.objects.create(
            mesa=self.mesa,
            mesero=self.mesero,
            estado=Pedido.Estado.ABIERTO,
        )
        response = self.client.post(
            reverse('registrar_pago', args=[pedido.pk]),
            {'metodo': Pago.Metodo.EFECTIVO, 'monto_recibido': '20.00'},
        )
        self.assertRedirects(response, reverse('panel_caja'))
        self.assertEqual(Pago.objects.count(), 0)

    def test_no_se_pueden_registrar_dos_pagos_para_el_mismo_pedido(self):
        self.client.login(username='cajero1', password='test12345')
        pedido = self._pedido_entregado()
        self._crear_pago(pedido)
        response = self.client.post(
            reverse('registrar_pago', args=[pedido.pk]),
            {'metodo': Pago.Metodo.TARJETA},
        )
        self.assertRedirects(
            response, reverse('detalle_pago', args=[pedido.pago.pk])
        )
        self.assertEqual(Pago.objects.count(), 1)

    def test_no_se_puede_pagar_en_efectivo_sin_monto_recibido(self):
        self.client.login(username='cajero1', password='test12345')
        pedido = self._pedido_entregado()
        response = self.client.post(
            reverse('registrar_pago', args=[pedido.pk]),
            {'metodo': Pago.Metodo.EFECTIVO},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Pago.objects.count(), 0)

    def test_no_se_puede_pagar_en_efectivo_con_monto_menor_al_total(self):
        self.client.login(username='cajero1', password='test12345')
        pedido = self._pedido_entregado()
        response = self.client.post(
            reverse('registrar_pago', args=[pedido.pk]),
            {'metodo': Pago.Metodo.EFECTIVO, 'monto_recibido': '5.00'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Pago.objects.count(), 0)

    def test_se_puede_pagar_con_tarjeta_sin_monto_recibido(self):
        self.client.login(username='cajero1', password='test12345')
        pedido = self._pedido_entregado()
        response = self.client.post(
            reverse('registrar_pago', args=[pedido.pk]),
            {'metodo': Pago.Metodo.TARJETA},
        )
        pago = Pago.objects.get(pedido=pedido)
        self.assertRedirects(response, reverse('detalle_pago', args=[pago.pk]))
        self.assertEqual(pago.vuelto, Decimal('0'))

    def test_la_vista_detalle_pago_muestra_los_datos_del_pago(self):
        self.client.login(username='cajero1', password='test12345')
        pedido = self._pedido_entregado()
        pago = self._crear_pago(pedido, metodo=Pago.Metodo.EFECTIVO)
        response = self.client.get(reverse('detalle_pago', args=[pago.pk]))
        self.assertContains(response, f'Comprobante de pago N.º {pago.id}')
        self.assertContains(response, 'Café')
        self.assertContains(response, 'Efectivo')
        self.assertContains(response, 'S/ 12.50')


class CierreCajaTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.cajero = User.objects.create_user(
            username='cajero1', password='test12345', is_staff=True
        )
        PerfilEmpleado.objects.create(
            usuario=self.cajero, rol=PerfilEmpleado.Rol.CAJERO
        )
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
        self.cocina = User.objects.create_user(
            username='cocina1', password='test12345'
        )
        PerfilEmpleado.objects.create(
            usuario=self.cocina, rol=PerfilEmpleado.Rol.COCINA
        )
        self.mesa = Mesa.objects.create(numero=1, capacidad=4)
        self.categoria = Categoria.objects.create(nombre='Bebidas')
        self.producto = Producto.objects.create(
            categoria=self.categoria,
            nombre='Café',
            precio=Decimal('12.50'),
            disponible=True,
        )

    def _pedido_entregado(self, cantidad=1):
        pedido = Pedido.objects.create(
            mesa=self.mesa,
            mesero=self.mesero,
            estado=Pedido.Estado.ABIERTO,
        )
        DetallePedido.objects.create(
            pedido=pedido, producto=self.producto, cantidad=cantidad
        )
        pedido.estado = Pedido.Estado.ENTREGADO
        pedido.save()
        return pedido

    def _crear_pago(self, pedido, metodo=Pago.Metodo.EFECTIVO):
        return Pago.objects.create(
            pedido=pedido,
            cajero=self.cajero,
            metodo=metodo,
            monto=pedido.total,
            monto_recibido=pedido.total,
        )

    def _crear_cierre(self, **kwargs):
        valores = {
            'fecha_operacion': timezone.localdate(),
            'responsable': self.cajero,
            'monto_inicial': Decimal('0.00'),
            'efectivo_contado': Decimal('0.00'),
        }
        valores.update(kwargs)
        return CierreCaja.objects.create(**valores)

    def test_el_cierre_calcula_los_totales_por_metodo(self):
        self._crear_pago(self._pedido_entregado(), metodo=Pago.Metodo.EFECTIVO)
        self._crear_pago(self._pedido_entregado(), metodo=Pago.Metodo.TARJETA)
        self._crear_pago(
            self._pedido_entregado(cantidad=2), metodo=Pago.Metodo.YAPE
        )
        self._crear_pago(self._pedido_entregado(), metodo=Pago.Metodo.PLIN)
        cierre = self._crear_cierre()
        self.assertEqual(cierre.efectivo_ventas, Decimal('12.50'))
        self.assertEqual(cierre.total_tarjeta, Decimal('12.50'))
        self.assertEqual(cierre.total_yape, Decimal('25.00'))
        self.assertEqual(cierre.total_plin, Decimal('12.50'))
        self.assertEqual(cierre.total_ventas, Decimal('62.50'))
        self.assertEqual(cierre.cantidad_pagos, 4)

    def test_el_efectivo_esperado_incluye_el_monto_inicial(self):
        self._crear_pago(self._pedido_entregado())
        cierre = self._crear_cierre(
            monto_inicial=Decimal('50.00'),
            efectivo_contado=Decimal('62.50'),
        )
        self.assertEqual(cierre.efectivo_ventas, Decimal('12.50'))
        self.assertEqual(cierre.efectivo_esperado, Decimal('62.50'))
        self.assertEqual(cierre.diferencia, Decimal('0'))

    def test_la_diferencia_detecta_sobrante_y_faltante(self):
        self._crear_pago(self._pedido_entregado())
        sobrante = self._crear_cierre(efectivo_contado=Decimal('15.00'))
        self.assertEqual(sobrante.diferencia, Decimal('2.50'))
        faltante = self._crear_cierre(
            fecha_operacion=timezone.localdate() + timedelta(days=1),
            monto_inicial=Decimal('50.00'),
            efectivo_contado=Decimal('40.00'),
        )
        self.assertEqual(faltante.diferencia, Decimal('-10.00'))

    def test_solo_hay_un_cierre_por_fecha(self):
        self._crear_cierre()
        with self.assertRaises(ValidationError):
            self._crear_cierre()

    def test_no_se_admiten_montos_negativos(self):
        with self.assertRaises(ValidationError):
            self._crear_cierre(monto_inicial=Decimal('-1.00'))
        with self.assertRaises(ValidationError):
            self._crear_cierre(efectivo_contado=Decimal('-1.00'))

    def test_el_cierre_es_una_fotografia_historica(self):
        self._crear_pago(self._pedido_entregado())
        cierre = self._crear_cierre(
            monto_inicial=Decimal('50.00'),
            efectivo_contado=Decimal('62.50'),
        )
        self.assertEqual(cierre.total_ventas, Decimal('12.50'))
        cierre.monto_inicial = Decimal('100.00')
        cierre.save()
        cierre.refresh_from_db()
        self.assertEqual(cierre.total_ventas, Decimal('12.50'))
        self.assertEqual(cierre.efectivo_esperado, Decimal('62.50'))

    def test_no_se_puede_crear_un_pago_con_la_caja_cerrada(self):
        self._crear_cierre()
        pedido = self._pedido_entregado()
        with self.assertRaises(ValidationError):
            self._crear_pago(pedido)

    def test_mesero_y_cocina_no_pueden_cerrar_la_caja(self):
        self.client.login(username='mesero1', password='test12345')
        response = self.client.get(reverse('cerrar_caja'))
        self.assertEqual(response.status_code, 403)
        self.client.login(username='cocina1', password='test12345')
        response = self.client.get(reverse('cerrar_caja'))
        self.assertEqual(response.status_code, 403)

    def test_el_cajero_abre_el_formulario_de_cierre(self):
        self.client.login(username='cajero1', password='test12345')
        response = self.client.get(reverse('cerrar_caja'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Confirmar cierre de caja')
        self.assertContains(response, 'Resumen antes de cerrar')

    def test_el_administrador_cierra_la_caja(self):
        self.client.login(username='admin1', password='test12345')
        self._crear_pago(self._pedido_entregado())
        response = self.client.post(
            reverse('cerrar_caja'),
            {'monto_inicial': '0.00', 'efectivo_contado': '12.50'},
        )
        cierre = CierreCaja.objects.get(fecha_operacion=timezone.localdate())
        self.assertRedirects(response, reverse('detalle_cierre', args=[cierre.pk]))
        self.assertEqual(cierre.responsable, self.administrador)
        self.assertEqual(cierre.total_ventas, Decimal('12.50'))
        self.assertEqual(cierre.diferencia, Decimal('0'))

    def test_el_superusuario_cierra_la_caja(self):
        self.client.login(username='super1', password='test12345')
        response = self.client.post(
            reverse('cerrar_caja'),
            {'monto_inicial': '0.00', 'efectivo_contado': '0.00'},
        )
        cierre = CierreCaja.objects.get(fecha_operacion=timezone.localdate())
        self.assertRedirects(response, reverse('detalle_cierre', args=[cierre.pk]))
        self.assertEqual(cierre.responsable, self.superusuario)

    def test_no_se_admiten_valores_negativos_en_el_formulario(self):
        self.client.login(username='cajero1', password='test12345')
        response = self.client.post(
            reverse('cerrar_caja'),
            {'monto_inicial': '-1.00', 'efectivo_contado': '0.00'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CierreCaja.objects.count(), 0)

    def test_no_se_abre_el_formulario_si_ya_hay_un_cierre(self):
        self.client.login(username='cajero1', password='test12345')
        cierre = self._crear_cierre()
        response = self.client.get(reverse('cerrar_caja'))
        self.assertRedirects(response, reverse('detalle_cierre', args=[cierre.pk]))

    def test_se_bloquea_registrar_pagos_despues_del_cierre(self):
        self.client.login(username='cajero1', password='test12345')
        self._crear_cierre()
        pedido = self._pedido_entregado()
        response = self.client.post(
            reverse('registrar_pago', args=[pedido.pk]),
            {'metodo': Pago.Metodo.EFECTIVO, 'monto_recibido': '20.00'},
        )
        self.assertRedirects(response, reverse('panel_caja'))
        self.assertEqual(Pago.objects.count(), 0)

    def test_el_panel_indica_que_la_caja_esta_cerrada(self):
        self.client.login(username='cajero1', password='test12345')
        self._pedido_entregado()
        self._crear_cierre()
        response = self.client.get(reverse('panel_caja'))
        self.assertContains(response, 'Caja cerrada')
        self.assertNotContains(response, 'Cobrar')
        self.assertContains(response, 'Ver cierre del día')

    def test_el_panel_muestra_el_boton_de_cierre_cuando_esta_abierta(self):
        self.client.login(username='cajero1', password='test12345')
        response = self.client.get(reverse('panel_caja'))
        self.assertContains(response, 'Cerrar caja')

    def test_el_detalle_del_cierre_muestra_los_valores(self):
        self.client.login(username='cajero1', password='test12345')
        self._crear_pago(self._pedido_entregado())
        cierre = self._crear_cierre(
            monto_inicial=Decimal('50.00'),
            efectivo_contado=Decimal('62.50'),
        )
        response = self.client.get(reverse('detalle_cierre', args=[cierre.pk]))
        self.assertContains(response, 'Cierre de caja del')
        self.assertContains(response, 'S/ 12.50')
        self.assertContains(response, 'S/ 62.50')
        self.assertContains(response, 'Efectivo contado')
        self.assertContains(response, 'La caja cuadra perfectamente.')
        self.assertContains(response, 'Pagos incluidos en el cierre')
