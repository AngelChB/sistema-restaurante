from core.paginacion import paginar
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from inventario.services import iniciar_preparacion_con_descuento
from mesas.models import Mesa
from personal.models import PerfilEmpleado
from personal.permisos import rol_requerido, tiene_roles

from .forms import DetallePedidoFormSet, PedidoForm
from .models import Pedido

ROLES_PEDIDOS = [PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.MESERO]

TRANSICIONES = {
    Pedido.Estado.ABIERTO: [Pedido.Estado.EN_PREPARACION, Pedido.Estado.CANCELADO],
    Pedido.Estado.EN_PREPARACION: [Pedido.Estado.LISTO, Pedido.Estado.CANCELADO],
    Pedido.Estado.LISTO: [Pedido.Estado.ENTREGADO, Pedido.Estado.CANCELADO],
    Pedido.Estado.ENTREGADO: [],
    Pedido.Estado.PAGADO: [],
    Pedido.Estado.CANCELADO: [],
}


@rol_requerido(*ROLES_PEDIDOS)
def lista_pedidos(request):
    estado = request.GET.get('estado', '')
    buscar = request.GET.get('buscar', '').strip()

    pedidos = Pedido.objects.select_related('mesa', 'mesero').prefetch_related(
        'detalles'
    )
    if not tiene_roles(request.user, [PerfilEmpleado.Rol.ADMINISTRADOR]):
        pedidos = pedidos.filter(mesero=request.user)
    if estado in [c[0] for c in Pedido.Estado.choices]:
        pedidos = pedidos.filter(estado=estado)
    if buscar:
        if buscar.isdigit():
            pedidos = pedidos.filter(Q(pk=buscar) | Q(mesa__numero=buscar))
        else:
            pedidos = pedidos.filter(mesa__numero__icontains=buscar)

    return render(request, 'pedidos/lista.html', {
        'pedidos': paginar(request, pedidos),
        'estado': estado,
        'buscar': buscar,
        'estados': Pedido.Estado.choices,
    })


@rol_requerido(*ROLES_PEDIDOS)
def crear_pedido(request):
    initial = {}
    mesa_id = request.GET.get('mesa')
    if mesa_id and mesa_id.isdigit():
        mesa = Mesa.objects.filter(pk=mesa_id, activo=True).first()
        if mesa and mesa.estado == Mesa.Estado.LIBRE:
            initial['mesa'] = mesa.pk

    if request.method == 'POST':
        form = PedidoForm(request.POST)
        formset = DetallePedidoFormSet(
            request.POST, instance=Pedido(), prefix='detalles'
        )
        if form.is_valid() and formset.is_valid():
            pedido = form.save(commit=False)
            pedido.mesero = request.user
            pedido.estado = Pedido.Estado.ABIERTO
            try:
                with transaction.atomic():
                    pedido.save()
                    formset.instance = pedido
                    formset.save()
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Pedido creado correctamente.')
                return redirect('detalle_pedido', pk=pedido.pk)
    else:
        form = PedidoForm(initial=initial)
        formset = DetallePedidoFormSet(instance=Pedido(), prefix='detalles')

    return render(request, 'pedidos/formulario.html', {
        'form': form,
        'formset': formset,
        'titulo': 'Nuevo pedido',
    })


@rol_requerido(*ROLES_PEDIDOS)
def detalle_pedido(request, pk):
    pedido = get_object_or_404(
        Pedido.objects.select_related('mesa', 'mesero').prefetch_related(
            'detalles__producto'
        ),
        pk=pk,
    )
    if (
        not tiene_roles(request.user, [PerfilEmpleado.Rol.ADMINISTRADOR])
        and pedido.mesero != request.user
    ):
        raise PermissionDenied
    return render(request, 'pedidos/detalle.html', {
        'pedido': pedido,
        'estados_siguientes': TRANSICIONES.get(pedido.estado, []),
    })


@rol_requerido(*ROLES_PEDIDOS)
@require_POST
@transaction.atomic
def cambiar_estado_pedido(request, pk):
    pedido = get_object_or_404(Pedido.objects.select_for_update(), pk=pk)
    if (
        not tiene_roles(request.user, [PerfilEmpleado.Rol.ADMINISTRADOR])
        and pedido.mesero != request.user
    ):
        raise PermissionDenied
    nuevo_estado = request.POST.get('estado')
    if nuevo_estado not in TRANSICIONES.get(pedido.estado, []):
        messages.error(
            request,
            'No se puede cambiar el pedido a ese estado.',
        )
        return redirect('detalle_pedido', pk=pedido.pk)
    try:
        if nuevo_estado == Pedido.Estado.EN_PREPARACION:
            iniciar_preparacion_con_descuento(pedido.pk, request.user)
        else:
            pedido.estado = nuevo_estado
            pedido.save()
    except ValidationError as error:
        mensaje = error.messages[0] if error.messages else 'No se pudo cambiar el estado.'
        messages.error(request, mensaje)
    else:
        messages.success(request, 'Estado del pedido actualizado correctamente.')
    return redirect('detalle_pedido', pk=pedido.pk)
