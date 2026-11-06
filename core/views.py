from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.utils import timezone

from caja.models import CierreCaja, Pago
from compras.models import Compra
from inventario.models import Ingrediente
from mesas.models import Mesa
from pedidos.models import Pedido
from personal.models import PerfilEmpleado
from personal.permisos import tiene_roles
from reservas.models import Reserva

ROL = PerfilEmpleado.Rol

ROLES_MESAS = [ROL.ADMINISTRADOR, ROL.MESERO]
ROLES_PEDIDOS = [ROL.ADMINISTRADOR, ROL.MESERO]
ROLES_COCINA = [ROL.ADMINISTRADOR, ROL.COCINA]
ROLES_CAJA = [ROL.ADMINISTRADOR, ROL.CAJERO]
ROLES_INVENTARIO = [ROL.ADMINISTRADOR, ROL.COCINA]
ROLES_COMPRAS = [ROL.ADMINISTRADOR, ROL.COCINA]
ROLES_RESERVAS = [ROL.ADMINISTRADOR, ROL.MESERO]


def _datos_mesas():
    mesas = Mesa.objects.all()
    return {
        'mesas_activas': mesas.filter(activo=True).count(),
        'mesas_libres': mesas.filter(activo=True, estado=Mesa.Estado.LIBRE).count(),
        'mesas_ocupadas': mesas.filter(activo=True, estado=Mesa.Estado.OCUPADA).count(),
        'mesas_reservadas': mesas.filter(
            activo=True, estado=Mesa.Estado.RESERVADA
        ).count(),
        'mesas_fuera_servicio': mesas.filter(
            activo=True, estado=Mesa.Estado.FUERA_SERVICIO
        ).count(),
    }


def _datos_pedidos(user, es_administrador):
    pedidos = Pedido.objects.select_related('mesa', 'mesero').prefetch_related(
        'detalles'
    )
    if not es_administrador:
        pedidos = pedidos.filter(mesero=user)
    activos = pedidos.filter(estado__in=Pedido.ESTADOS_ACTIVOS)
    return {
        'pedidos_activos': activos.order_by('fecha_creacion')[:5],
        'pedidos_activos_cantidad': activos.count(),
        'cantidad_abiertos': activos.filter(estado=Pedido.Estado.ABIERTO).count(),
        'cantidad_en_preparacion': activos.filter(
            estado=Pedido.Estado.EN_PREPARACION
        ).count(),
        'cantidad_listos': activos.filter(estado=Pedido.Estado.LISTO).count(),
        'cantidad_entregados': activos.filter(estado=Pedido.Estado.ENTREGADO).count(),
        'pedidos_recientes': pedidos.order_by('-fecha_creacion', '-id')[:5],
    }


def _datos_cocina():
    pedidos = Pedido.objects.all()
    return {
        'cantidad_abiertos': pedidos.filter(estado=Pedido.Estado.ABIERTO).count(),
        'cantidad_en_preparacion': pedidos.filter(
            estado=Pedido.Estado.EN_PREPARACION
        ).count(),
        'cantidad_listos': pedidos.filter(estado=Pedido.Estado.LISTO).count(),
    }


def _datos_caja(hoy):
    pagos = Pago.objects.filter(fecha_pago__date=hoy)
    totales = pagos.aggregate(
        total=Coalesce(Sum('monto'), Decimal('0')),
        cantidad=Count('id'),
        efectivo=Coalesce(
            Sum('monto', filter=Q(metodo=Pago.Metodo.EFECTIVO)),
            Decimal('0'),
        ),
        tarjeta=Coalesce(
            Sum('monto', filter=Q(metodo=Pago.Metodo.TARJETA)),
            Decimal('0'),
        ),
        yape=Coalesce(
            Sum('monto', filter=Q(metodo=Pago.Metodo.YAPE)),
            Decimal('0'),
        ),
        plin=Coalesce(
            Sum('monto', filter=Q(metodo=Pago.Metodo.PLIN)),
            Decimal('0'),
        ),
    )
    total_vendido = totales['total']
    cantidad_pagos = totales['cantidad']
    ticket_promedio = (
        total_vendido / Decimal(cantidad_pagos) if cantidad_pagos else Decimal('0')
    )
    return {
        'ventas_hoy': total_vendido,
        'cantidad_pagos_hoy': cantidad_pagos,
        'total_efectivo': totales['efectivo'],
        'total_tarjeta': totales['tarjeta'],
        'total_yape': totales['yape'],
        'total_plin': totales['plin'],
        'ticket_promedio': ticket_promedio,
        'caja_cerrada_hoy': CierreCaja.objects.filter(fecha_operacion=hoy).exists(),
        'pedidos_pendientes_cobro': Pedido.objects.filter(
            estado=Pedido.Estado.ENTREGADO,
            pago__isnull=True,
        ).count(),
    }


def _datos_reservas(hoy):
    reservas_hoy = Reserva.objects.filter(fecha_hora__date=hoy)
    activas = reservas_hoy.exclude(
        estado__in=[
            Reserva.Estado.CANCELADA,
            Reserva.Estado.ATENDIDA,
            Reserva.Estado.NO_ASISTIO,
        ]
    )
    return {
        'cantidad_reservas_hoy': reservas_hoy.count(),
        'proximas_reservas': activas.filter(fecha_hora__gte=timezone.now())
        .select_related('cliente', 'mesa')
        .order_by('fecha_hora')[:5],
        'cantidad_confirmadas': reservas_hoy.filter(
            estado=Reserva.Estado.CONFIRMADA
        ).count(),
        'cantidad_pendientes': reservas_hoy.filter(
            estado=Reserva.Estado.PENDIENTE
        ).count(),
    }


def _datos_inventario():
    activos = Ingrediente.objects.filter(activo=True).select_related('unidad_medida')
    return {
        'cantidad_ingredientes': activos.count(),
        'bajo_stock': activos.filter(stock_actual__lte=F('stock_minimo')).count(),
        'sin_stock': activos.filter(stock_actual=0).count(),
        'ingredientes_criticos': activos.filter(
            stock_actual__lte=F('stock_minimo')
        ).order_by('stock_actual', 'nombre')[:5],
    }


def _datos_compras():
    borrador = Compra.objects.filter(estado=Compra.Estado.BORRADOR)
    return {
        'cantidad_compras_borrador': borrador.count(),
        'compras_pendientes': borrador.select_related('proveedor')
        .prefetch_related('detalles')
        .order_by('-fecha_creacion', '-id')[:5],
    }


@login_required
def dashboard(request):
    hoy = timezone.localdate()
    user = request.user
    es_administrador = tiene_roles(user, [ROL.ADMINISTRADOR])

    context = {'hoy': hoy}

    if tiene_roles(user, ROLES_MESAS):
        context.update(_datos_mesas())

    if tiene_roles(user, ROLES_PEDIDOS):
        context.update(_datos_pedidos(user, es_administrador))

    if tiene_roles(user, ROLES_COCINA) and not es_administrador:
        context.update(_datos_cocina())

    if tiene_roles(user, ROLES_RESERVAS):
        context.update(_datos_reservas(hoy))

    if tiene_roles(user, ROLES_CAJA):
        context.update(_datos_caja(hoy))

    if tiene_roles(user, ROLES_INVENTARIO):
        context.update(_datos_inventario())

    if tiene_roles(user, ROLES_COMPRAS):
        context.update(_datos_compras())

    return render(request, 'core/dashboard.html', context)
