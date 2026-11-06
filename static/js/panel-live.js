(function () {
    'use strict';
    var panel = document.querySelector('[data-panel-live]');
    var boton = document.getElementById('alternar-actualizacion');
    var estado = document.getElementById('estado-actualizacion');
    if (!panel || !boton || !estado) return;
    var pausado = false;
    var enviando = false;
    var cargando = false;
    var ultimoContacto = 0;
    var controller = null;

    function ocupado() {
        return pausado || enviando || document.hidden ||
            Date.now() - ultimoContacto < 2000 ||
            !!document.querySelector('dialog[open]') ||
            (panel.contains(document.activeElement) &&
             document.activeElement.matches('a, button, input, select, textarea'));
    }

    function tiempos() {
        panel.querySelectorAll('.tiempo-transcurrido').forEach(function (elemento) {
            var minutos = Math.floor((Date.now() - new Date(elemento.dataset.fecha).getTime()) / 60000);
            if (!Number.isFinite(minutos)) return;
            elemento.textContent = minutos < 1 ? 'hace menos de un minuto' :
                minutos < 60 ? 'hace ' + minutos + ' min' :
                minutos < 1440 ? 'hace ' + Math.floor(minutos / 60) + ' h ' + minutos % 60 + ' min' :
                'hace ' + Math.floor(minutos / 1440) + ' días';
        });
    }

    boton.addEventListener('click', function () {
        pausado = !pausado;
        boton.setAttribute('aria-pressed', String(pausado));
        boton.textContent = pausado ? 'Reanudar actualización' : 'Pausar actualización';
        estado.textContent = pausado ? 'Actualización pausada.' : 'Actualización automática cada 15 segundos.';
    });
    panel.addEventListener('pointerdown', function () { ultimoContacto = Date.now(); });
    panel.addEventListener('keydown', function () { ultimoContacto = Date.now(); });
    document.addEventListener('submit', function () {
        enviando = true;
        if (controller) controller.abort();
    });
    window.addEventListener('pageshow', function () { enviando = false; });

    async function actualizar() {
        tiempos();
        if (cargando || ocupado()) return;
        cargando = true;
        controller = new AbortController();
        var timeout = setTimeout(function () { controller.abort(); }, 8000);
        try {
            var respuesta = await fetch(window.location.href, {
                credentials: 'same-origin', cache: 'no-store', signal: controller.signal
            });
            if (!respuesta.ok || respuesta.redirected) throw new Error('No disponible');
            var html = await respuesta.text();
            var nuevo = new DOMParser().parseFromString(html, 'text/html').querySelector('[data-panel-live]');
            if (!nuevo) throw new Error('Panel no disponible');
            // Revalidar: el usuario pudo comenzar una acción durante la petición.
            if (ocupado()) return;
            panel.replaceChildren.apply(panel, Array.from(nuevo.childNodes));
            tiempos();
            estado.textContent = 'Actualizado a las ' + new Date().toLocaleTimeString('es-PE') + '.';
        } catch (error) {
            if (!pausado && !enviando) estado.textContent = 'No se pudo actualizar. Se reintentará automáticamente.';
        } finally {
            clearTimeout(timeout);
            controller = null;
            cargando = false;
        }
    }
    tiempos();
    setInterval(actualizar, 15000);
})();
