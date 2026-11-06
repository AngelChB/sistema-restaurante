const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/js/formset.js'), 'utf8');
function entorno(id) {
    const formEvents = {}, listEvents = {}, buttonEvents = {}, winEvents = {};
    function campo(name, value='') { return {name, value, checked:false, getAttribute(k){return this[k];},setAttribute(k,v){this[k]=v;}}; }
    function fila(index, saved='') {
        const inputs = [campo('detalles-'+index+'-id', saved), campo('detalles-'+index+'-cantidad'), campo('detalles-'+index+'-DELETE')];
        const label = campo(''); label.for='id_detalles-'+index+'-cantidad';
        return {inputs, label, dataset:{}, marcada:false,
            querySelectorAll(s){return s==='label' ? [label] : inputs;},
            querySelector(s){return s.includes('-DELETE') ? inputs[2] : inputs[0];},
            classList:{toggle(n,v){this.marcada=v;}},
            cloneNode(){return fila(index);}, parentNode:null};
    }
    const rows=[fila(0)]; const total={name:'detalles-TOTAL_FORMS',value:1};
    const list={querySelectorAll:()=>rows, addEventListener:(n,f)=>listEvents[n]=f,
        appendChild(f){f.parentNode=list;rows.push(f);},removeChild(f){rows.splice(rows.indexOf(f),1);}};
    rows[0].parentNode=list;
    const form={id,querySelector:s=>s==='#detalle-formset'?list:total,addEventListener:(n,f)=>formEvents[n]=f};
    const empty={querySelector:()=>fila('__prefix__')};
    const add={addEventListener:(n,f)=>buttonEvents[n]=f};
    const document={querySelector:()=>form,getElementById:id=>id==='fila-vacia'?empty:add};
    vm.runInNewContext(source,{document,window:{addEventListener:(n,f)=>winEvents[n]=f}});
    function quitar(row){listEvents.click({target:{closest:()=>({closest:()=>row})}});}
    function advierte(){let aviso=false;winEvents.beforeunload({preventDefault(){aviso=true;}});return aviso;}
    return {rows,total,buttonEvents,formEvents,quitar,advierte};
}
for (const id of ['pedido-form','compra-form']) {
    test(id+': agregar/eliminar fila conserva índices y etiquetas',()=>{
        const e=entorno(id);e.buttonEvents.click();
        assert.equal(e.rows.length,2);assert.equal(e.total.value,2);
        assert.equal(e.rows[1].inputs[1].name,'detalles-1-cantidad');
        assert.equal(e.rows[1].label.for,'id_detalles-1-cantidad');
        e.quitar(e.rows[0]);assert.equal(e.total.value,1);
        assert.equal(e.rows[0].inputs[1].name,'detalles-0-cantidad');
        assert.equal(e.rows[0].label.for,'id_detalles-0-cantidad');
    });
    test(id+': fila guardada se marca para borrar sin quitar su id',()=>{
        const e=entorno(id);e.rows[0].inputs[0].value='42';e.quitar(e.rows[0]);
        assert.equal(e.rows.length,1);assert.equal(e.rows[0].inputs[0].value,'42');
        assert.equal(e.rows[0].inputs[2].checked,true);
        e.quitar(e.rows[0]);assert.equal(e.rows[0].inputs[2].checked,false);
    });
    test(id+': cambios avisan al salir y guardar desactiva el aviso',()=>{
        const e=entorno(id);assert.equal(e.advierte(),false);
        e.buttonEvents.click();assert.equal(e.advierte(),true);
        e.formEvents.submit();assert.equal(e.advierte(),false);
        e.formEvents.change();assert.equal(e.advierte(),true);
    });
}
test('no hace nada en pantallas sin formulario dinámico',()=>{
    assert.doesNotThrow(()=>vm.runInNewContext(source,{document:{querySelector:()=>null}}));
});
