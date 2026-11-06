from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth import password_validation
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from django.db import transaction

from .models import PerfilEmpleado

User = get_user_model()


class EmpleadoCrearForm(UserCreationForm):
    rol = forms.ChoiceField(
        choices=PerfilEmpleado.Rol.choices,
        label='Rol',
        help_text='Rol del empleado en el restaurante.',
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    telefono = forms.CharField(
        max_length=20,
        required=False,
        label='Teléfono',
        help_text='Opcional.',
        widget=forms.TextInput(
            attrs={'class': 'form-input', 'placeholder': 'Ej. 999 888 777'}
        ),
    )
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        label='Activo',
        help_text='Indica si el empleado puede iniciar sesión.',
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'is_active')
        labels = {
            'username': 'Nombre de usuario',
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'email': 'Correo electrónico',
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-input'}),
            'first_name': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Ej. María'}
            ),
            'last_name': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Ej. García'}
            ),
            'email': forms.EmailInput(
                attrs={'class': 'form-input', 'placeholder': 'ejemplo@restaurante.com'}
            ),
        }
        help_texts = {
            'username': 'Requerido. 150 caracteres o menos, sin espacios.',
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            duplicado = User.objects.filter(username__iexact=username).exclude(
                pk=self.instance.pk
            )
            if duplicado.exists():
                raise forms.ValidationError(
                    'Ya existe un empleado con ese nombre de usuario.'
                )
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            duplicado = User.objects.filter(email__iexact=email).exclude(
                pk=self.instance.pk
            )
            if duplicado.exists():
                raise forms.ValidationError(
                    'Ya existe un empleado con ese correo electrónico.'
                )
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = False
        user.is_superuser = False
        with transaction.atomic():
            if commit:
                user.save()
                PerfilEmpleado.objects.update_or_create(
                    usuario=user,
                    defaults={
                        'rol': self.cleaned_data.get('rol') or PerfilEmpleado.Rol.MESERO,
                        'telefono': self.cleaned_data.get('telefono', ''),
                    },
                )
        return user


class EmpleadoEditarForm(forms.ModelForm):
    rol = forms.ChoiceField(
        choices=PerfilEmpleado.Rol.choices,
        label='Rol',
        help_text='Rol del empleado en el restaurante.',
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    telefono = forms.CharField(
        max_length=20,
        required=False,
        label='Teléfono',
        help_text='Opcional.',
        widget=forms.TextInput(
            attrs={'class': 'form-input', 'placeholder': 'Ej. 999 888 777'}
        ),
    )

    is_staff = forms.BooleanField(
        required=False,
        label='Es staff',
        help_text='Permite entrar al administrador de Django según los permisos asignados. El panel de personal depende del rol.',
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'is_active', 'is_staff')
        labels = {
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'email': 'Correo electrónico',
            'is_active': 'Activo',
        }
        widgets = {
            'first_name': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Ej. María'}
            ),
            'last_name': forms.TextInput(
                attrs={'class': 'form-input', 'placeholder': 'Ej. García'}
            ),
            'email': forms.EmailInput(
                attrs={'class': 'form-input', 'placeholder': 'ejemplo@restaurante.com'}
            ),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
        help_texts = {
            'is_active': 'Desmarca esta casilla para desactivar el acceso del empleado.',
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            duplicado = User.objects.filter(email__iexact=email).exclude(
                pk=self.instance.pk
            )
            if duplicado.exists():
                raise forms.ValidationError(
                    'Ya existe un empleado con ese correo electrónico.'
                )
        return email


class CambiarPasswordForm(SetPasswordForm):
    error_messages = {
        'password_mismatch': 'Las contraseñas no coinciden.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = 'Nueva contraseña'
        self.fields['new_password1'].widget.attrs.update(
            {
                'class': 'form-input',
                'placeholder': '••••••••••',
                'autocomplete': 'new-password',
            }
        )
        self.fields['new_password1'].help_text = (
            password_validation.password_validators_help_texts()
        )
        self.fields['new_password2'].label = 'Confirmar nueva contraseña'
        self.fields['new_password2'].widget.attrs.update(
            {
                'class': 'form-input',
                'placeholder': '••••••••••',
                'autocomplete': 'new-password',
            }
        )
        self.fields['new_password2'].help_text = ''


class CambiarUsuarioForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username',)
        labels = {
            'username': 'Nuevo usuario',
        }
        help_texts = {
            'username': 'Requerido. 150 caracteres o menos, sin espacios.',
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-input'}),
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            raise forms.ValidationError(
                'El nombre de usuario no puede estar vacío.'
            )
        duplicado = User.objects.filter(username__iexact=username).exclude(
            pk=self.instance.pk
        )
        if duplicado.exists():
            raise forms.ValidationError(
                'Ya existe un empleado con ese nombre de usuario.'
            )
        return username
