from core.paginacion import paginar
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from pedidos.models import Pedido
from personal.models import PerfilEmpleado
from personal.permisos import rol_requerido

from .forms import CierreCajaForm, PagoForm
from .models import CierreCaja, Pago

ROLES_CAJA = [PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.CAJERO]


@rol_requerido(*ROLES_CAJA)
def panel_caja(request):
    hoy = timezone.localdate()
    cierre_del_dia = CierreCaja.objects.filter(
        fecha_operacion=hoy,
    ).select_related('responsable').first()
    pagos = Pago.objects.filter(
        fecha_pago__date=hoy,
    ).select_related('pedido__mesa', 'cajero')

    total_dia = pagos.aggregate(total=Sum('monto'))['total'] or Decimal('0')
    totales_por_metodo = [
        (Pago.Metodo.EFECTIVO, total_dia_metodo(pagos, Pago.Metodo.EFECTIVO)),
        (Pago.Metodo.TARJETA, total_dia_metodo(pagos, Pago.Metodo.TARJETA)),
        (Pago.Metodo.YAPE, total_dia_metodo(pagos, Pago.Metodo.YAPE)),
        (Pago.Metodo.PLIN, total_dia_metodo(pagos, Pago.Metodo.PLIN)),
    ]
    pendientes = Pedido.objects.filter(
        estado=Pedido.Estado.ENTREGADO,
        pago__isnull=True,
    ).select_related('mesa', 'mesero').order_by('fecha_creacion')

    return render(request, 'caja/panel.html', {
        'hoy': hoy,
        'cierre_del_dia': cierre_del_dia,
        'pagos': paginar(request, pagos, 'pagina_pagos'),
        'total_dia': total_dia,
        'cantidad_pagos': pagos.count(),
        'totales_por_metodo': totales_por_metodo,
        'pendientes': paginar(request, pendientes, 'pagina_pendientes'),
    })


def total_dia_metodo(pagos, metodo):
    total = pagos.filter(metodo=metodo).aggregate(total=Sum('monto'))['total']
    return total or Decimal('0')


def caja_cerrada_hoy():
    return CierreCaja.objects.filter(
        fecha_operacion=timezone.localdate()
    ).exists()


@rol_requerido(*ROLES_CAJA)
def registrar_pago(request, pedido_id):
    if caja_cerrada_hoy():
        messages.error(request, 'La caja del día ya fue cerrada.')
        return redirect('panel_caja')
    pedido = get_object_or_404(
        Pedido.objects.select_related('mesa', 'mesero').prefetch_related(
            'detalles__producto'
        ),
        pk=pedido_id,
    )
    if hasattr(pedido, 'pago'):
        messages.error(request, 'Este pedido ya tiene un pago registrado.')
        return redirect('detalle_pago', pk=pedido.pago.pk)
    if pedido.estado != Pedido.Estado.ENTREGADO:
        messages.error(request, 'Solo se pueden pagar pedidos entregados.')
        return redirect('panel_caja')

    pago = Pago(pedido=pedido, cajero=request.user, monto=pedido.total)
    if request.method == 'POST':
        form = PagoForm(request.POST, instance=pago)
        if form.is_valid():
            try:
                pago = form.save()
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Pago registrado correctamente.')
                return redirect('detalle_pago', pk=pago.pk)
    else:
        form = PagoForm(instance=pago)

    return render(request, 'caja/formulario_pago.html', {
        'form': form,
        'pedido': pedido,
    })


@rol_requerido(*ROLES_CAJA)
def detalle_pago(request, pk):
    pago = get_object_or_404(
        Pago.objects.select_related(
            'pedido__mesa', 'pedido__mesero', 'cajero'
        ).prefetch_related('pedido__detalles__producto'),
        pk=pk,
    )
    return render(request, 'caja/detalle_pago.html', {'pago': pago})


@rol_requerido(*ROLES_CAJA)
def cerrar_caja(request):
    hoy = timezone.localdate()
    cierre = CierreCaja.objects.filter(fecha_operacion=hoy).first()
    if cierre is not None:
        return redirect('detalle_cierre', pk=cierre.pk)

    pagos = Pago.objects.filter(fecha_pago__date=hoy)
    resumen = {
        'cantidad_pagos': pagos.count(),
        'efectivo': total_dia_metodo(pagos, Pago.Metodo.EFECTIVO),
        'tarjeta': total_dia_metodo(pagos, Pago.Metodo.TARJETA),
        'yape': total_dia_metodo(pagos, Pago.Metodo.YAPE),
        'plin': total_dia_metodo(pagos, Pago.Metodo.PLIN),
        'total': pagos.aggregate(total=Sum('monto'))['total'] or Decimal('0'),
    }

    cierre = CierreCaja(fecha_operacion=hoy, responsable=request.user)
    if request.method == 'POST':
        form = CierreCajaForm(request.POST, instance=cierre)
        if form.is_valid():
            try:
                with transaction.atomic():
                    cierre = form.save()
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Cierre de caja registrado.')
                return redirect('detalle_cierre', pk=cierre.pk)
    else:
        form = CierreCajaForm(instance=cierre)

    return render(request, 'caja/cerrar_caja.html', {
        'form': form,
        'hoy': hoy,
        'resumen': resumen,
    })


@rol_requerido(*ROLES_CAJA)
def detalle_cierre(request, pk):
    cierre = get_object_or_404(
        CierreCaja.objects.select_related('responsable'),
        pk=pk,
    )
    pagos = cierre.pagos_del_dia()
    return render(request, 'caja/detalle_cierre.html', {
        'cierre': cierre,
        'pagos': pagos,
    })
