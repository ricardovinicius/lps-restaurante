import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=readFileSync(new URL('dist/app.js',import.meta.url),'utf8');
const key='mesa-establishment-variant-v1';
const orderKey='mesa-facil-prototype-v1';
function app(storage=new Map(),area='client') {
 const nodes=new Map(), listeners={},windowListeners={};
 const node=selector=>{if(!nodes.has(selector))nodes.set(selector,{innerHTML:'',textContent:'',value:'',classList:{add(){},remove(){}}});return nodes.get(selector);};
 const document={body:{dataset:{}},querySelector:node,querySelectorAll:()=>[],addEventListener:(name,fn)=>(listeners[name]||=[]).push(fn)};
 const context=vm.createContext({document,localStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v)},sessionStorage:{getItem:()=>null,setItem(){}},location:{search:'?view='+area,href:'http://localhost:4173/?view='+area},history:{replaceState(){}},window:{addEventListener:(name,fn)=>windowListeners[name]=fn},Intl,URL,URLSearchParams,crypto:{randomUUID:()=>Math.random().toString(36)},setTimeout:()=>1,clearTimeout(){},setInterval:()=>1});
 vm.runInContext(source,context);
 const run=code=>vm.runInContext(code,context);
 const emit=(name,event)=>listeners[name]?.forEach(fn=>fn(event));
 return {run,node,storage,emit,
  click:(dataset={},id='')=>emit('click',{target:{closest:selector=>selector==='button'?{dataset,id}:null}}),
  change:target=>emit('change',{target}),
  submit:(id='checkout-form')=>emit('submit',{target:{id},preventDefault(){}}),
  sync:k=>windowListeners.storage({key:k}),
 };
}
// Defaults, legacy migration and validation.
let a=app();assert.equal(a.run('variant'),'express');assert.equal(a.run('page'),'menu');
for(const preset of ['express','delivery','salao']) {
 const old=app(new Map([[key,preset]]));assert.equal(old.run('configuredVariant()'),preset);
}
assert.equal(a.run('configErrors({}).length'),1);
assert.equal(a.run('configErrors({pickup:true,tablet:true}).length'),1);
assert.equal(a.run('configErrors({pickup:true,delivery:true,tables:true,tablet:true,tv:true}).length'),0);
// Draft isolation and saved multi-feature configuration.
const shared=new Map();const admin=app(shared,'admin');
assert.equal(admin.run('page'),'settings');
admin.click({preset:'salao'});
assert.equal(shared.has(key),false,'Preset is a draft until saved');
admin.change({dataset:{feature:'delivery'},checked:true});
admin.submit('settings-form');
assert.equal(JSON.parse(shared.get(key)).features.delivery,true);
assert.equal(JSON.parse(shared.get(key)).features.tablet,true);
assert.equal(admin.run('servicesFor(features).length'),4);
admin.change({dataset:{feature:'tables'},checked:false});
const previous=shared.get(key);admin.submit('settings-form');
assert.equal(shared.get(key),previous,'Invalid dependencies cannot be saved');
admin.click({},'discard-settings');
assert.equal(admin.run('draftFeatures.tables'),true);
// Client cannot save features or select presets.
const client=app(shared);client.run('draftFeatures={...presets.express}');client.submit('settings-form');
client.click({preset:'express'});assert.equal(shared.get(key),previous);
assert.ok(client.run('fulfillmentPicker().includes("Entrega no endereço")'));
assert.ok(!client.run('fulfillmentPicker().includes("Retirada no balcão")'));
client.change({id:'fulfillment',value:'delivery'});
client.run("cart={1:2};customer='Ana';address=''");client.submit();
assert.equal(client.run('orders.length'),0,'Delivery requires address');
client.run("address='Rua das Flores, 10'");client.submit();
assert.equal(client.run('orders[0].total'),70.8);
assert.equal(client.run('page'),'tracking');assert.equal(client.run('count()'),0);
const orderId=client.run('orders[0].id');client.click({advance:orderId});
assert.equal(client.run('orders[0].stage'),0,'Client cannot advance orders');
// Tablet, rounds, history and order snapshots.
const tablet=app(shared,'tablet');
assert.equal(tablet.run('variant'),'salao');tablet.run("table='5';cart={4:2};");tablet.submit();
assert.equal(tablet.run('orders.at(-1).total'),39.8);assert.equal(tablet.run('table'),'5');
assert.equal(tablet.run('page'),'menu');assert.ok(tablet.node('#view').innerHTML.includes('tablet-success'));
tablet.run('cart={4:1}');tablet.submit();tablet.click({page:'tablet-orders'});
assert.equal(tablet.run('tabletOrders().length'),2);
assert.ok(tablet.node('#view').innerHTML.includes('Batata da Casa'));
assert.ok(!tablet.node('#view').innerHTML.includes('Rua das Flores'));
tablet.change({id:'tablet-table',value:'12'});
assert.ok(tablet.node('#view').innerHTML.includes('A mesa ainda não fez pedidos'));
tablet.run("table='99';cart={4:1}");const total=tablet.run('orders.length');tablet.submit();
assert.equal(tablet.run('orders.length'),total);
// Counter sees every channel, delivery dispatch and TV privacy.
const counter=app(shared,'counter');
assert.ok(counter.node('#view').innerHTML.includes('Ana'));
assert.ok(counter.node('#view').innerHTML.includes('Mesa 5'));
counter.click({advance:orderId});counter.click({advance:orderId});
const tv=app(shared,'tv');assert.ok(tv.node('#view').innerHTML.includes('1001'));
assert.ok(!tv.node('#view').innerHTML.includes('Rua das Flores'));
assert.ok(!tv.node('#view').innerHTML.includes('Ana'));
counter.click({advance:orderId});tv.sync(orderKey);
assert.equal(counter.run('orders[0].dispatched'),true);
assert.ok(!tv.node('#view').innerHTML.includes('1001'));
counter.click({advance:orderId});assert.equal(counter.run('orders[0].stage'),3);
client.sync(orderKey);assert.ok(client.node('#view').innerHTML.includes('Concluído'));
// Disabling features updates all areas, preserves orders, blocks old URLs.
admin.click({preset:'express'});admin.change({dataset:{feature:'tv'},checked:false});admin.submit('settings-form');
tablet.sync(key);tv.sync(key);client.sync(key);counter.sync(key);
assert.ok(tablet.node('#view').innerHTML.includes('não está habilitado'));
assert.ok(tv.node('#view').innerHTML.includes('não está habilitado'));
assert.equal(client.run('variant'),'express');
assert.ok(counter.node('#view').innerHTML.includes('Mesa 5'),'Old-channel orders stay operable');
assert.ok(!counter.node('#view').innerHTML.includes('Abrir painel de TV'));
assert.equal(app(shared,'tablet').run('enabledRole(role)'),false);
// Pickup, unavailable products, repricing and preserved historical amounts.
client.run("page='menu';cart={4:1};customer='Carla'");client.submit();
assert.equal(client.run('orders.at(-1).total'),19.9);
shared.set('mesa-catalog-v1',JSON.stringify({4:{price:45,available:false}}));client.sync('mesa-catalog-v1');
client.run("page='menu';cart={4:1};customer='Teste'");const before=client.run('orders.length');client.submit();
assert.equal(client.run('orders.length'),before);
assert.equal(client.run('orders.at(-1).items[0].price'),19.9);
assert.equal(client.run("esc('<script>')"),'&lt;script&gt;');
console.log('Passed: migration, feature dependencies, draft/save/discard, admin restrictions, combined fulfillment, all checkouts, tablet history, mixed queue, dispatch, TV privacy, live configuration, disabled routes, persistence and price snapshots.');
