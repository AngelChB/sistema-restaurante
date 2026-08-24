from django import forms

from mesas.models import Mesa

from .models import Cliente, Reserva


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'nombres',
            'apellidos',
            'documento',
            'telefono',
            'email',
            'observacion',
            'activo',
        ]
        labels = {
            'nombres': 'Nombres',
            'apellidos': 'Apellidos',
            'documento': 'Documento',
            'telefono': 'Teléfono',
            'email': 'Correo electrónico',
            'observacion': 'Observación',
            'activo': 'Activo',
        }
        widgets = {
            'nombres': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Ej. Juan Carlos'}
            ),
            'apellidos': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Opcional'}
            ),
            'documento': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Opcional'}
            ),
            'telefono': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Ej. 987654321'}
            ),
            'email': forms.EmailInput(
                attrs={'class': 'form-input', 'placeholder': 'Opcional'}
            ),
            'observacion': forms.Textarea(
                attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Opcional'}
            ),
            'activo': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def clean_documento(self):
        documento = self.cleaned_data.get('documento')
        if not documento:
            return None
        documento = documento.strip()
        clientes = Cliente.objects.filter(documento__iexact=documento)
        if self.instance.pk:
            clientes = clientes.exclude(pk=self.instance.pk)
        if clientes.exists():
            raise forms.ValidationError(
                'Ya existe un cliente con ese documento.'
            )
        return documento

    def clean_telefono(self):
        telefono = self.cleaned_data.get('telefono')
        if not telefono:
            raise forms.ValidationError(
                'El teléfono no puede estar vacío.'
            )
        return telefono.strip()


class ReservaForm(forms.ModelForm):
    class Meta:
        model = Reserva
        fields = [
            'cliente',
            'mesa',
            'fecha_hora',
            'cantidad_personas',
            'duracion_minutos',
            'observacion',
        ]
        labels = {
            'cliente': 'Cliente',
            'mesa': 'Mesa',
            'fecha_hora': 'Fecha y hora',
            'cantidad_personas': 'Cantidad de personas',
            'duracion_minutos': 'Duración (minutos)',
            'observacion': 'Observación',
        }
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-input'}),
            'mesa': forms.Select(attrs={'class': 'form-input'}),
            'fecha_hora': forms.DateTimeInput(
                attrs={'class': 'form-input', 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'cantidad_personas': forms.NumberInput(
                attrs={'class': 'form-input', 'min': '1', 'placeholder': 'Ej. 4'}
            ),
            'duracion_minutos': forms.NumberInput(
                attrs={'class': 'form-input', 'min': '1', 'placeholder': 'Ej. 120'}
            ),
            'observacion': forms.Textarea(
                attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Opcional'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        clientes = Cliente.objects.filter(activo=True)
        if self.instance.pk and self.instance.cliente_id:
            clientes = clientes | Cliente.objects.filter(pk=self.instance.cliente_id)
        self.fields['cliente'].queryset = clientes.order_by('nombres', 'apellidos')
        mesas = Mesa.objects.filter(activo=True).exclude(
            estado=Mesa.Estado.FUERA_SERVICIO
        )
        if self.instance.pk and self.instance.mesa_id:
            mesas = mesas | Mesa.objects.filter(pk=self.instance.mesa_id)
        self.fields['mesa'].queryset = mesas.order_by('numero')

    def clean_fecha_hora(self):
        fecha_hora = self.cleaned_data.get('fecha_hora')
        if not fecha_hora:
            return fecha_hora
        from django.utils import timezone

        if fecha_hora <= timezone.now():
            raise forms.ValidationError(
                'La fecha y hora de la reserva debe ser futura.'
            )
        return fecha_hora
