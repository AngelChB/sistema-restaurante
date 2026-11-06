from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from caja.models import Pago
from catalogo.models import Categoria, Producto
from compras.models import Compra, DetalleCompra, Proveedor
from compras.services import recibir_compra
from inventario.models import (
    Ingrediente,
    MovimientoInventario,
    RecetaProducto,
    UnidadMedida,
)
from inventario.services import iniciar_preparacion_con_descuento
from mesas.models import Mesa
from pedidos.models import DetallePedido, Pedido
from personal.models import PerfilEmpleado
from reservas.models import Cliente, Reserva


def es_base_demo():
    nombre_base = str(connection.settings_dict['NAME'])
    return getattr(settings, 'DEMO_MODE', False) and nombre_base.endswith('_demo')


def _crear_usuarios():
    usuarios = {}
    for nombre, rol in [
        ('admin_demo', 'ADMINISTRADOR'),
        ('mesero_demo', 'MESERO'),
        ('cocina_demo', 'COCINA'),
        ('caja_demo', 'CAJERO'),
    ]:
        usuario = get_user_model().objects.create_user(
            username=nombre,
            password='DemoRestaurante123!',
            first_name=nombre.split('_')[0].capitalize(),
            is_staff=False,
        )
        PerfilEmpleado.objects.create(usuario=usuario, rol=rol)
        usuarios[rol] = usuario
    return usuarios


def _crear_mesas():
    mesas = [
        Mesa.objects.create(
            numero=indice,
            capacidad=4 if indice % 2 else 6,
            ubicacion='Salón' if indice <= 4 else 'Terraza',
        )
        for indice in range(1, 9)
    ]
    return mesas


def _crear_catalogo(usuarios):
    kg = UnidadMedida.objects.create(nombre='Kilogramo', abreviatura='kg')
    unidad = UnidadMedida.objects.create(nombre='Unidad', abreviatura='und')
    ingredientes = []
    for nombre, medida, stock, costo in [
        ('Arroz', kg, 25, '4.50'),
        ('Pollo', kg, 20, '12.00'),
        ('Papa', kg, 15, '3.50'),
        ('Limón', unidad, 40, '0.50'),
        ('Azúcar', kg, 8, '4.00'),
        ('Fruta de estación', kg, 10, '6.00'),
    ]:
        ingrediente = Ingrediente.objects.create(
            nombre=nombre, unidad_medida=medida, stock_minimo=5, costo_unitario=costo
        )
        MovimientoInventario.objects.create(
            ingrediente=ingrediente,
            tipo='ENTRADA',
            cantidad=stock,
            motivo='Carga inicial de demostración',
            usuario=usuarios['ADMINISTRADOR'],
        )
        ingredientes.append(ingrediente)
    platos = Categoria.objects.create(nombre='Platos de fondo')
    bebidas = Categoria.objects.create(nombre='Bebidas')
    productos = []
    for nombre, precio, categoria, indice, cantidad in [
        ('Arroz con pollo', '18.00', platos, 0, '0.20'),
        ('Pollo a la plancha', '22.00', platos, 1, '0.25'),
        ('Papa rellena', '10.00', platos, 2, '0.20'),
        ('Limonada', '8.00', bebidas, 3, '2'),
        ('Jugo de estación', '9.00', bebidas, 5, '0.20'),
        ('Refresco del día', '6.00', bebidas, 4, '0.03'),
    ]:
        producto = Producto.objects.create(
            nombre=nombre,
            precio=precio,
            categoria=categoria,
            descripcion='Producto de demostración',
        )
        RecetaProducto.objects.create(
            producto=producto,
            ingrediente=ingredientes[indice],
            cantidad=Decimal(cantidad),
        )
        productos.append(producto)
    return ingredientes, productos


