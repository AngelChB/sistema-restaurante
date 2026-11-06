from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from caja.models import Pago
from catalogo.models import Categoria, Producto
from mesas.models import Mesa
from pedidos.models import DetallePedido, Pedido
from personal.models import PerfilEmpleado

User = get_user_model()


def crear_usuario(username, rol=None):
    usuario = User.objects.create_user(username=username, password='test12345')
    if rol is not None:
        PerfilEmpleado.objects.create(usuario=usuario, rol=rol)
    return usuario


class ReporteVentasTests(TestCase):
    def setUp(self):
        self.administrador = crear_usuario('admin1', PerfilEmpleado.Rol.ADMINISTRADOR)
        self.cajero = crear_usuario('cajero1', PerfilEmpleado.Rol.CAJERO)
        self.mesero = crear_usuario('mesero1', PerfilEmpleado.Rol.MESERO)
        self.cocinero = crear_usuario('cocinero1', PerfilEmpleado.Rol.COCINA)
        self.sin_perfil = User.objects.create_user(
            username='anonimo', password='test12345'
        )
        self.superusuario = User.objects.create_superuser(
            username='super',
            email='super@restaurante.com',
            password='test12345',
        )

        self.categoria = Categoria.objects.create(nombre='Bebidas')
        self.producto1 = Producto.objects.create(
            categoria=self.categoria,
            nombre='Café',
            precio='12.50',
            disponible=True,
        )
        self.producto2 = Producto.objects.create(
            categoria=self.categoria,
            nombre='Jugo',
            precio='8.00',
            disponible=True,
        )
        self.mesa = Mesa.objects.create(numero=1, capacidad=4)

    def _login(self, usuario):
        self.client.login(username=usuario.username, password='test12345')

    def _crear_pago(
        self,
        mesero=None,
        cajero=None,
        metodo=Pago.Metodo.EFECTIVO,
        monto_recibido=None,
        producto=None,
        cantidad=1,
        fecha=None,
        referencia='',
    ):
        pedido = Pedido.objects.create(
            mesa=self.mesa,
            mesero=mesero or self.mesero,
            estado=Pedido.Estado.ABIERTO,
        )
        DetallePedido.objects.create(
            pedido=pedido,
            producto=producto or self.producto1,
            cantidad=cantidad,
        )
        pedido.estado = Pedido.Estado.ENTREGADO
        pedido.save()
        if metodo == Pago.Metodo.EFECTIVO and monto_recibido is None:
            monto_recibido = pedido.total
        pago = Pago.objects.create(
            pedido=pedido,
            cajero=cajero or self.cajero,
            metodo=metodo,
            monto=pedido.total,
            monto_recibido=monto_recibido,
            referencia=referencia,
        )
        if fecha is not None:
            Pago.objects.filter(pk=pago.pk).update(fecha_pago=fecha)
        return pago

    def test_visitante_no_autenticado_es_redirigido_al_login(self):
        response = self.client.get(reverse('reporte_ventas'))
        self.assertRedirects(
            response,
            f'{reverse("login")}?next={reverse("reporte_ventas")}',
        )

    def test_usuario_sin_perfil_recibe_403(self):
        self._login(self.sin_perfil)
        response = self.client.get(reverse('reporte_ventas'))
        self.assertEqual(response.status_code, 403)

    def test_mesero_recibe_403(self):
        self._login(self.mesero)
        response = self.client.get(reverse('reporte_ventas'))
        self.assertEqual(response.status_code, 403)

    def test_cocinero_recibe_403(self):
        self._login(self.cocinero)
        response = self.client.get(reverse('reporte_ventas'))
        self.assertEqual(response.status_code, 403)

    def test_cajero_puede_abrir_el_reporte(self):
        self._login(self.cajero)
        response = self.client.get(reverse('reporte_ventas'))
        self.assertEqual(response.status_code, 200)

    def test_administrador_puede_abrir_el_reporte(self):
        self._login(self.administrador)
        response = self.client.get(reverse('reporte_ventas'))
        self.assertEqual(response.status_code, 200)

    def test_superusuario_puede_abrir_el_reporte(self):
        self._login(self.superusuario)
        response = self.client.get(reverse('reporte_ventas'))
        self.assertEqual(response.status_code, 200)

    def test_sin_fechas_se_utiliza_el_dia_actual(self):
        self._login(self.cajero)
        response = self.client.get(reverse('reporte_ventas'))
        hoy = timezone.localdate()
        self.assertEqual(response.context['fecha_desde'], hoy)
        self.assertEqual(response.context['fecha_hasta'], hoy)

    def test_el_filtro_por_rango_de_fechas_funciona(self):
        pago_hoy = self._crear_pago(fecha=timezone.now())
        pago_viejo = self._crear_pago(fecha=timezone.now() - timedelta(days=10))
        hoy = timezone.localdate()
        self._login(self.cajero)
        response = self.client.get(
            reverse('reporte_ventas'),
            {
                'fecha_desde': (hoy - timedelta(days=3)).isoformat(),
                'fecha_hasta': hoy.isoformat(),
            },
        )
        self.assertEqual(response.context['cantidad_pagos'], 1)
        self.assertEqual(response.context['total_vendido'], pago_hoy.monto)
        ids_pagos = [p.id for p in response.context['pagos_recientes']]
        self.assertIn(pago_hoy.id, ids_pagos)
        self.assertNotIn(pago_viejo.id, ids_pagos)

    def test_el_total_vendido_se_calcula_correctamente(self):
        pago1 = self._crear_pago()
        pago2 = self._crear_pago(cantidad=2)
        self._login(self.cajero)
        response = self.client.get(reverse('reporte_ventas'))
        self.assertEqual(response.context['total_vendido'], pago1.monto + pago2.monto)
        self.assertEqual(response.context['cantidad_pagos'], 2)

    def test_los_totales_por_metodo_de_pago_se_calcularon_correctamente(self):
        efectivo = self._crear_pago(metodo=Pago.Metodo.EFECTIVO)
        tarjeta = self._crear_pago(
            metodo=Pago.Metodo.TARJETA,
            producto=self.producto2,
            cantidad=2,
        )
        yape = self._crear_pago(
            metodo=Pago.Metodo.YAPE,
            producto=self.producto2,
        )
        plin = self._crear_pago(
            metodo=Pago.Metodo.PLIN,
            producto=self.producto2,
            cantidad=3,
        )
        self._login(self.cajero)
        response = self.client.get(reverse('reporte_ventas'))
        self.assertEqual(response.context['total_efectivo'], efectivo.monto)
        self.assertEqual(response.context['total_tarjeta'], tarjeta.monto)
        self.assertEqual(response.context['total_yape'], yape.monto)
        self.assertEqual(response.context['total_plin'], plin.monto)

    def test_el_ticket_promedio_se_calcula_correctamente(self):
        self._crear_pago()
        self._crear_pago(cantidad=2)
        self._login(self.cajero)
        response = self.client.get(reverse('reporte_ventas'))
        self.assertEqual(response.context['ticket_promedio'], Decimal('18.75'))

    def test_los_productos_mas_vendidos_se_calcularon_correctamente(self):
        self._crear_pago(producto=self.producto1, cantidad=2)
        self._crear_pago(producto=self.producto1)
        self._crear_pago(producto=self.producto2, cantidad=3)
        self._login(self.cajero)
        response = self.client.get(reverse('reporte_ventas'))
        productos = response.context['productos_mas_vendidos']
        por_producto = {fila['producto__nombre']: fila for fila in productos}
        cafe = por_producto['Café']
        self.assertEqual(cafe['cantidad_total'], 3)
        self.assertEqual(cafe['ingreso'], Decimal('37.50'))
        jugo = por_producto['Jugo']
        self.assertEqual(jugo['cantidad_total'], 3)
        self.assertEqual(jugo['ingreso'], Decimal('24.00'))
        self.assertEqual(productos[0]['producto__nombre'], 'Café')

    def test_las_ventas_por_dia_se_agrupan_correctamente(self):
        hoy = timezone.localdate()
        self._crear_pago(fecha=timezone.now())
        self._crear_pago(
            producto=self.producto2,
            cantidad=2,
            fecha=timezone.now() - timedelta(days=1),
        )
        self._login(self.cajero)
        response = self.client.get(
            reverse('reporte_ventas'),
            {
                'fecha_desde': (hoy - timedelta(days=2)).isoformat(),
                'fecha_hasta': hoy.isoformat(),
            },
        )
        ventas = response.context['ventas_por_dia']
        self.assertEqual(len(ventas), 2)
        totales = {str(venta['fecha']): venta['total'] for venta in ventas}
        self.assertEqual(totales[str(hoy)], Decimal('12.50'))
        self.assertEqual(totales[str(hoy - timedelta(days=1))], Decimal('16.00'))

    def test_una_fecha_inicial_posterior_a_la_final_muestra_un_mensaje_de_error(self):
        hoy = timezone.localdate()
        self._login(self.cajero)
        response = self.client.get(
            reverse('reporte_ventas'),
            {
                'fecha_desde': hoy.isoformat(),
                'fecha_hasta': (hoy - timedelta(days=1)).isoformat(),
            },
        )
        mensajes = [str(m) for m in response.context['messages']]
        self.assertTrue(
            any('posterior a la fecha final' in mensaje for mensaje in mensajes)
        )
        self.assertEqual(response.context['fecha_desde'], hoy)
        self.assertEqual(response.context['fecha_hasta'], hoy)

    def test_la_exportacion_csv_responde_con_content_type_text_csv(self):
        self._crear_pago()
        self._login(self.cajero)
        response = self.client.get(reverse('exportar_ventas_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/csv'))
        nombre_archivo = response['Content-Disposition']
        self.assertIn('attachment', nombre_archivo)
        self.assertIn('ventas_', nombre_archivo)
        self.assertIn('.csv', nombre_archivo)

    def test_el_csv_contiene_encabezados_y_datos_de_pagos(self):
        pago = self._crear_pago()
        self._login(self.cajero)
        response = self.client.get(reverse('exportar_ventas_csv'))
        contenido = response.content.decode('utf-8-sig')
        self.assertIn('Número de pago', contenido)
        self.assertIn('Número de pedido', contenido)
        self.assertIn('Método', contenido)
        self.assertIn(str(pago.id), contenido)
        self.assertIn(str(pago.pedido.mesa.numero), contenido)
        self.assertIn(self.mesero.username, contenido)

    def test_el_enlace_reportes_se_muestra_solamente_a_los_roles_permitidos(self):
        enlace = reverse('reporte_ventas')
        casos = [
            (self.administrador, True),
            (self.cajero, True),
            (self.superusuario, True),
            (self.mesero, False),
            (self.cocinero, False),
            (self.sin_perfil, False),
        ]
        for usuario, debe_mostrarse in casos:
            with self.subTest(usuario=usuario.username):
                self._login(usuario)
                response = self.client.get(reverse('dashboard'))
                if debe_mostrarse:
                    self.assertContains(response, enlace)
                else:
                    self.assertNotContains(response, enlace)
