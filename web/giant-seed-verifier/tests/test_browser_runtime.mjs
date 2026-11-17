import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';
import {createPlanner,normalize} from '../static/planner-engine.mjs';
import lua51 from '../static/runtime/lua51.mjs';

const bundle=JSON.parse(await fs.readFile(new URL('../static/runtime/planner-bundle.json',import.meta.url)));
const wasmBinary=await fs.readFile(new URL('../static/runtime/lua51.wasm',import.meta.url));
test('actual Lua 5.1 APIs, coroutines and float32 boundary math survive WASM compilation',async()=>{
 const runtime=await lua51({wasmBinary});
 const text=runtime.ccall('planner_execute','string',['string'],[`
 assert(_VERSION=='Lua 5.1')
 local f=assert(loadstring('return value'));setfenv(f,{value=42});assert(f()==42)
 local co=coroutine.create(function()coroutine.yield(7);return 9 end)
 local ok,n=coroutine.resume(co);assert(ok and n==7)
 ok,n=coroutine.resume(co);assert(ok and n==9 and coroutine.status(co)=='dead')
 assert(PY_F32(16777217)==16777216)
 assert(PY_DISTANCE_SQ(0,0,0,4,0,0)==PY_RADIUS_SQ(4))
 assert(PY_DISTANCE_SQ(0,0,0,4.000001,0,0)>PY_RADIUS_SQ(4))
 return 'ok'`]);
 assert.equal(runtime.ccall('planner_failed','number',[],[]),0,text);assert.equal(text,'ok');
});
test('invalid inputs fail before planning',()=>{
 for(const input of [null,[],{width:true},{width:null},{season:null},{strategy:'bad'},{seeds:null},{seeds:{tomato:null}},{seeds:{tomato:1.5}},{seeds:{unknown:4}},{tiles:[]},{tiles:[[0,0],[0,0]]},{start:[4,4]}]){
  assert.throws(()=>normalize(input,bundle.meta),undefined,JSON.stringify(input));
 }
});
test('tampered Lua and mismatched runtime are rejected',async()=>{
 const changed=structuredClone(bundle);changed.modules.aom_seed_layout+='\n-- changed';
 await assert.rejects(createPlanner({bundle:changed,wasmBinary}),/源码快照校验失败/);
 const bad=Uint8Array.from(wasmBinary);bad[0]^=1;
 await assert.rejects(createPlanner({bundle,wasmBinary:bad}),/运行时版本/);
});
test('both native Mod entry points execute in a fresh Lua state per run',async()=>{
 const engine=await createPlanner({bundle,wasmBinary});
 for(const strategy of ['GIANT_TEMPLATE','GIANT']){
  const result=engine.run({strategy,seeds:{tomato:40,potato:40}});
  assert.equal(result.count,32);assert.equal(result.checks.family_passed,32);
  assert.equal(result.timings.basis,'browser_elapsed');assert.equal(result.remaining.tomato,24);
  assert.equal(result.slots.filter(p=>p.crop===false).length,4,'empty pits retain the native false representation');
  assert.equal(result.optimal,strategy==='GIANT');
 }
 assert.equal(engine.run({seeds:{}}).count,0);
});

async function clientHarness(){
 const workers=[];let release;
 const pending=new Promise(resolve=>release=resolve);
 class Worker{
  constructor(){this.terminated=false;workers.push(this);}
  postMessage(data){this.data=data;}
  terminate(){this.terminated=true;}
 }
 const context={window:{},document:{currentScript:{src:'http://localhost/sub/browser-client.js'}},URL,DOMException,structuredClone,performance,Worker,
  fetch:()=>pending,setInterval,clearInterval};
 vm.runInNewContext(await fs.readFile(new URL('../static/browser-client.js',import.meta.url),'utf8'),context);
 return {client:context.window.BrowserPlanner,workers,release:()=>release({ok:true,json:async()=>bundle})};
}
test('cancel while bundle loads never starts a stale worker',async()=>{
 const h=await clientHarness(),first=h.client.start({});const rejected=assert.rejects(first,{name:'AbortError'});
 h.client.cancel();h.release();await rejected;assert.equal(h.workers.length,0);
});
test('replacing a task terminates it and late replies cannot overwrite the new task',async()=>{
 const h=await clientHarness();h.release();await h.client.metadata();
 const first=h.client.start({width:1});await new Promise(resolve=>setImmediate(resolve));
 const rejected=assert.rejects(first,{name:'AbortError'}),second=h.client.start({width:2});
 await new Promise(resolve=>setImmediate(resolve));await rejected;
 assert.equal(h.workers[0].terminated,true);
 h.workers[0].onmessage({data:{type:'result',result:'stale'}});
 h.workers[1].onmessage({data:{type:'result',result:'current'}});
 assert.equal(await second,'current');assert.equal(h.workers[1].terminated,true);
});
