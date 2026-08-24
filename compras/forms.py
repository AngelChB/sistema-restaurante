import re

from django import forms

from inventario.models import Ingrediente

from .models import Compra, DetalleCompra, Proveedor


class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = [
            'razon_social',
            'ruc',
            'contacto',
            'telefono',
            'email',
            'direccion',
            'activo',
        ]
        labels = {
            'razon_social': 'Razón social',
            'ruc': 'RUC',
            'contacto': 'Contacto',
            'telefono': 'Teléfono',
            'email': 'Correo electrónico',
            'direccion': 'Dirección',
            'activo': 'Activo',
        }
        widgets = {
            'razon_social': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Ej. Distribuidora del Norte'}
            ),
            'ruc': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Ej. 20123456789'}
            ),
            'contacto': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Opcional'}
            ),
            'telefono': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Opcional'}
            ),
            'email': forms.EmailInput(
                attrs={'class': 'form-input', 'placeholder': 'Opcional'}
            ),
            'direccion': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Opcional'}
            ),
            'activo': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def clean_razon_social(self):
        razon_social = self.cleaned_data.get('razon_social')
        if not razon_social:
            raise forms.ValidationError(
                'La razón social no puede estar vacía.'
            )
        proveedores = Proveedor.objects.filter(
            razon_social__iexact=razon_social
        )
        if self.instance.pk:
            proveedores = proveedores.exclude(pk=self.instance.pk)
        if proveedores.exists():
            raise forms.ValidationError(
                'Ya existe un proveedor con esa razón social.'
            )
        return razon_social

    def clean_ruc(self):
        ruc = self.cleaned_data.get('ruc')
        if not ruc:
            return None
        ruc = ruc.strip()
        if not re.fullmatch(r'\d{11}', ruc):
            raise forms.ValidationError(
                'El RUC debe tener exactamente 11 dígitos.'
            )
        proveedores = Proveedor.objects.filter(ruc=ruc)
        if self.instance.pk:
            proveedores = proveedores.exclude(pk=self.instance.pk)
        if proveedores.exists():
            raise forms.ValidationError(
                'Ya existe un proveedor con ese RUC.'
            )
        return ruc


class CompraForm(forms.ModelForm):
    class Meta:
        model = Compra
        fields = ['proveedor', 'numero_documento', 'fecha_documento', 'observacion']
        labels = {
            'proveedor': 'Proveedor',
            'numero_documento': 'Número de documento',
            'fecha_documento': 'Fecha del documento',
            'observacion': 'Observación',
        }
        widgets = {
            'proveedor': forms.Select(attrs={'class': 'form-input'}),
            'numero_documento': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Opcional'}
            ),
            'fecha_documento': forms.DateInput(
                attrs={'class': 'form-input', 'type': 'date'}
            ),
            'observacion': forms.Textarea(
                attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Opcional'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        proveedores = Proveedor.objects.filter(activo=True)
        if self.instance.pk and self.instance.proveedor_id:
            proveedores = proveedores | Proveedor.objects.filter(
                pk=self.instance.proveedor_id
            )
        self.fields['proveedor'].queryset = proveedores.order_by('razon_social')
        if not self.instance.pk:
            from django.utils import timezone

            self.fields['fecha_documento'].initial = timezone.localdate()

    def clean_numero_documento(self):
        numero_documento = self.cleaned_data.get('numero_documento')
        if not numero_documento:
            return ''
        compras = Compra.objects.filter(numero_documento=numero_documento)
        if self.instance.pk:
            compras = compras.exclude(pk=self.instance.pk)
        if compras.exists():
            raise forms.ValidationError(
                'Ya existe una compra con ese número de documento.'
            )
        return numero_documento


class DetalleCompraForm(forms.ModelForm):
    class Meta:
        model = DetalleCompra
        fields = ['ingrediente', 'cantidad', 'costo_unitario']
        labels = {
            'ingrediente': 'Ingrediente',
            'cantidad': 'Cantidad',
            'costo_unitario': 'Costo unitario',
        }
        widgets = {
            'ingrediente': forms.Select(attrs={'class': 'form-input'}),
            'cantidad': forms.NumberInput(
                attrs={
                    'class': 'form-input',
                    'step': '0.001',
                    'min': '0.001',
                    'placeholder': 'Ej. 25',
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
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ingrediente'].queryset = Ingrediente.objects.filter(
            activo=True
        ).select_related('unidad_medida').order_by('nombre')
        self.fields['ingrediente'].required = False
        self.fields['cantidad'].required = False
        self.fields['costo_unitario'].required = False

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad is not None and cantidad <= 0:
            raise forms.ValidationError(
                'La cantidad debe ser mayor que cero.'
            )
        return cantidad

    def clean_costo_unitario(self):
        costo_unitario = self.cleaned_data.get('costo_unitario')
        if costo_unitario is not None and costo_unitario < 0:
            raise forms.ValidationError(
                'El costo unitario no puede ser negativo.'
            )
        return costo_unitario


class BaseDetalleCompraFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        ingredientes = []
        hay_detalles = False
        for form in self.forms:
            if not hasattr(form, 'cleaned_data'):
                continue
            if self.can_delete and form.cleaned_data.get('DELETE'):
                continue
            ingrediente = form.cleaned_data.get('ingrediente')
            if not ingrediente:
                continue
            cantidad = form.cleaned_data.get('cantidad')
            if cantidad is None or cantidad <= 0:
                form.add_error(
                    'cantidad', 'La cantidad debe ser mayor que cero.'
                )
                continue
            costo_unitario = form.cleaned_data.get('costo_unitario')
            if costo_unitario is None or costo_unitario < 0:
                form.add_error(
                    'costo_unitario',
                    'El costo unitario no puede ser negativo.',
                )
                continue
            if ingrediente.pk in ingredientes:
                form.add_error(
                    'ingrediente',
                    'No se puede repetir el mismo ingrediente en la compra.',
                )
                continue
            ingredientes.append(ingrediente.pk)
            hay_detalles = True
        if not hay_detalles:
            raise forms.ValidationError(
                'Debes agregar al menos un ingrediente a la compra.'
            )


DetalleCompraFormSet = forms.inlineformset_factory(
    Compra,
    DetalleCompra,
    form=DetalleCompraForm,
    formset=BaseDetalleCompraFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
