from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from pedidos.models import Pedido
from personal.models import PerfilEmpleado
from personal.permisos import rol_requerido
from reservas.models import Reserva

from .forms import MesaForm
from .models import Mesa


@rol_requerido(PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.MESERO)
def lista_mesas(request):
    mesas = Mesa.objects.all()

    pedidos_activos = {}
    for pedido in Pedido.objects.filter(
        estado__in=Pedido.ESTADOS_ACTIVOS
    ).select_related('mesa'):
        pedidos_activos.setdefault(pedido.mesa_id, pedido)

    reservas_activas = {}
    for reserva in Reserva.objects.filter(
        estado__in=Reserva.ESTADOS_ACTIVOS
    ).select_related('cliente', 'mesa').order_by('fecha_hora'):
        reservas_activas.setdefault(reserva.mesa_id, reserva)

    mesas_info = [
        {
            'mesa': mesa,
            'pedido': pedidos_activos.get(mesa.pk),
            'reserva': reservas_activas.get(mesa.pk),
        }
        for mesa in mesas
    ]

    resumen = {
        'activas': mesas.filter(activo=True).count(),
        'libres': mesas.filter(estado=Mesa.Estado.LIBRE).count(),
        'ocupadas': mesas.filter(estado=Mesa.Estado.OCUPADA).count(),
        'reservadas': mesas.filter(estado=Mesa.Estado.RESERVADA).count(),
    }

    return render(request, 'mesas/lista.html', {
        'mesas_info': mesas_info,
        'resumen': resumen,
    })


@rol_requerido(PerfilEmpleado.Rol.ADMINISTRADOR)
def crear_mesa(request):
    if request.method == 'POST':
        form = MesaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Mesa creada correctamente.')
            return redirect('lista_mesas')
    else:
        form = MesaForm()
    return render(
        request,
        'mesas/formulario.html',
        {'form': form, 'titulo': 'Nueva mesa'},
    )


@rol_requerido(PerfilEmpleado.Rol.ADMINISTRADOR)
def editar_mesa(request, pk):
    mesa = get_object_or_404(Mesa, pk=pk)
    if request.method == 'POST':
        form = MesaForm(request.POST, instance=mesa)
        if form.is_valid():
            form.save()
            messages.success(request, 'Mesa actualizada correctamente.')
            return redirect('lista_mesas')
    else:
        form = MesaForm(instance=mesa)
    return render(
        request,
        'mesas/formulario.html',
        {'form': form, 'titulo': 'Editar mesa'},
    )
