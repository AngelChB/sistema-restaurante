(function () {
    document.querySelectorAll('.pedido-fila').forEach(function (fila) {
        fila.addEventListener('click', function (event) {
            if (event.target.closest('a, button, input, select, textarea')) {
                return;
            }
            var url = fila.getAttribute('data-url');
            if (url) {
                window.location.href = url;
            }
        });
        fila.addEventListener('keydown', function (event) {
            if (event.target.closest('a, button, input, select, textarea')) {
                return;
            }
            if (event.key === 'Enter') {
                var url = fila.getAttribute('data-url');
                if (url) {
                    window.location.href = url;
                }
            }
        });
    });
})();
