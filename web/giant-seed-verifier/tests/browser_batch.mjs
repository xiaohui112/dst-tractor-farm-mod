#!/usr/bin/env node
// Node executes the browser Lua WASM engine only; this is not browser automation.
// stdin: {cases:[{id,scene}]}; stdout: one JSON event per line.
import {readFile} from 'node:fs/promises';
import {Worker, isMainThread, parentPort, workerData} from 'node:worker_threads';
import {fileURLToPath, pathToFileURL} from 'node:url';
import path from 'node:path';

const here=path.dirname(fileURLToPath(import.meta.url));
const emit=value=>process.stdout.write(JSON.stringify(value)+'\n');

if(!isMainThread){
  try{
    const bundle=JSON.parse(await readFile(workerData.bundle,'utf8'));
    const wasmBinary=new Uint8Array(await readFile(workerData.wasm));
    const {createPlanner}=await import(pathToFileURL(workerData.engine));
    const engine=await createPlanner({bundle,wasmBinary,onProgress:()=>{}});
    parentPort.on('message',({id,scene})=>{
      const started=performance.now();
      try{
        const result=engine.run(scene);
        if(result&&typeof result.then==='function')throw Error('engine.run must return synchronous JSON');
        parentPort.postMessage({type:'case',id,status:'complete',wall_ms:performance.now()-started,result});
      }catch(error){
        parentPort.postMessage({type:'case',id,status:'error',wall_ms:performance.now()-started,error:error.stack||String(error)});
      }
    });
    parentPort.postMessage({type:'ready'});
  }catch(error){parentPort.postMessage({type:'fatal',error:error.stack||String(error)});}
}else{
  const args=process.argv.slice(2);
  const options={engine:path.resolve(here,'../static/planner-engine.mjs'),bundle:path.resolve(here,'../static/runtime/planner-bundle.json'),wasm:path.resolve(here,'../static/runtime/lua51.wasm')};
  let seconds=30,worker=null;
  function exchange(message,timeoutMs){
    return new Promise(resolve=>{
      const current=worker;
      const finish=value=>{clearTimeout(timer);current.off('message',receive);current.off('error',error);current.off('exit',exited);resolve(value);};
      const receive=value=>finish(value);
      const error=value=>finish({type:'fatal',error:value.stack||String(value)});
      const exited=code=>finish({type:'fatal',error:`WASM worker exited (${code})`});
      const timer=setTimeout(()=>finish({type:'timeout'}),timeoutMs);
      current.once('message',receive);current.once('error',error);current.once('exit',exited);
      if(message)current.postMessage(message);
    });
  }
  async function stop(){if(worker){const old=worker;worker=null;await old.terminate();}}
  async function start(){
    worker=new Worker(new URL(import.meta.url),{workerData:options,stdout:true,stderr:true});
    worker.stdout.pipe(process.stderr);worker.stderr.pipe(process.stderr);
    const ready=await exchange(null,Math.max(60,seconds)*1000);
    if(ready.type!=='ready'){await stop();throw Error(ready.error||'WASM initialization timed out');}
  }
  try{
    for(let i=0;i<args.length;i++){
      const key=args[i];
      if(key==='--case-seconds')seconds=Number(args[++i]);
      else if(['--engine','--bundle','--wasm'].includes(key))options[key.slice(2)]=path.resolve(args[++i]);
      else throw Error(`Unknown argument: ${key}`);
    }
    if(!Number.isFinite(seconds)||seconds<=0)throw Error('--case-seconds must be positive');
    let raw='';for await(const part of process.stdin)raw+=part;
    const payload=JSON.parse(raw),cases=Array.isArray(payload)?payload:payload.cases;
    if(!Array.isArray(cases))throw Error('Expected {cases:[{id,scene}]}');
    const ids=new Set();for(const item of cases){if(typeof item.id!=='string'||ids.has(item.id)||!item.scene)throw Error('Cases need unique IDs and scenes');ids.add(item.id);}
    let incomplete=0,errors=0;
    for(const item of cases){
      if(!worker)await start();
      const started=performance.now();
      const event=await exchange(item,seconds*1000);
      if(event.type==='timeout'){
        emit({type:'case',id:item.id,status:'incomplete',wall_ms:performance.now()-started,error:`WASM exceeded ${seconds}s; worker terminated`});
        incomplete++;await stop();
      }else if(event.type==='fatal'){
        emit({type:'case',id:item.id,status:'error',wall_ms:performance.now()-started,error:event.error});
        errors++;await stop();
      }else{
        if(event.type!=='case'||event.id!==item.id)throw Error('Unexpected worker response');
        emit(event);if(event.status!=='complete')errors++;
      }
    }
    await stop();emit({type:'summary',total:cases.length,incomplete,errors});
    process.exitCode=errors?1:incomplete?2:0;
  }catch(error){await stop();emit({type:'fatal',error:error.stack||String(error)});process.exitCode=1;}
}
