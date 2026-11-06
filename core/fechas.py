from datetime import datetime, time
from django.utils import timezone


def parsear_fecha(texto):
    if not texto:
        return None
    try:
        return datetime.strptime(texto, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def limites_fechas(fecha_desde, fecha_hasta):
    zona = timezone.get_current_timezone()
    return (
        datetime.combine(fecha_desde, time.min, tzinfo=zona),
        datetime.combine(fecha_hasta, time.max, tzinfo=zona),
    )
