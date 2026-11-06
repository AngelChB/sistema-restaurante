from django.db import transaction
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from pedidos.models import Pedido
from personal.models import PerfilEmpleado
from personal.permisos import rol_requerido, tiene_roles


@rol_requerido(PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.MESERO)
def panel_sala(request):
    pedidos = Pedido.objects.select_related('mesa', 'mesero').prefetch_related(
        'detalles__producto'
    ).filter(
        estado=Pedido.Estado.LISTO
    ).order_by('fecha_creacion')
    if not tiene_roles(request.user, [PerfilEmpleado.Rol.ADMINISTRADOR]):
        pedidos = pedidos.filter(mesero=request.user)
    return render(request, 'sala/panel.html', {
        'pedidos': pedidos,
        'hora_actual': timezone.now(),
    })


@rol_requerido(PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.MESERO)
@require_POST
@transaction.atomic
def marcar_pedido_entregado(request, pk):
    pedido = get_object_or_404(Pedido.objects.select_for_update(), pk=pk)
    if (
        not tiene_roles(request.user, [PerfilEmpleado.Rol.ADMINISTRADOR])
        and pedido.mesero != request.user
    ):
        raise PermissionDenied
    if pedido.estado != Pedido.Estado.LISTO:
        messages.error(
            request,
            'Solo se pueden entregar pedidos en estado "Listo".',
        )
        return redirect('panel_sala')
    pedido.estado = Pedido.Estado.ENTREGADO
    try:
        pedido.save()
    except ValidationError as error:
        mensaje = error.messages[0] if error.messages else 'No se pudo marcar el pedido como entregado.'
        messages.error(request, mensaje)
    else:
        messages.success(request, 'Pedido marcado como entregado correctamente.')
    return redirect('panel_sala')
