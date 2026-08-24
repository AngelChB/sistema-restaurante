from django import forms

from catalogo.models import Producto

from .models import Ingrediente, MovimientoInventario, RecetaProducto, UnidadMedida


class UnidadMedidaForm(forms.ModelForm):
    class Meta:
        model = UnidadMedida
        fields = ['nombre', 'abreviatura', 'activo']
        labels = {
            'nombre': 'Nombre',
            'abreviatura': 'Abreviatura',
            'activo': 'Activa',
        }
        widgets = {
            'nombre': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Ej. Kilogramo'}
            ),
            'abreviatura': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Ej. kg'}
            ),
            'activo': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        if not nombre:
            raise forms.ValidationError(
                'El nombre de la unidad no puede estar vacío.'
            )
        unidades = UnidadMedida.objects.filter(nombre__iexact=nombre)
        if self.instance.pk:
            unidades = unidades.exclude(pk=self.instance.pk)
        if unidades.exists():
            raise forms.ValidationError(
                'Ya existe una unidad de medida con ese nombre.'
            )
        return nombre

    def clean_abreviatura(self):
        abreviatura = self.cleaned_data.get('abreviatura')
        if not abreviatura:
            raise forms.ValidationError(
                'La abreviatura no puede estar vacía.'
            )
        unidades = UnidadMedida.objects.filter(abreviatura__iexact=abreviatura)
        if self.instance.pk:
            unidades = unidades.exclude(pk=self.instance.pk)
        if unidades.exists():
            raise forms.ValidationError(
                'Ya existe una unidad de medida con esa abreviatura.'
            )
        return abreviatura


class IngredienteForm(forms.ModelForm):
    class Meta:
        model = Ingrediente
        fields = [
            'nombre',
            'unidad_medida',
            'stock_minimo',
            'costo_unitario',
            'activo',
        ]
        labels = {
            'nombre': 'Nombre',
            'unidad_medida': 'Unidad de medida',
            'stock_minimo': 'Stock mínimo',
            'costo_unitario': 'Costo unitario',
            'activo': 'Activo',
        }
        widgets = {
            'nombre': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Ej. Harina'}
            ),
            'unidad_medida': forms.Select(attrs={'class': 'form-input'}),
            'stock_minimo': forms.NumberInput(
                attrs={
                    'class': 'form-input',
                    'step': '0.001',
                    'min': '0',
                    'placeholder': 'Ej. 10',
                }
            ),
            'costo_unitario': forms.NumberInput(
                attrs={
                    'class': 'form-input',
                    'step': '0.0001',
                    'min': '0',
                    'placeholder': 'Ej. 5.0000',
                }
            ),
            'activo': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        if not nombre:
            raise forms.ValidationError(
                'El nombre del ingrediente no puede estar vacío.'
            )
        ingredientes = Ingrediente.objects.filter(nombre__iexact=nombre)
        if self.instance.pk:
            ingredientes = ingredientes.exclude(pk=self.instance.pk)
        if ingredientes.exists():
            raise forms.ValidationError(
                'Ya existe un ingrediente con ese nombre.'
            )
        return nombre

    def clean_stock_minimo(self):
        stock_minimo = self.cleaned_data.get('stock_minimo')
        if stock_minimo is not None and stock_minimo < 0:
            raise forms.ValidationError(
                'El stock mínimo no puede ser negativo.'
            )
        return stock_minimo

    def clean_costo_unitario(self):
        costo_unitario = self.cleaned_data.get('costo_unitario')
        if costo_unitario is not None and costo_unitario < 0:
            raise forms.ValidationError(
                'El costo unitario no puede ser negativo.'
            )
        return costo_unitario


class MovimientoInventarioForm(forms.ModelForm):
    class Meta:
        model = MovimientoInventario
        fields = ['ingrediente', 'tipo', 'cantidad', 'motivo', 'referencia']
        labels = {
            'ingrediente': 'Ingrediente',
            'tipo': 'Tipo de movimiento',
            'cantidad': 'Cantidad',
            'motivo': 'Motivo',
            'referencia': 'Referencia',
        }
        widgets = {
            'ingrediente': forms.Select(attrs={'class': 'form-input'}),
            'tipo': forms.Select(attrs={'class': 'form-input'}),
            'cantidad': forms.NumberInput(
                attrs={
                    'class': 'form-input',
                    'step': '0.001',
                    'min': '0.001',
                    'placeholder': 'Ej. 25',
                }
            ),
            'motivo': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Ej. Compra a proveedor'}
            ),
            'referencia': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Opcional'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ingrediente'].queryset = Ingrediente.objects.filter(
            activo=True
        ).order_by('nombre')

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad is not None and cantidad <= 0:
            raise forms.ValidationError(
                'La cantidad debe ser mayor que cero.'
            )
        return cantidad


class RecetaProductoForm(forms.ModelForm):
    class Meta:
        model = RecetaProducto
        fields = ['producto', 'ingrediente', 'cantidad']
        labels = {
            'producto': 'Producto',
            'ingrediente': 'Ingrediente',
            'cantidad': 'Cantidad',
        }
        widgets = {
            'producto': forms.Select(attrs={'class': 'form-input'}),
            'ingrediente': forms.Select(attrs={'class': 'form-input'}),
            'cantidad': forms.NumberInput(
                attrs={
                    'class': 'form-input',
                    'step': '0.001',
                    'min': '0.001',
                    'placeholder': 'Ej. 0.5',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto'].queryset = Producto.objects.filter(
            disponible=True
        ).select_related('categoria').order_by('nombre')
        self.fields['ingrediente'].queryset = Ingrediente.objects.filter(
            activo=True
        ).order_by('nombre')

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad is not None and cantidad <= 0:
            raise forms.ValidationError(
                'La cantidad debe ser mayor que cero.'
            )
        return cantidad

    def clean(self):
        cleaned_data = super().clean()
        producto = cleaned_data.get('producto')
        ingrediente = cleaned_data.get('ingrediente')
        if producto and ingrediente:
            recetas = RecetaProducto.objects.filter(
                producto=producto,
                ingrediente=ingrediente,
            )
            if self.instance.pk:
                recetas = recetas.exclude(pk=self.instance.pk)
            if recetas.exists():
                self.add_error(
                    'ingrediente',
                    'Este ingrediente ya está en la receta de este producto.',
                )
        return cleaned_data
