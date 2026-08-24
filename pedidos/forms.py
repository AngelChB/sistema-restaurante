from django import forms

from catalogo.models import Producto
from mesas.models import Mesa

from .models import DetallePedido, Pedido


class PedidoForm(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = ['mesa', 'observacion']
        labels = {
            'mesa': 'Mesa',
            'observacion': 'Observación',
        }
        widgets = {
            'mesa': forms.Select(attrs={'class': 'form-input'}),
            'observacion': forms.Textarea(
                attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Opcional'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        mesas = Mesa.objects.filter(activo=True).exclude(
            estado=Mesa.Estado.FUERA_SERVICIO
        )
        if not self.instance.pk:
            mesas = mesas.filter(estado=Mesa.Estado.LIBRE)
        self.fields['mesa'].queryset = mesas


class DetallePedidoForm(forms.ModelForm):
    class Meta:
        model = DetallePedido
        fields = ['producto', 'cantidad', 'observacion']
        labels = {
            'producto': 'Producto',
            'cantidad': 'Cantidad',
            'observacion': 'Observación',
        }
        widgets = {
            'producto': forms.Select(attrs={'class': 'form-input'}),
            'cantidad': forms.NumberInput(
                attrs={'class': 'form-input', 'min': '1', 'value': '1'}
            ),
            'observacion': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Opcional'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto'].queryset = Producto.objects.filter(
            disponible=True
        )
        self.fields['producto'].required = False
        self.fields['cantidad'].required = False

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad is not None and cantidad < 1:
            raise forms.ValidationError('La cantidad debe ser mayor o igual a 1.')
        return cantidad


class BaseDetallePedidoFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        productos = []
        hay_detalles = False
        for form in self.forms:
            if not hasattr(form, 'cleaned_data'):
                continue
            if self.can_delete and form.cleaned_data.get('DELETE'):
                continue
            producto = form.cleaned_data.get('producto')
            if not producto:
                continue
            cantidad = form.cleaned_data.get('cantidad')
            if cantidad is None or cantidad < 1:
                form.add_error(
                    'cantidad', 'La cantidad debe ser mayor o igual a 1.'
                )
                continue
            if producto.pk in productos:
                form.add_error(
                    'producto',
                    'No se puede repetir el mismo producto en el pedido.',
                )
                continue
            productos.append(producto.pk)
            hay_detalles = True
        if not hay_detalles:
            raise forms.ValidationError(
                'Debes agregar al menos un producto al pedido.'
            )


DetallePedidoFormSet = forms.inlineformset_factory(
    Pedido,
    DetallePedido,
    form=DetallePedidoForm,
    formset=BaseDetallePedidoFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