def _crear_compra(usuarios, ingredientes):
    proveedor = Proveedor.objects.create(
        razon_social='Proveedor de demostración', contacto='Contacto ficticio'
    )
    compra = Compra.objects.create(
        proveedor=proveedor,
        usuario=usuarios['ADMINISTRADOR'],
        fecha_documento=timezone.localdate(),
        numero_documento='DEMO-001',
    )
    DetalleCompra.objects.create(
        compra=compra,
        ingrediente=ingredientes[0],
        cantidad=10,
        costo_unitario=Decimal('4.50'),
    )
    recibir_compra(compra.pk, usuarios['ADMINISTRADOR'])


def _crear_pedidos(usuarios, mesas, productos):
    estados = [
        'PAGADO',
        'PAGADO',
        'PAGADO',
        'PAGADO',
        'ENTREGADO',
        'LISTO',
        'EN_PREPARACION',
        'ABIERTO',
    ]
    for indice, estado in enumerate(estados):
        pedido = Pedido.objects.create(
            mesa=mesas[indice],
            mesero=usuarios['MESERO'],
            observacion='Pedido de demostración',
        )
        DetallePedido.objects.create(
            pedido=pedido, producto=productos[indice % 6], cantidad=2
        )
        DetallePedido.objects.create(
            pedido=pedido, producto=productos[3 if indice % 6 != 3 else 4], cantidad=1
        )
        if estado != 'ABIERTO':
            pedido = iniciar_preparacion_con_descuento(pedido.pk, usuarios['COCINA'])
        if estado in ['LISTO', 'ENTREGADO', 'PAGADO']:
            pedido.estado = 'LISTO'
            pedido.save()
        if estado in ['ENTREGADO', 'PAGADO']:
            pedido.estado = 'ENTREGADO'
            pedido.save()
        if estado == 'PAGADO':
            metodo = ['EFECTIVO', 'TARJETA', 'YAPE', 'PLIN'][indice]
            Pago.objects.create(
                pedido=pedido,
                cajero=usuarios['CAJERO'],
                metodo=metodo,
                monto=pedido.total,
                monto_recibido=pedido.total if metodo == 'EFECTIVO' else None,
                referencia='DEMO-' + str(indice + 1),
            )


def _crear_reservas(usuarios, mesas):
    for indice in range(2):
        cliente = Cliente.objects.create(
            nombres='Cliente demo ' + str(indice + 1), telefono='000000000'
        )
        Reserva.objects.create(
            cliente=cliente,
            mesa=mesas[indice],
            usuario=usuarios['MESERO'],
            fecha_hora=timezone.now() + timedelta(hours=2 + 24 * indice),
            cantidad_personas=3,
            estado='CONFIRMADA',
        )


class Command(BaseCommand):
    help = 'Carga una demostración ficticia en una base vacía terminada en _demo.'

    @transaction.atomic
    def handle(self, *args, **options):
        if not es_base_demo():
            raise CommandError(
                'Usa --settings=config.settings_demo y una base terminada en _demo.'
            )
        modelos = [
            get_user_model(),
            Mesa,
            Categoria,
            Producto,
            UnidadMedida,
            Ingrediente,
            Proveedor,
            Cliente,
        ]
        if any(modelo.objects.exists() for modelo in modelos):
            raise CommandError(
                'La base demo debe estar vacía. No se sobrescribió ningún registro.'
            )
        usuarios = _crear_usuarios()
        mesas = _crear_mesas()
        ingredientes, productos = _crear_catalogo(usuarios)
        _crear_compra(usuarios, ingredientes)
        _crear_pedidos(usuarios, mesas, productos)
        _crear_reservas(usuarios, mesas)
        self.stdout.write(
            self.style.SUCCESS(
                'Demo cargada: 8 mesas, 6 productos, 8 pedidos, 4 pagos y 2 reservas.'
            )
        )
        self.stdout.write(
            'Cuentas: admin_demo, mesero_demo, cocina_demo, caja_demo. Clave local: DemoRestaurante123!'
        )
