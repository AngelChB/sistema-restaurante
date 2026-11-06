from django.core.paginator import Paginator


def paginar(request, registros, parametro='pagina'):
    # Desempatar por clave primaria mantiene el orden entre páginas.
    orden = registros.query.order_by or registros.model._meta.ordering or ('pk',)
    registros = registros.order_by(*orden, 'pk')
    pagina = Paginator(registros, 25).get_page(request.GET.get(parametro))
    filtros = request.GET.copy()

    pagina.url_anterior = ''
    if pagina.has_previous():
        filtros[parametro] = pagina.previous_page_number()
        pagina.url_anterior = '?' + filtros.urlencode()

    pagina.url_siguiente = ''
    if pagina.has_next():
        filtros[parametro] = pagina.next_page_number()
        pagina.url_siguiente = '?' + filtros.urlencode()

    return pagina
