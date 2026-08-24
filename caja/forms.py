from django import forms

from .models import CierreCaja, Pago


class PagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = ['metodo', 'monto_recibido', 'referencia', 'observacion']
        labels = {
            'metodo': 'Método de pago',
            'monto_recibido': 'Monto recibido',
            'referencia': 'Referencia',
            'observacion': 'Observación',
        }
        widgets = {
            'metodo': forms.Select(attrs={'class': 'form-input'}),
            'monto_recibido': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Opcional fuera de efectivo',
            }),
            'referencia': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Opcional',
            }),
            'observacion': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': 'Opcional',
            }),
        }

    def clean_monto_recibido(self):
        monto_recibido = self.cleaned_data.get('monto_recibido')
        metodo = self.cleaned_data.get('metodo')
        if metodo == Pago.Metodo.EFECTIVO and monto_recibido is None:
            raise forms.ValidationError(
                'En pagos en efectivo el monto recibido es obligatorio.'
            )
        return monto_recibido


class CierreCajaForm(forms.ModelForm):
    class Meta:
        model = CierreCaja
        fields = ['monto_inicial', 'efectivo_contado', 'observacion']
        labels = {
            'monto_inicial': 'Monto inicial',
            'efectivo_contado': 'Efectivo contado',
            'observacion': 'Observación',
        }
        widgets = {
            'monto_inicial': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.01',
                'min': '0',
            }),
            'efectivo_contado': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.01',
                'min': '0',
            }),
            'observacion': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': 'Opcional',
            }),
        }

    def clean_monto_inicial(self):
        monto_inicial = self.cleaned_data.get('monto_inicial')
        if monto_inicial is not None and monto_inicial < 0:
            raise forms.ValidationError('El monto inicial no puede ser negativo.')
        return monto_inicial

    def clean_efectivo_contado(self):
        efectivo_contado = self.cleaned_data.get('efectivo_contado')
        if efectivo_contado is not None and efectivo_contado < 0:
            raise forms.ValidationError(
                'El efectivo contado no puede ser negativo.'
            )
        return efectivo_contado
