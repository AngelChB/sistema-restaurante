from django.db import connection


def bloquear_jornada(fecha):
    """Serializa cobros y cierres del día hasta terminar la transacción.

    Debe invocarse dentro de transaction.atomic(). En SQLite las pruebas
    funcionales son secuenciales; la concurrencia se prueba en PostgreSQL.
    """
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            # Espacio propio de la aplicación; segundo entero identifica el día.
            cursor.execute('SELECT pg_advisory_xact_lock(%s, %s)', [731204, fecha.toordinal()])
