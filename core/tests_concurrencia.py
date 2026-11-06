from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier, Event
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, connections, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from caja.models import CierreCaja, Pago
from catalogo.models import Categoria, Producto
from mesas.models import Mesa
from pedidos.models import DetallePedido, Pedido
from reservas.models import Cliente, Reserva


@skipUnless(connection.vendor == 'postgresql', 'Requiere bloqueos de PostgreSQL')
class ConcurrenciaPostgresTests(TransactionTestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(username='concurrencia')
        self.mesa = Mesa.objects.create(numero=1, capacidad=4)
        categoria = Categoria.objects.create(nombre='Menu')
        self.producto = Producto.objects.create(
            categoria=categoria, nombre='Plato', precio=10
        )
        self.cliente = Cliente.objects.create(nombres='Cliente', telefono='999999999')

    def ejecutar(self, operacion):
        connections.close_all()
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout = '5s'")
                operacion()
            return 'ok'
        except ValidationError:
            return 'rechazado'
        finally:
            connections.close_all()

    def competir(self, a, b):
        barrera = Barrier(2)

        def tarea(op):
            barrera.wait(timeout=10)
            return self.ejecutar(op)

        with ThreadPoolExecutor(max_workers=2) as pool:
            fa = pool.submit(tarea, a)
            fb = pool.submit(tarea, b)
            return [fa.result(timeout=15), fb.result(timeout=15)]

    def nuevo_pedido(self):
        Pedido.objects.create(mesa_id=self.mesa.pk, mesero_id=self.usuario.pk)

    def nueva_reserva(self):
        Reserva.objects.create(
            mesa_id=self.mesa.pk,
            cliente_id=self.cliente.pk,
            usuario_id=self.usuario.pk,
            cantidad_personas=2,
            fecha_hora=timezone.now() + timedelta(days=1),
        )

    def pedido_entregado(self):
        pedido = Pedido.objects.create(
            mesa=self.mesa, mesero=self.usuario, estado=Pedido.Estado.ABIERTO
        )
        DetallePedido.objects.create(pedido=pedido, producto=self.producto, cantidad=1)
        pedido.estado = Pedido.Estado.ENTREGADO
        pedido.save()
        self.pedido_id = pedido.pk

    def cobrar(self):
        Pago.objects.create(
            pedido_id=self.pedido_id,
            cajero_id=self.usuario.pk,
            metodo='EFECTIVO',
            monto=Decimal('10'),
            monto_recibido=Decimal('10'),
        )

    def cerrar(self):
        CierreCaja.objects.create(
            responsable_id=self.usuario.pk, monto_inicial=0, efectivo_contado=10
        )

    def test_dos_pedidos_simultaneos_solo_crean_uno(self):
        self.assertCountEqual(
            self.competir(self.nuevo_pedido, self.nuevo_pedido), ['ok', 'rechazado']
        )
        self.assertEqual(Pedido.objects.count(), 1)

    def test_dos_reservas_simultaneas_no_se_solapan(self):
        self.assertCountEqual(
            self.competir(self.nueva_reserva, self.nueva_reserva), ['ok', 'rechazado']
        )
        self.assertEqual(Reserva.objects.count(), 1)

    def test_dos_cobros_simultaneos_solo_crean_uno(self):
        self.pedido_entregado()
        self.assertCountEqual(
            self.competir(self.cobrar, self.cobrar), ['ok', 'rechazado']
        )
        self.assertEqual(Pago.objects.count(), 1)

    def test_dos_cierres_simultaneos_devuelven_rechazo_controlado(self):
        self.assertCountEqual(
            self.competir(self.cerrar, self.cerrar), ['ok', 'rechazado']
        )
        self.assertEqual(CierreCaja.objects.count(), 1)

    def ordenar_operaciones(self, primera, segunda):
        guardada = Event()
        liberar = Event()
        iniciada = Event()

        def mantener():
            def op():
                primera()
                guardada.set()
                if not liberar.wait(timeout=10):
                    raise RuntimeError('No se liberó la transacción de prueba')

            return self.ejecutar(op)

        def esperar():
            iniciada.set()
            return self.ejecutar(segunda)

        with ThreadPoolExecutor(max_workers=2) as pool:
            fa = pool.submit(mantener)
            try:
                self.assertTrue(guardada.wait(timeout=10))
                fb = pool.submit(esperar)
                self.assertTrue(iniciada.wait(timeout=10))
                # La segunda operación debe esperar hasta confirmar la primera.
                from concurrent.futures import TimeoutError

                with self.assertRaises(TimeoutError):
                    fb.result(timeout=0.25)
            finally:
                liberar.set()
            return fa.result(timeout=15), fb.result(timeout=15)

    def test_cierre_espera_cobro_y_lo_incluye_en_totales(self):
        self.pedido_entregado()
        self.assertEqual(
            self.ordenar_operaciones(self.cobrar, self.cerrar), ('ok', 'ok')
        )
        cierre = CierreCaja.objects.get()
        self.assertEqual(cierre.total_ventas, Decimal('10'))
        self.assertEqual(cierre.cantidad_pagos, 1)

    def test_cobro_espera_cierre_y_se_rechaza(self):
        self.pedido_entregado()
        self.assertEqual(
            self.ordenar_operaciones(self.cerrar, self.cobrar), ('ok', 'rechazado')
        )
        self.assertFalse(Pago.objects.exists())
        self.assertEqual(CierreCaja.objects.get().cantidad_pagos, 0)
