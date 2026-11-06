const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/js/panel-live.js'), 'utf8');
function entorno() {
    const eventos = {}, panelEventos = {}, botonEventos = {};
    let llamadas = 0, cambios = 0, modal = false, tick;
    const panel = { querySelectorAll: () => [], contains: el => el && el.dentro,
        addEventListener: (n, f) => panelEventos[n] = f,
        replaceChildren: () => cambios++ };
    const boton = { addEventListener: (n, f) => botonEventos[n] = f, setAttribute() {} };
    const estado = {};
    const document = { getElementById: id => id === 'alternar-actualizacion' ? boton : estado, hidden: false, activeElement: null,
        querySelector: s => s === '[data-panel-live]' ? panel : s === '#alternar-actualizacion' ? boton : s === '#estado-actualizacion' ? estado : modal ? {} : null,
        addEventListener: (n, f) => eventos[n] = f };
    const contexto = { document, window: {location: {href: 'http://localhost/cocina/'}, addEventListener() {}},
        AbortController, setTimeout, clearTimeout,
        setInterval: f => tick = f,
        DOMParser: class { parseFromString() { return {querySelector: () => ({childNodes: []})}; } },
        fetch: async () => { llamadas++; return {ok: true, redirected: false, text: async () => '<div></div>'}; }
    };
    vm.runInNewContext(source, contexto);
    return { contexto, document, estado, eventos, botonEventos, panelEventos,
        tick: () => tick(), modal: v => modal = v,
        llamadas: () => llamadas, cambios: () => cambios };
}
test('actualiza el contenido cuando el panel está libre', async () => {
    const e = entorno(); await e.tick(); assert.equal(e.llamadas(), 1); assert.equal(e.cambios(), 1);
});
test('no consulta al pausar, ocultar pestaña o abrir confirmación', async () => {
    const e = entorno(); e.botonEventos.click(); await e.tick(); assert.equal(e.llamadas(), 0);
    e.botonEventos.click(); e.document.hidden = true; await e.tick(); assert.equal(e.llamadas(), 0);
    e.document.hidden = false; e.modal(true); await e.tick(); assert.equal(e.llamadas(), 0);
});
test('no reemplaza controles enfocados ni paneles con envío pendiente', async () => {
    const e = entorno(); e.document.activeElement = {dentro: true, matches: () => true};
    await e.tick(); assert.equal(e.llamadas(), 0);
    e.document.activeElement = null; e.eventos.submit(); await e.tick(); assert.equal(e.llamadas(), 0);
});
test('no reemplaza si se pausa durante la petición', async () => {
    const e = entorno(); let resolver;
    e.contexto.fetch = () => new Promise(resolve => resolver = resolve);
    const pending = e.tick(); e.botonEventos.click();
    resolver({ok: true, redirected: false, text: async () => ''}); await pending;
    assert.equal(e.cambios(), 0);
});
test('no inserta una página de login y reintenta tras un error', async () => {
    const e = entorno(); e.contexto.fetch = async () => ({ok: true, redirected: true});
    await e.tick(); assert.equal(e.cambios(), 0); assert.match(e.estado.textContent, /reintentará/);
    e.contexto.fetch = async () => ({ok: true, redirected: false, text: async () => ''});
    await e.tick(); assert.equal(e.cambios(), 1);
});
