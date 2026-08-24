from django import forms

from .models import Categoria, Producto


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nombre', 'descripcion', 'activo']
        labels = {
            'nombre': 'Nombre',
            'descripcion': 'Descripción',
            'activo': 'Activa',
        }
        widgets = {
            'nombre': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Ej. Bebidas'}
            ),
            'descripcion': forms.Textarea(
                attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Opcional'}
            ),
            'activo': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        if not nombre:
            raise forms.ValidationError('El nombre de la categoría no puede estar vacío.')
        categorias = Categoria.objects.filter(nombre__iexact=nombre)
        if self.instance.pk:
            categorias = categorias.exclude(pk=self.instance.pk)
        if categorias.exists():
            raise forms.ValidationError('Ya existe una categoría con ese nombre.')
        return nombre


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['categoria', 'nombre', 'descripcion', 'precio', 'disponible']
        labels = {
            'categoria': 'Categoría',
            'nombre': 'Nombre',
            'descripcion': 'Descripción',
            'precio': 'Precio',
            'disponible': 'Disponible',
        }
        widgets = {
            'categoria': forms.Select(attrs={'class': 'form-input'}),
            'nombre': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Ej. Café'}
            ),
            'descripcion': forms.Textarea(
                attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Opcional'}
            ),
            'precio': forms.NumberInput(
                attrs={
                    'class': 'form-input',
                    'step': '0.01',
                    'min': '0.01',
                    'placeholder': 'Ej. 12.50',
                }
            ),
            'disponible': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        if not nombre:
            raise forms.ValidationError('El nombre del producto no puede estar vacío.')
        return nombre

    def clean_precio(self):
        precio = self.cleaned_data.get('precio')
        if precio is not None and precio <= 0:
            raise forms.ValidationError('El precio debe ser mayor que cero.')
        return precio

    def clean(self):
        cleaned_data = super().clean()
        nombre = cleaned_data.get('nombre')
        categoria = cleaned_data.get('categoria')
        if nombre and categoria:
            productos = Producto.objects.filter(
                categoria=categoria,
                nombre__iexact=nombre,
            )
            if self.instance.pk:
                productos = productos.exclude(pk=self.instance.pk)
            if productos.exists():
                self.add_error(
                    'nombre',
                    'Ya existe un producto con ese nombre en esta categoría.',
                )
        return cleaned_data
