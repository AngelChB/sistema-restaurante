from core.paginacion import paginar
from core.filtros import filtro_id, filtro_fecha
from core.fechas import parsear_fecha

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.shortcuts import get_object_or_404, redirect, render

from catalogo.models import Categoria, Producto
from personal.models import PerfilEmpleado
from personal.permisos import rol_requerido

from .forms import (
    IngredienteForm,
    MovimientoInventarioForm,
    RecetaProductoForm,
    UnidadMedidaForm,
)
from .models import Ingrediente, MovimientoInventario, RecetaProducto, UnidadMedida

ROLES_VER = [PerfilEmpleado.Rol.ADMINISTRADOR, PerfilEmpleado.Rol.COCINA]
ROLES_GESTIONAR = [PerfilEmpleado.Rol.ADMINISTRADOR]


@rol_requerido(*ROLES_VER)
def panel_inventario(request):
    activos = Ingrediente.objects.filter(activo=True)
    bajo_stock = activos.filter(stock_actual__lte=F('stock_minimo')).count()
    sin_stock = activos.filter(stock_actual=0).count()
    valor_inventario = activos.aggregate(
        valor=Sum(
            F('stock_actual') * F('costo_unitario'),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        )
    )['valor'] or 0
    menores_stock = activos.select_related('unidad_medida').order_by(
        'stock_actual', 'nombre'
    )[:10]
    movimientos_recientes = MovimientoInventario.objects.select_related(
        'ingrediente__unidad_medida', 'usuario'
    )[:10]

    return render(request, 'inventario/panel.html', {
        'total_ingredientes': activos.count(),
        'bajo_stock': bajo_stock,
        'sin_stock': sin_stock,
        'valor_inventario': valor_inventario,
        'menores_stock': menores_stock,
        'movimientos_recientes': movimientos_recientes,
    })


@rol_requerido(*ROLES_VER)
def lista_ingredientes(request):
    buscar = request.GET.get('buscar', '').strip()
    unidad_id = filtro_id(request, 'unidad')
    stock = request.GET.get('stock', '')

    ingredientes = Ingrediente.objects.select_related('unidad_medida').annotate(
        valor=ExpressionWrapper(
            F('stock_actual') * F('costo_unitario'),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        )
    )
    if buscar:
        ingredientes = ingredientes.filter(nombre__icontains=buscar)
    if unidad_id:
        ingredientes = ingredientes.filter(unidad_medida_id=unidad_id)
    if stock == 'bajo':
        ingredientes = ingredientes.filter(stock_actual__lte=F('stock_minimo'))
    elif stock == 'sin_stock':
        ingredientes = ingredientes.filter(stock_actual=0)
    elif stock == 'normal':
        ingredientes = ingredientes.filter(stock_actual__gt=F('stock_minimo'))

    ingredientes = ingredientes.order_by('nombre')
    unidades = UnidadMedida.objects.filter(activo=True).order_by('nombre')

    return render(request, 'inventario/lista_ingredientes.html', {
        'ingredientes': ingredientes,
        'unidades': unidades,
        'buscar': buscar,
        'unidad_id': unidad_id,
        'stock': stock,
    })


@rol_requerido(*ROLES_GESTIONAR)
def crear_ingrediente(request):
    if request.method == 'POST':
        form = IngredienteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ingrediente creado correctamente.')
            return redirect('lista_ingredientes')
    else:
        form = IngredienteForm()
    return render(request, 'inventario/formulario_ingrediente.html', {
        'form': form,
        'titulo': 'Nuevo ingrediente',
    })


