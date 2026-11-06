from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from core.filtros import filtro_id
from personal.models import PerfilEmpleado
from personal.permisos import rol_requerido

from .forms import CategoriaForm, ProductoForm
from .models import Categoria, Producto

ROL_CATALOGO = [
    PerfilEmpleado.Rol.ADMINISTRADOR,
    PerfilEmpleado.Rol.MESERO,
    PerfilEmpleado.Rol.COCINA,
    PerfilEmpleado.Rol.CAJERO,
]


@rol_requerido(*ROL_CATALOGO)
def lista_productos(request):
    buscar = request.GET.get('buscar', '').strip()
    categoria_id = filtro_id(request, 'categoria')
    disponible = request.GET.get('disponible', '')

    productos = Producto.objects.select_related('categoria').all()
    if buscar:
        productos = productos.filter(nombre__icontains=buscar)
    if categoria_id:
        productos = productos.filter(categoria_id=categoria_id)
    if disponible in ('1', '0'):
        productos = productos.filter(disponible=(disponible == '1'))

    productos = productos.order_by('categoria__nombre', 'nombre')
    categorias = Categoria.objects.filter(activo=True).order_by('nombre')

    return render(
        request,
        'catalogo/lista_productos.html',
        {
            'productos': productos,
            'categorias': categorias,
            'buscar': buscar,
            'categoria_id': categoria_id,
            'disponible': disponible,
        },
    )


@rol_requerido(PerfilEmpleado.Rol.ADMINISTRADOR)
def crear_producto(request):
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto creado correctamente.')
            return redirect('lista_productos')
    else:
        form = ProductoForm()
    return render(
        request,
        'catalogo/formulario_producto.html',
        {
            'form': form,
            'titulo': 'Nuevo producto',
        },
    )


@rol_requerido(PerfilEmpleado.Rol.ADMINISTRADOR)
def editar_producto(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto actualizado correctamente.')
            return redirect('lista_productos')
    else:
        form = ProductoForm(instance=producto)
    return render(
        request,
        'catalogo/formulario_producto.html',
        {
            'form': form,
            'titulo': 'Editar producto',
        },
    )


@rol_requerido(*ROL_CATALOGO)
def lista_categorias(request):
    categorias = Categoria.objects.order_by('nombre')
    return render(
        request,
        'catalogo/lista_categorias.html',
        {
            'categorias': categorias,
        },
    )


@rol_requerido(PerfilEmpleado.Rol.ADMINISTRADOR)
def crear_categoria(request):
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoría creada correctamente.')
            return redirect('lista_categorias')
    else:
        form = CategoriaForm()
    return render(
        request,
        'catalogo/formulario_categoria.html',
        {
            'form': form,
            'titulo': 'Nueva categoría',
        },
    )


@rol_requerido(PerfilEmpleado.Rol.ADMINISTRADOR)
def editar_categoria(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    if request.method == 'POST':
        form = CategoriaForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoría actualizada correctamente.')
            return redirect('lista_categorias')
    else:
        form = CategoriaForm(instance=categoria)
    return render(
        request,
        'catalogo/formulario_categoria.html',
        {
            'form': form,
            'titulo': 'Editar categoría',
        },
    )
