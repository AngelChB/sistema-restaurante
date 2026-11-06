from .models import PerfilEmpleado
from .permisos import tiene_roles


def permisos(request):
    contexto = {
        'rol_usuario': None,
        'rol_usuario_nombre': None,
        'es_administrador': False,
        'puede_ver_mesas': False,
        'puede_ver_catalogo': False,
        'puede_ver_pedidos': False,
        'puede_ver_cocina': False,
        'puede_ver_sala': False,
        'puede_ver_caja': False,
        'puede_ver_inventario': False,
        'puede_gestionar_inventario': False,
        'puede_ver_compras': False,
        'puede_gestionar_compras': False,
        'puede_ver_personal': False,
        'puede_ver_reportes': False,
        'puede_ver_reservas': False,
    }
    user = request.user
    if not user.is_authenticated:
        return contexto

    perfil = getattr(user, 'perfil_empleado', None)
    contexto['rol_usuario'] = perfil.rol if perfil is not None else None
    contexto['rol_usuario_nombre'] = (
        perfil.get_rol_display() if perfil is not None else None
    )
    contexto['es_administrador'] = tiene_roles(user, [PerfilEmpleado.Rol.ADMINISTRADOR])
    contexto['puede_ver_mesas'] = tiene_roles(
        user, [PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.MESERO]
    )
    contexto['puede_ver_catalogo'] = tiene_roles(
        user,
        [
            PerfilEmpleado.Rol.ADMINISTRADOR,
            PerfilEmpleado.Rol.MESERO,
            PerfilEmpleado.Rol.COCINA,
            PerfilEmpleado.Rol.CAJERO,
        ],
    )
    contexto['puede_ver_pedidos'] = tiene_roles(
        user, [PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.MESERO]
    )
    contexto['puede_ver_cocina'] = tiene_roles(
        user, [PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.COCINA]
    )
    contexto['puede_ver_sala'] = tiene_roles(
        user, [PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.MESERO]
    )
    contexto['puede_ver_caja'] = tiene_roles(
        user, [PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.CAJERO]
    )
    contexto['puede_ver_inventario'] = tiene_roles(
        user, [PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.COCINA]
    )
    contexto['puede_gestionar_inventario'] = tiene_roles(
        user, [PerfilEmpleado.Rol.ADMINISTRADOR]
    )
    contexto['puede_ver_compras'] = tiene_roles(
        user, [PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.COCINA]
    )
    contexto['puede_gestionar_compras'] = tiene_roles(
        user, [PerfilEmpleado.Rol.ADMINISTRADOR]
    )
    contexto['puede_ver_personal'] = tiene_roles(
        user, [PerfilEmpleado.Rol.ADMINISTRADOR]
    )
    contexto['puede_ver_reportes'] = tiene_roles(
        user, [PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.CAJERO]
    )
    contexto['puede_ver_reservas'] = tiene_roles(
        user, [PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.MESERO]
    )
    return contexto
