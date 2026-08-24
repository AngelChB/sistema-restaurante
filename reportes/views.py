import csv
from datetime import datetime, time as dt_time
from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from caja.models import Pago
from pedidos.models import DetallePedido
from personal.models import PerfilEmpleado
from personal.permisos import rol_requerido

ROLES_REPORTES = [
    PerfilEmpleado.Rol.ADMINISTRADOR,
    PerfilEmpleado.Rol.CAJERO,
]

MAX_DIAS_RANGO = 366

COLUMNAS_CSV = [
    'Número de pago',
    'Fecha',
    'Número de pedido',
    'Mesa',
    'Mesero',
    'Cajero',
    'Método',
    'Monto',
    'Monto recibido',
    'Vuelto',
    'Referencia',
]


def _parsear_fecha(texto):
    if not texto:
        return None
    try:
        return datetime.strptime(texto, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _rango_fechas(request):
    hoy = timezone.localdate()
    texto_desde = request.GET.get('fecha_desde')
    texto_hasta = request.GET.get('fecha_hasta')
    fecha_desde = _parsear_fecha(texto_desde)
    fecha_hasta = _parsear_fecha(texto_hasta)

    if (texto_desde or texto_hasta) and (
        fecha_desde is None or fecha_hasta is None
    ):
        messages.error(
            request,
            'Las fechas ingresadas no son válidas, se usará la fecha actual.',
        )

    if fecha_desde is None or fecha_hasta is None:
        fecha_desde = fecha_hasta = hoy

    if fecha_desde > fecha_hasta:
        messages.error(
            request,
            'La fecha inicial no puede ser posterior a la fecha final.',
        )
        fecha_desde = fecha_hasta = hoy

    if (fecha_hasta - fecha_desde).days > MAX_DIAS_RANGO:
        messages.error(
            request,
            'El rango de fechas no puede superar los 366 días.',
        )
        fecha_desde = fecha_hasta = hoy

    return fecha_desde, fecha_hasta


def _extremos_naive(fecha_desde, fecha_hasta):
    zona = timezone.get_current_timezone()
    inicio = datetime.combine(fecha_desde, dt_time.min, tzinfo=zona)
    fin = datetime.combine(fecha_hasta, dt_time.max, tzinfo=zona)
    return inicio, fin


def _consultar_pagos(fecha_desde, fecha_hasta):
    inicio, fin = _extremos_naive(fecha_desde, fecha_hasta)
    return Pago.objects.filter(
        fecha_pago__range=(inicio, fin),
    ).select_related('pedido', 'pedido__mesa', 'pedido__mesero', 'cajero')


def _productos_mas_vendidos(inicio, fin):
    return (
        DetallePedido.objects.filter(
            pedido__pago__fecha_pago__range=(inicio, fin),
        )
        .values(
            'producto_id',
            'producto__nombre',
            'producto__categoria__nombre',
        )
        .annotate(
            cantidad_total=Sum('cantidad'),
            ingreso=Sum(
                ExpressionWrapper(
                    F('cantidad') * F('precio_unitario'),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            ),
        )
        .order_by('-cantidad_total', '-ingreso')
    )[:5]


def _ventas_por_dia(pagos):
    filas = (
        pagos.values('fecha_pago__date')
        .annotate(
            cantidad=Count('id'),
            total=Sum('monto'),
        )
        .order_by('fecha_pago__date')
    )
    return [
        {
            'fecha': fila['fecha_pago__date'],
            'cantidad': fila['cantidad'],
            'total': fila['total'],
        }
        for fila in filas
    ]


@rol_requerido(*ROLES_REPORTES)
def reporte_ventas(request):
    fecha_desde, fecha_hasta = _rango_fechas(request)
    inicio, fin = _extremos_naive(fecha_desde, fecha_hasta)
    pagos = _consultar_pagos(fecha_desde, fecha_hasta)

    totales = pagos.aggregate(
        total_vendido=Sum('monto'),
        cantidad_pagos=Count('id'),
        total_efectivo=Sum('monto', filter=Q(metodo=Pago.Metodo.EFECTIVO)),
        total_tarjeta=Sum('monto', filter=Q(metodo=Pago.Metodo.TARJETA)),
        total_yape=Sum('monto', filter=Q(metodo=Pago.Metodo.YAPE)),
        total_plin=Sum('monto', filter=Q(metodo=Pago.Metodo.PLIN)),
    )

    total_vendido = totales['total_vendido'] or Decimal('0')
    cantidad_pagos = totales['cantidad_pagos'] or 0
    ticket_promedio = (
        total_vendido / Decimal(cantidad_pagos) if cantidad_pagos else Decimal('0')
    )

    return render(request, 'reportes/ventas.html', {
        'total_vendido': total_vendido,
        'cantidad_pagos': cantidad_pagos,
        'ticket_promedio': ticket_promedio,
        'total_efectivo': totales['total_efectivo'] or Decimal('0'),
        'total_tarjeta': totales['total_tarjeta'] or Decimal('0'),
        'total_yape': totales['total_yape'] or Decimal('0'),
        'total_plin': totales['total_plin'] or Decimal('0'),
        'pagos_recientes': pagos[:10],
        'productos_mas_vendidos': _productos_mas_vendidos(inicio, fin),
        'ventas_por_dia': _ventas_por_dia(pagos),
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
    })


@rol_requerido(*ROLES_REPORTES)
def exportar_ventas_csv(request):
    fecha_desde, fecha_hasta = _rango_fechas(request)
    pagos = _consultar_pagos(fecha_desde, fecha_hasta)

    respuesta = HttpResponse(content_type='text/csv; charset=utf-8')
    respuesta['Content-Disposition'] = (
        f'attachment; filename="ventas_{fecha_desde:%Y-%m-%d}_a_{fecha_hasta:%Y-%m-%d}.csv"'
    )
    respuesta.write('\ufeff')

    escritor = csv.writer(respuesta)
    escritor.writerow(COLUMNAS_CSV)

    for pago in pagos:
        escritor.writerow([
            pago.id,
            pago.fecha_pago.strftime('%d/%m/%Y %H:%M'),
            pago.pedido_id,
            pago.pedido.mesa.numero,
            pago.pedido.mesero.get_full_name() or pago.pedido.mesero.username,
            pago.cajero.get_full_name() or pago.cajero.username,
            pago.get_metodo_display(),
            f'{pago.monto:.2f}',
            f'{pago.monto_recibido:.2f}' if pago.monto_recibido is not None else '',
            f'{pago.vuelto:.2f}',
            pago.referencia,
        ])

    return respuesta
