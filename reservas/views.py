from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from personal.models import PerfilEmpleado
from personal.permisos import rol_requerido

from .forms import ClienteForm, ReservaForm
from .models import Cliente, Reserva

ROLES_RESERVAS_VER = [PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.MESERO]
ROLES_RESERVAS_GESTIONAR = [PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.MESERO]


@rol_requerido(*ROLES_RESERVAS_VER)
def lista_clientes(request):
    buscar = request.GET.get('buscar', '').strip()
    estado = request.GET.get('estado', '')

    clientes = Cliente.objects.annotate(
        cantidad_reservas=Count('reservas')
    )
    if buscar:
        clientes = clientes.filter(
            Q(nombres__icontains=buscar)
            | Q(apellidos__icontains=buscar)
            | Q(documento__icontains=buscar)
            | Q(telefono__icontains=buscar)
        )
    if estado == 'activos':
        clientes = clientes.filter(activo=True)
    elif estado == 'inactivos':
        clientes = clientes.filter(activo=False)

    return render(request, 'reservas/lista_clientes.html', {
        'clientes': clientes,
        'buscar': buscar,
        'estado': estado,
    })


@rol_requerido(*ROLES_RESERVAS_GESTIONAR)
def crear_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente creado correctamente.')
            return redirect('lista_clientes')
    else:
        form = ClienteForm()
    return render(request, 'reservas/formulario_cliente.html', {
        'form': form,
        'titulo': 'Nuevo cliente',
    })


@rol_requerido(PerfilEmpleado.Rol.ADMINISTRADOR)
def editar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente actualizado correctamente.')
            return redirect('lista_clientes')
    else:
        form = ClienteForm(instance=cliente)
    return render(request, 'reservas/formulario_cliente.html', {
        'form': form,
        'titulo': 'Editar cliente',
    })


@rol_requerido(*ROLES_RESERVAS_VER)
def lista_reservas(request):
    estado = request.GET.get('estado', '')
    fecha = request.GET.get('fecha', '')
    buscar = request.GET.get('buscar', '').strip()

    reservas = Reserva.objects.select_related('cliente', 'mesa', 'usuario')
    if estado in [c[0] for c in Reserva.Estado.choices]:
        reservas = reservas.filter(estado=estado)
    if fecha:
        reservas = reservas.filter(fecha_hora__date=fecha)
    if buscar:
        reservas = reservas.filter(
            Q(cliente__nombres__icontains=buscar)
            | Q(cliente__apellidos__icontains=buscar)
            | Q(cliente__telefono__icontains=buscar)
            | Q(mesa__numero__icontains=buscar)
        )

    return render(request, 'reservas/lista_reservas.html', {
        'reservas': reservas,
        'estado': estado,
        'fecha': fecha,
        'buscar': buscar,
        'estados': Reserva.Estado.choices,
    })


@rol_requerido(*ROLES_RESERVAS_GESTIONAR)
def crear_reserva(request):
    if request.method == 'POST':
        form = ReservaForm(request.POST)
        if form.is_valid():
            reserva = form.save(commit=False)
            reserva.usuario = request.user
            try:
                reserva.save()
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Reserva creada correctamente.')
                return redirect('detalle_reserva', pk=reserva.pk)
    else:
        form = ReservaForm()
    return render(request, 'reservas/formulario_reserva.html', {
        'form': form,
        'titulo': 'Nueva reserva',
    })


@rol_requerido(*ROLES_RESERVAS_GESTIONAR)
def editar_reserva(request, pk):
    reserva = get_object_or_404(Reserva, pk=pk)
    if reserva.estado not in Reserva.ESTADOS_ACTIVOS:
        messages.error(
            request,
            'Solo se pueden editar reservas pendientes o confirmadas.',
        )
        return redirect('detalle_reserva', pk=reserva.pk)

    if request.method == 'POST':
        form = ReservaForm(request.POST, instance=reserva)
        if form.is_valid():
            try:
                form.save()
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Reserva actualizada correctamente.')
                return redirect('detalle_reserva', pk=reserva.pk)
    else:
        form = ReservaForm(instance=reserva)
    return render(request, 'reservas/formulario_reserva.html', {
        'form': form,
        'titulo': 'Editar reserva',
    })


@rol_requerido(*ROLES_RESERVAS_VER)
def detalle_reserva(request, pk):
    reserva = get_object_or_404(
        Reserva.objects.select_related('cliente', 'mesa', 'usuario'),
        pk=pk,
    )
    return render(request, 'reservas/detalle_reserva.html', {
        'reserva': reserva,
        'estados_siguientes': Reserva.TRANSICIONES.get(reserva.estado, []),
    })


def _transicionar_reserva(request, pk, nuevo_estado):
    reserva = get_object_or_404(Reserva, pk=pk)
    if nuevo_estado not in Reserva.TRANSICIONES.get(reserva.estado, []):
        messages.error(
            request,
            'No se puede cambiar la reserva a ese estado.',
        )
        return redirect('detalle_reserva', pk=reserva.pk)
    reserva.estado = nuevo_estado
    try:
        reserva.save()
    except ValidationError as error:
        mensaje = (
            error.messages[0]
            if error.messages
            else 'No se pudo cambiar el estado de la reserva.'
        )
        messages.error(request, mensaje)
    else:
        mensajes = {
            Reserva.Estado.CONFIRMADA: 'Reserva confirmada correctamente.',
            Reserva.Estado.CANCELADA: 'Reserva cancelada correctamente.',
            Reserva.Estado.ATENDIDA: 'Reserva marcada como atendida.',
            Reserva.Estado.NO_ASISTIO: 'Reserva marcada como no asistió.',
        }
        messages.success(request, mensajes[nuevo_estado])
    return redirect('detalle_reserva', pk=reserva.pk)


@rol_requerido(*ROLES_RESERVAS_GESTIONAR)
@require_POST
def confirmar_reserva(request, pk):
    return _transicionar_reserva(request, pk, Reserva.Estado.CONFIRMADA)


@rol_requerido(*ROLES_RESERVAS_GESTIONAR)
@require_POST
def cancelar_reserva(request, pk):
    return _transicionar_reserva(request, pk, Reserva.Estado.CANCELADA)


@rol_requerido(*ROLES_RESERVAS_GESTIONAR)
@require_POST
def atender_reserva(request, pk):
    return _transicionar_reserva(request, pk, Reserva.Estado.ATENDIDA)


@rol_requerido(*ROLES_RESERVAS_GESTIONAR)
@require_POST
def no_asistio_reserva(request, pk):
    return _transicionar_reserva(request, pk, Reserva.Estado.NO_ASISTIO)
