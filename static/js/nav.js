(function () {
    var toggle = document.getElementById('nav-toggle');
    var header = document.querySelector('.site-header');

    if (!toggle || !header) {
        return;
    }

    function abierto() {
        return header.classList.contains('nav-abierto');
    }

    function actualizarEstado(abrir) {
        header.classList.toggle('nav-abierto', abrir);
        toggle.setAttribute('aria-expanded', abrir ? 'true' : 'false');
        toggle.setAttribute('aria-label', abrir ? 'Cerrar menú' : 'Abrir menú');
    }

    function abrir() {
        actualizarEstado(true);
    }

    function cerrar() {
        actualizarEstado(false);
    }

    function alternar() {
        if (abierto()) {
            cerrar();
        } else {
            abrir();
        }
    }

    toggle.addEventListener('click', function () {
        alternar();
    });

    toggle.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && abierto()) {
            cerrar();
            toggle.focus();
        }
    });

    header.addEventListener('click', function (event) {
        if (abierto() && event.target.closest('a')) {
            cerrar();
        }
    });

    document.addEventListener('click', function (event) {
        if (abierto() && !header.contains(event.target)) {
            cerrar();
        }
    });
})();
