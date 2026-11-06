from django import forms
from django.contrib import messages


def filtro_id(request, nombre):
    valor = request.GET.get(nombre, '').strip()
    if not valor:
        return ''
    try:
        # Los identificadores BigAutoField usan enteros de 64 bits con signo.
        numero = forms.IntegerField(min_value=1, max_value=9223372036854775807).clean(
            valor
        )
    except forms.ValidationError:
        messages.error(
            request, f'El filtro {nombre} debe ser un identificador positivo válido.'
        )
        return ''
    return str(numero)


def filtro_fecha(request, nombre):
    valor = request.GET.get(nombre, '').strip()
    if not valor:
        return ''
    try:
        fecha = forms.DateField(input_formats=['%Y-%m-%d']).clean(valor)
    except forms.ValidationError:
        messages.error(
            request, f'El filtro {nombre} debe tener una fecha válida (AAAA-MM-DD).'
        )
        return ''
    return fecha.isoformat()
