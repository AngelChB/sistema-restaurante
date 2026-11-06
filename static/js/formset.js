(function () {
    var formulario = document.querySelector('form[data-formset]');
    if (!formulario) return;
    var formset = formulario.querySelector('#detalle-formset');
    var filaVacia = document.getElementById('fila-vacia');
    var agregarBtn = document.getElementById('agregar-fila');
    var totalForms = formulario.querySelector('[name$="-TOTAL_FORMS"]');
    if (!formset || !filaVacia || !totalForms) return;
    var hayCambios = false;
    var prefix = totalForms ? totalForms.name.replace('-TOTAL_FORMS', '') : 'detalles';

    function reindexar() {
        var filas = formset.querySelectorAll('.detalle-fila');
        filas.forEach(function (fila, index) {
            fila.querySelectorAll('input, select, textarea').forEach(function (input) {
                var name = input.getAttribute('name');
                if (name) {
                    var nuevo = name.replace(new RegExp('^' + prefix + '-\\d+'), prefix + '-' + index);
                    input.setAttribute('name', nuevo);
                    input.setAttribute('id', 'id_' + nuevo.replace(/\./g, '__'));
                }
            });
            fila.querySelectorAll('label').forEach(function (label) {
                var forAttr = label.getAttribute('for');
                if (forAttr) {
                    label.setAttribute('for', forAttr.replace(new RegExp('^id_' + prefix + '-\\d+'), 'id_' + prefix + '-' + index));
                }
            });
            fila.dataset.prefix = prefix + '-' + index;
        });
        if (totalForms) {
            totalForms.value = filas.length;
        }
    }

    function nuevaFila() {
        var index = formset.querySelectorAll('.detalle-fila').length;
        var fila = filaVacia.querySelector('.detalle-fila').cloneNode(true);
        fila.querySelectorAll('input, select, textarea').forEach(function (input) {
            var name = input.getAttribute('name');
            if (name && name.indexOf('__prefix__') !== -1) {
                var nuevo = name.replace(/__prefix__/g, index);
                input.setAttribute('name', nuevo);
                input.setAttribute('id', 'id_' + nuevo.replace(/\./g, '__'));
            }
        });
        fila.querySelectorAll('label').forEach(function (label) {
            var forAttr = label.getAttribute('for');
            if (forAttr && forAttr.indexOf('__prefix__') !== -1) {
                label.setAttribute('for', forAttr.replace(/__prefix__/g, index));
            }
        });
        hayCambios = true;
        formset.appendChild(fila);
        reindexar();
    }

    function eliminarFila(fila) {
        hayCambios = true;
        var idInput = fila.querySelector('input[name$="-id"]');
        var esNueva = !idInput || idInput.value === '';
        if (esNueva) {
            fila.parentNode.removeChild(fila);
            reindexar();
        } else {
            var checkbox = fila.querySelector('input[name$="-DELETE"]');
            if (checkbox) {
                checkbox.checked = !checkbox.checked;
            }
            fila.classList.toggle('fila-marcada-eliminar', checkbox ? checkbox.checked : true);
        }
    }

    if (agregarBtn) {
        agregarBtn.addEventListener('click', nuevaFila);
    }
    if (formset) {
        formset.addEventListener('click', function (event) {
            var target = event.target;
            var boton = target && target.closest ? target.closest('.eliminar-fila') : null;
            if (boton) {
                eliminarFila(boton.closest('.detalle-fila'));
            }
        });
    }

    if (formulario) {
        formulario.addEventListener('input', function () {
            hayCambios = true;
        });
        formulario.addEventListener('change', function () {
            hayCambios = true;
        });
        formulario.addEventListener('submit', function () {
            hayCambios = false;
        });
    }
    window.addEventListener('beforeunload', function (event) {
        if (hayCambios) {
            event.preventDefault();
            event.returnValue = '';
        }
    });
})();
