from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def obtener_rol_usuario(user):
    if user is None or not user.is_authenticated:
        return None
    perfil = getattr(user, 'perfil_empleado', None)
    if perfil is None:
        return None
    return perfil.rol


def tiene_roles(user, roles):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    rol = obtener_rol_usuario(user)
    if rol is None:
        return False
    return rol in roles


def rol_requerido(*roles):
    def decorador(vista):
        @login_required
        @wraps(vista)
        def envoltorio(request, *args, **kwargs):
            if not tiene_roles(request.user, roles):
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        return envoltorio

    return decorador
