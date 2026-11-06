from django.core.paginator import Paginator


def paginar(request, registros, parametro='pagina'):
    # Un desempate por clave primaria evita saltos entre filas con igual fecha/nombre.
    orden = registros.query.order_by or registros.model._meta.ordering or ('pk',)
    registros = registros.order_by(*orden, 'pk')
    pagina = Paginator(registros, 25).get_page(request.GET.get(parametro))
    filtros = request.GET.copy()
    filtros.pop(parametro, None)
    base = filtros.urlencode()
    pagina.url_anterior = ('?' + base + ('&' if base else '') + parametro + '=' + str(pagina.previous_page_number())) if pagina.has_previous() else ''
    pagina.url_siguiente = ('?' + base + ('&' if base else '') + parametro + '=' + str(pagina.next_page_number())) if pagina.has_next() else ''
    return pagina
