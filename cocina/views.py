from django.db import transaction
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from inventario.services import iniciar_preparacion_con_descuento
from pedidos.models import Pedido
from personal.models import PerfilEmpleado
from personal.permisos import rol_requerido

TRANSICIONES = {
    Pedido.Estado.ABIERTO: Pedido.Estado.EN_PREPARACION,
    Pedido.Estado.EN_PREPARACION: Pedido.Estado.LISTO,
}


@rol_requerido(PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.COCINA)
def panel_cocina(request):
    pedidos = Pedido.objects.select_related('mesa', 'mesero').prefetch_related(
        'detalles__producto'
    )
    pedidos_abiertos = pedidos.filter(
        estado=Pedido.Estado.ABIERTO
    ).order_by('fecha_creacion')
    pedidos_en_preparacion = pedidos.filter(
        estado=Pedido.Estado.EN_PREPARACION
    ).order_by('fecha_creacion')
    pedidos_listos = pedidos.filter(
        estado=Pedido.Estado.LISTO
    ).order_by('fecha_creacion')

    return render(request, 'cocina/panel.html', {
        'pedidos_abiertos': pedidos_abiertos,
        'pedidos_en_preparacion': pedidos_en_preparacion,
        'pedidos_listos': pedidos_listos,
        'hora_actual': timezone.now(),
    })


@rol_requerido(PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.COCINA)
@require_POST
@transaction.atomic
def actualizar_estado_cocina(request, pk):
    pedido = get_object_or_404(Pedido.objects.select_for_update(), pk=pk)
    siguiente = TRANSICIONES.get(pedido.estado)
    if siguiente is None:
        messages.error(
            request,
            'No se puede actualizar el estado de este pedido desde cocina.',
        )
        return redirect('panel_cocina')

    if pedido.estado == Pedido.Estado.ABIERTO:
        try:
            iniciar_preparacion_con_descuento(pedido.pk, request.user)
        except ValidationError as error:
            mensaje = (
                error.messages[0]
                if error.messages
                else 'No se pudo iniciar la preparación.'
            )
            messages.error(request, mensaje)
        else:
            messages.success(
                request, 'Preparación iniciada e ingredientes descontados.'
            )
    else:
        pedido.estado = Pedido.Estado.LISTO
        try:
            pedido.save()
        except ValidationError as error:
            mensaje = (
                error.messages[0]
                if error.messages
                else 'No se pudo actualizar el estado.'
            )
            messages.error(request, mensaje)
        else:
            messages.success(
                request, 'Estado del pedido actualizado correctamente.'
            )
    return redirect('panel_cocina')