@rol_requerido(*ROLES_GESTIONAR)
def editar_ingrediente(request, pk):
    ingrediente = get_object_or_404(Ingrediente, pk=pk)
    if request.method == 'POST':
        form = IngredienteForm(request.POST, instance=ingrediente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ingrediente actualizado correctamente.')
            return redirect('lista_ingredientes')
    else:
        form = IngredienteForm(instance=ingrediente)
    return render(request, 'inventario/formulario_ingrediente.html', {
        'form': form,
        'titulo': 'Editar ingrediente',
    })


@rol_requerido(*ROLES_GESTIONAR)
def registrar_movimiento(request):
    movimiento = MovimientoInventario(usuario=request.user)
    if request.method == 'POST':
        form = MovimientoInventarioForm(request.POST, instance=movimiento)
        if form.is_valid():
            try:
                with transaction.atomic():
                    movimiento = form.save()
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(
                    request,
                    'Movimiento registrado. '
                    f'Stock de {movimiento.ingrediente.nombre}: '
                    f'{movimiento.stock_anterior} → {movimiento.stock_resultante}.',
                )
                return redirect('historial_movimientos')
    else:
        form = MovimientoInventarioForm(instance=movimiento)
    return render(request, 'inventario/formulario_movimiento.html', {
        'form': form,
    })


@rol_requerido(*ROLES_VER)
def historial_movimientos(request):
    ingrediente_id = filtro_id(request, 'ingrediente')
    tipo = request.GET.get('tipo', '')
    fecha_desde = filtro_fecha(request, 'fecha_desde')
    fecha_hasta = filtro_fecha(request, 'fecha_hasta')

    movimientos = MovimientoInventario.objects.select_related(
        'ingrediente__unidad_medida', 'pedido', 'compra', 'usuario'
    )
    if ingrediente_id:
        movimientos = movimientos.filter(ingrediente_id=ingrediente_id)
    if tipo:
        movimientos = movimientos.filter(tipo=tipo)
    fecha_desde_dt = parsear_fecha(fecha_desde)
    if fecha_desde_dt is not None:
        movimientos = movimientos.filter(fecha_creacion__date__gte=fecha_desde_dt)
    fecha_hasta_dt = parsear_fecha(fecha_hasta)
    if fecha_hasta_dt is not None:
        movimientos = movimientos.filter(fecha_creacion__date__lte=fecha_hasta_dt)

    movimientos = movimientos.order_by('-fecha_creacion', '-id')
    ingredientes = Ingrediente.objects.filter(activo=True).order_by('nombre')

    return render(request, 'inventario/historial_movimientos.html', {
        'movimientos': paginar(request, movimientos),
        'ingredientes': ingredientes,
        'tipos': MovimientoInventario.Tipo.choices,
        'ingrediente_id': ingrediente_id,
        'tipo': tipo,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
    })


@rol_requerido(*ROLES_VER)
def lista_unidades(request):
    unidades = UnidadMedida.objects.order_by('nombre')
    return render(request, 'inventario/lista_unidades.html', {
        'unidades': unidades,
    })


@rol_requerido(*ROLES_GESTIONAR)
def crear_unidad(request):
    if request.method == 'POST':
        form = UnidadMedidaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Unidad de medida creada correctamente.')
            return redirect('lista_unidades')
    else:
        form = UnidadMedidaForm()
    return render(request, 'inventario/formulario_unidad.html', {
        'form': form,
        'titulo': 'Nueva unidad de medida',
    })


@rol_requerido(*ROLES_GESTIONAR)
def editar_unidad(request, pk):
    unidad = get_object_or_404(UnidadMedida, pk=pk)
    if request.method == 'POST':
        form = UnidadMedidaForm(request.POST, instance=unidad)
        if form.is_valid():
            form.save()
            messages.success(request, 'Unidad de medida actualizada correctamente.')
            return redirect('lista_unidades')
    else:
        form = UnidadMedidaForm(instance=unidad)
    return render(request, 'inventario/formulario_unidad.html', {
        'form': form,
        'titulo': 'Editar unidad de medida',
    })


@rol_requerido(*ROLES_VER)
def lista_recetas(request):
    buscar = request.GET.get('buscar', '').strip()
    categoria_id = filtro_id(request, 'categoria')

    recetas = RecetaProducto.objects.select_related(
        'producto__categoria', 'ingrediente__unidad_medida'
    )
    if buscar:
        recetas = recetas.filter(producto__nombre__icontains=buscar)
    if categoria_id:
        recetas = recetas.filter(producto__categoria_id=categoria_id)

    recetas = recetas.order_by(
        'producto__categoria__nombre', 'producto__nombre', 'ingrediente__nombre'
    )
    productos_con_recetas = []
    producto_actual = None
    for receta in recetas:
        if producto_actual is None or receta.producto_id != producto_actual.pk:
            producto_actual = receta.producto
            productos_con_recetas.append({
                'producto': producto_actual,
                'items': [],
            })
        productos_con_recetas[-1]['items'].append(receta)

    categorias = Categoria.objects.filter(activo=True).order_by('nombre')

    return render(request, 'inventario/lista_recetas.html', {
        'productos_con_recetas': productos_con_recetas,
        'categorias': categorias,
        'buscar': buscar,
        'categoria_id': categoria_id,
    })


@rol_requerido(*ROLES_GESTIONAR)
def crear_receta(request):
    if request.method == 'POST':
        form = RecetaProductoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ingrediente agregado a la receta correctamente.')
            return redirect('lista_recetas')
    else:
        form = RecetaProductoForm()
    return render(request, 'inventario/formulario_receta.html', {
        'form': form,
        'titulo': 'Agregar ingrediente a receta',
    })


@rol_requerido(*ROLES_GESTIONAR)
def editar_receta(request, pk):
    receta = get_object_or_404(
        RecetaProducto.objects.select_related('producto', 'ingrediente'),
        pk=pk,
    )
    if request.method == 'POST':
        form = RecetaProductoForm(request.POST, instance=receta)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ingrediente de receta actualizado correctamente.')
            return redirect('lista_recetas')
    else:
        form = RecetaProductoForm(instance=receta)
    return render(request, 'inventario/formulario_receta.html', {
        'form': form,
        'titulo': 'Editar ingrediente de receta',
    })
