(function () {
    var elementos = document.querySelectorAll('.tiempo-transcurrido');

    function calcularTiempo(timestamp) {
        var fecha = new Date(timestamp);
        var ahora = new Date();
        var segundos = Math.floor((ahora.getTime() - fecha.getTime()) / 1000);
        if (isNaN(segundos) || segundos < 0) {
            return 'hace un momento';
        }
        var minutos = Math.floor(segundos / 60);
        if (minutos < 1) {
            return 'hace menos de un minuto';
        }
        if (minutos < 60) {
            return 'hace ' + minutos + ' min';
        }
        var horas = Math.floor(minutos / 60);
        var minutosRestantes = minutos % 60;
        if (horas < 24) {
            return minutosRestantes
                ? 'hace ' + horas + ' h ' + minutosRestantes + ' min'
                : 'hace ' + horas + ' h';
        }
        var dias = Math.floor(horas / 24);
        return 'hace ' + dias + ' día' + (dias > 1 ? 's' : '');
    }

    function actualizarTiempos() {
        elementos.forEach(function (elemento) {
            var fecha = elemento.getAttribute('data-fecha');
            if (fecha) {
                elemento.textContent = calcularTiempo(fecha);
            }
        });
    }

    actualizarTiempos();
    setInterval(actualizarTiempos, 60000);
})();
