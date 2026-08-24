from django import forms

from .models import Mesa


class MesaForm(forms.ModelForm):
    class Meta:
        model = Mesa
        fields = ['numero', 'capacidad', 'estado', 'ubicacion', 'activo']
        labels = {
            'numero': 'Número',
            'capacidad': 'Capacidad',
            'estado': 'Estado',
            'ubicacion': 'Ubicación',
            'activo': 'Activa',
        }
        help_texts = {
            'numero': 'Número único de la mesa.',
            'capacidad': 'Cantidad de personas que puede acomodar.',
            'estado': 'Estado actual de la mesa.',
            'ubicacion': 'Zona o área donde se encuentra la mesa.',
            'activo': 'Indica si la mesa está disponible para uso.',
        }
        widgets = {
            'numero': forms.NumberInput(
                attrs={'class': 'form-input', 'placeholder': 'Ej. 1'}
            ),
            'capacidad': forms.NumberInput(
                attrs={'class': 'form-input', 'placeholder': 'Ej. 4'}
            ),
            'estado': forms.Select(attrs={'class': 'form-input'}),
            'ubicacion': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Ej. Terraza'}
            ),
            'activo': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def clean_numero(self):
        numero = self.cleaned_data.get('numero')
        if numero is not None and numero <= 0:
            raise forms.ValidationError('El número de mesa debe ser mayor que cero.')
        if numero is not None:
            mesas = Mesa.objects.filter(numero=numero)
            if self.instance.pk:
                mesas = mesas.exclude(pk=self.instance.pk)
            if mesas.exists():
                raise forms.ValidationError('Ya existe una mesa con ese número.')
        return numero

    def clean_capacidad(self):
        capacidad = self.cleaned_data.get('capacidad')
        if capacidad is not None and capacidad <= 0:
            raise forms.ValidationError('La capacidad debe ser mayor que cero.')
        return capacidad
