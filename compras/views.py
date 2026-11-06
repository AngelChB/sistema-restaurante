from core.paginacion import paginar
from core.filtros import filtro_id, filtro_fecha
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from personal.models import PerfilEmpleado
from personal.permisos import rol_requerido

from .forms import CompraForm, DetalleCompraFormSet, ProveedorForm
from .models import Compra, Proveedor
from .services import recibir_compra

ROLES_COMPRAS_VER = [PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.COCINA]
ROLES_COMPRAS_GESTIONAR = [PerfilEmpleado.Rol.ADMINISTRADOR]


@rol_requerido(*ROLES_COMPRAS_VER)
def lista_proveedores(request):
    buscar = request.GET.get('buscar', '').strip()
    estado = request.GET.get('estado', '')

    proveedores = Proveedor.objects.order_by('razon_social')
    if buscar:
        proveedores = proveedores.filter(
            Q(razon_social__icontains=buscar)
            | Q(ruc__icontains=buscar)
            | Q(contacto__icontains=buscar)
            | Q(telefono__icontains=buscar)
        )
    if estado == 'activos':
        proveedores = proveedores.filter(activo=True)
    elif estado == 'inactivos':
        proveedores = proveedores.filter(activo=False)

    return render(request, 'compras/lista_proveedores.html', {
        'proveedores': proveedores,
        'buscar': buscar,
        'estado': estado,
    })


@rol_requerido(*ROLES_COMPRAS_GESTIONAR)
def crear_proveedor(request):
    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proveedor creado correctamente.')
            return redirect('lista_proveedores')
    else:
        form = ProveedorForm()
    return render(request, 'compras/formulario_proveedor.html', {
        'form': form,
        'titulo': 'Nuevo proveedor',
    })


@rol_requerido(*ROLES_COMPRAS_GESTIONAR)
def editar_proveedor(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proveedor actualizado correctamente.')
            return redirect('lista_proveedores')
    else:
        form = ProveedorForm(instance=proveedor)
    return render(request, 'compras/formulario_proveedor.html', {
        'form': form,
        'titulo': 'Editar proveedor',
    })


@rol_requerido(*ROLES_COMPRAS_VER)
def lista_compras(request):
    estado = request.GET.get('estado', '')
    proveedor_id = filtro_id(request, 'proveedor')
    buscar = request.GET.get('buscar', '').strip()

    compras = Compra.objects.select_related('proveedor', 'usuario').prefetch_related(
        'detalles'
    )
    if estado in [c[0] for c in Compra.Estado.choices]:
        compras = compras.filter(estado=estado)
    if proveedor_id:
        compras = compras.filter(proveedor_id=proveedor_id)
    if buscar:
        compras = compras.filter(
            Q(numero_documento__icontains=buscar)
            | Q(proveedor__razon_social__icontains=buscar)
        )

    compras = compras.order_by('-fecha_creacion', '-id')
    proveedores = Proveedor.objects.filter(activo=True).order_by('razon_social')

    return render(request, 'compras/lista_compras.html', {
        'compras': paginar(request, compras),
        'proveedores': proveedores,
        'estado': estado,
        'proveedor_id': proveedor_id,
        'buscar': buscar,
        'estados': Compra.Estado.choices,
    })


@rol_requerido(*ROLES_COMPRAS_GESTIONAR)
def crear_compra(request):
    if request.method == 'POST':
        form = CompraForm(request.POST)
        formset = DetalleCompraFormSet(
            request.POST, instance=Compra(), prefix='detalles'
        )
        if form.is_valid() and formset.is_valid():
            compra = form.save(commit=False)
            compra.usuario = request.user
            try:
                with transaction.atomic():
                    compra.save()
                    formset.instance = compra
                    formset.save()
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Compra registrada correctamente.')
                return redirect('detalle_compra', pk=compra.pk)
    else:
        form = CompraForm()
        formset = DetalleCompraFormSet(instance=Compra(), prefix='detalles')

    return render(request, 'compras/formulario_compra.html', {
        'form': form,
        'formset': formset,
        'titulo': 'Nueva compra',
    })


@rol_requerido(*ROLES_COMPRAS_GESTIONAR)
def editar_compra(request, pk):
    compra = get_object_or_404(
        Compra.objects.select_related('proveedor').prefetch_related('detalles'),
        pk=pk,
    )
    if compra.estado != Compra.Estado.BORRADOR:
        messages.error(
            request,
            'Solo se pueden editar compras en borrador.',
        )
        return redirect('detalle_compra', pk=compra.pk)

    if request.method == 'POST':
        form = CompraForm(request.POST, instance=compra)
        formset = DetalleCompraFormSet(
            request.POST, instance=compra, prefix='detalles'
        )
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                    formset.instance = compra
                    formset.save()
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Compra actualizada correctamente.')
                return redirect('detalle_compra', pk=compra.pk)
    else:
        form = CompraForm(instance=compra)
        formset = DetalleCompraFormSet(instance=compra, prefix='detalles')

    return render(request, 'compras/formulario_compra.html', {
        'form': form,
        'formset': formset,
        'titulo': 'Editar compra',
    })


@rol_requerido(*ROLES_COMPRAS_VER)
def detalle_compra(request, pk):
    compra = get_object_or_404(
        Compra.objects.select_related('proveedor', 'usuario').prefetch_related(
            'detalles__ingrediente__unidad_medida'
        ),
        pk=pk,
    )
    return render(request, 'compras/detalle_compra.html', {
        'compra': compra,
    })


@rol_requerido(*ROLES_COMPRAS_GESTIONAR)
@require_POST
def recibir_compra_view(request, pk):
    try:
        recibir_compra(pk, request.user)
    except ValidationError as error:
        mensaje = (
            error.messages[0]
            if error.messages
            else 'No se pudo recibir la compra.'
        )
        messages.error(request, mensaje)
    else:
        messages.success(request, 'Compra recibida e inventario actualizado.')
    return redirect('detalle_compra', pk=pk)


@rol_requerido(*ROLES_COMPRAS_GESTIONAR)
@require_POST
def cancelar_compra(request, pk):
    compra = get_object_or_404(Compra, pk=pk)
    if compra.estado != Compra.Estado.BORRADOR:
        messages.error(
            request,
            'Solo se puede cancelar una compra en borrador.',
        )
        return redirect('detalle_compra', pk=pk)
    compra.estado = Compra.Estado.CANCELADA
    try:
        compra.save()
    except ValidationError as error:
        mensaje = (
            error.messages[0]
            if error.messages
            else 'No se pudo cancelar la compra.'
        )
        messages.error(request, mensaje)
    else:
        messages.success(request, 'Compra cancelada correctamente.')
    return redirect('detalle_compra', pk=pk)
