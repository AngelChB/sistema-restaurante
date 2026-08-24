(function () {
    'use strict';

    var formularioPendiente = null;
    var dialogo = document.getElementById('modal-confirmar');
    var mensaje = document.getElementById('modal-confirmar-mensaje');
    var aceptar = document.getElementById('modal-confirmar-aceptar');
    var cancelar = document.getElementById('modal-confirmar-cancelar');

    function cerrarDialogo() {
        if (dialogo && dialogo.open) {
            dialogo.close();
        }
        formularioPendiente = null;
    }

    if (dialogo && aceptar && cancelar) {
        document.addEventListener('click', function (event) {
            var disparador = event.target.closest ? event.target.closest('[data-confirm]') : null;
            if (!disparador) {
                return;
            }
            var formulario = disparador.closest('form');
            if (!formulario) {
                return;
            }
            event.preventDefault();
            formularioPendiente = formulario;
            if (mensaje) {
                mensaje.textContent = disparador.getAttribute('data-confirm');
            }
            if (!dialogo.open) {
                dialogo.showModal();
            }
        });

        aceptar.addEventListener('click', function () {
            if (formularioPendiente) {
                formularioPendiente.submit();
            }
            cerrarDialogo();
        });

        cancelar.addEventListener('click', cerrarDialogo);

        dialogo.addEventListener('click', function (event) {
            if (event.target === dialogo) {
                cerrarDialogo();
            }
        });
    }

    Array.prototype.forEach.call(document.querySelectorAll('[data-dismiss]'), function (boton) {
        boton.addEventListener('click', function () {
            var bloque = boton.closest ? boton.closest('.message') : null;
            if (bloque && bloque.parentNode) {
                bloque.parentNode.removeChild(bloque);
            }
        });
    });
})();
