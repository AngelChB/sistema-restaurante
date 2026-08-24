from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    CambiarPasswordForm,
    CambiarUsuarioForm,
    EmpleadoCrearForm,
    EmpleadoEditarForm,
)
from .models import PerfilEmpleado
from .permisos import rol_requerido

User = get_user_model()


@rol_requerido(PerfilEmpleado.Rol.ADMINISTRADOR)
def lista_empleados(request):
    buscar = request.GET.get('buscar', '').strip()
    rol = request.GET.get('rol', '')

    usuarios = User.objects.select_related('perfil_empleado').order_by(
        '-is_active', 'first_name', 'last_name', 'username'
    )
    if buscar:
        usuarios = usuarios.filter(
            Q(username__icontains=buscar)
            | Q(first_name__icontains=buscar)
            | Q(last_name__icontains=buscar)
            | Q(email__icontains=buscar)
        )
    if rol in [codigo for codigo, _ in PerfilEmpleado.Rol.choices]:
        usuarios = usuarios.filter(perfil_empleado__rol=rol)

    return render(request, 'personal/lista.html', {
        'usuarios': usuarios,
        'buscar': buscar,
        'rol': rol,
        'roles': PerfilEmpleado.Rol.choices,
    })


@rol_requerido(PerfilEmpleado.Rol.ADMINISTRADOR)
def crear_empleado(request):
    if request.method == 'POST':
        form = EmpleadoCrearForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Empleado creado correctamente.')
            return redirect('lista_empleados')
    else:
        form = EmpleadoCrearForm()

    return render(request, 'personal/formulario.html', {
        'form': form,
        'titulo': 'Nuevo empleado',
    })


@rol_requerido(PerfilEmpleado.Rol.ADMINISTRADOR)
def editar_empleado(request, pk):
    empleado = get_object_or_404(User, pk=pk)
    perfil, _ = PerfilEmpleado.objects.get_or_create(
        usuario=empleado,
        defaults={'rol': PerfilEmpleado.Rol.MESERO},
    )

    if request.method == 'POST':
        form = EmpleadoEditarForm(request.POST, instance=empleado)
        if form.is_valid():
            error = False
            if request.user.pk == empleado.pk and not form.cleaned_data['is_active']:
                form.add_error(
                    'is_active', 'No puedes desactivar tu propio usuario.'
                )
                error = True
            if (
                request.user.pk == empleado.pk
                and empleado.is_staff
                and not form.cleaned_data['is_staff']
            ):
                form.add_error(
                    'is_staff', 'No puedes quitarte tus propios permisos de staff.'
                )
                error = True
            if not error:
                with transaction.atomic():
                    empleado = form.save()
                    perfil.rol = form.cleaned_data['rol']
                    perfil.telefono = form.cleaned_data.get('telefono', '')
                    perfil.save()
                messages.success(request, 'Empleado actualizado correctamente.')
                return redirect('lista_empleados')
    else:
        form = EmpleadoEditarForm(
            instance=empleado,
            initial={
                'is_staff': empleado.is_staff,
                'rol': perfil.rol,
                'telefono': perfil.telefono,
            },
        )

    return render(request, 'personal/formulario.html', {
        'form': form,
        'empleado': empleado,
        'titulo': 'Editar empleado',
    })


@rol_requerido(PerfilEmpleado.Rol.ADMINISTRADOR)
def cambiar_password_empleado(request, pk):
    empleado = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        form = CambiarPasswordForm(empleado, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Contraseña actualizada correctamente.')
            return redirect('lista_empleados')
    else:
        form = CambiarPasswordForm(empleado)

    return render(request, 'personal/cambiar_password.html', {
        'form': form,
        'empleado': empleado,
        'titulo': 'Cambiar contraseña',
    })


@rol_requerido(PerfilEmpleado.Rol.ADMINISTRADOR)
def cambiar_usuario_empleado(request, pk):
    empleado = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        form = CambiarUsuarioForm(request.POST, instance=empleado)
        if form.is_valid():
            form.save()
            messages.success(
                request, 'Nombre de usuario actualizado correctamente.'
            )
            return redirect('lista_empleados')
    else:
        form = CambiarUsuarioForm(instance=empleado)

    return render(request, 'personal/cambiar_usuario.html', {
        'form': form,
        'empleado': empleado,
        'titulo': 'Cambiar nombre de usuario',
    })


@rol_requerido(PerfilEmpleado.Rol.ADMINISTRADOR)
@require_POST
def alternar_estado_empleado(request, pk):
    empleado = get_object_or_404(User, pk=pk)

    if request.user.pk == empleado.pk:
        messages.error(request, 'No puedes desactivar tu propio usuario.')
        return redirect('lista_empleados')

    nombre = empleado.get_full_name() or empleado.username
    if empleado.is_active:
        empleado.is_active = False
        mensaje = f'{nombre} desactivado. Ya no puede iniciar sesión.'
    else:
        empleado.is_active = True
        mensaje = f'{nombre} activado. Ya puede iniciar sesión.'
    empleado.save(update_fields=['is_active'])
    messages.success(request, mensaje)
    return redirect('lista_empleados')
