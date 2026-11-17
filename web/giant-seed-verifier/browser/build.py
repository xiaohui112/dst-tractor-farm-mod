#!/usr/bin/env python3
"""Build a self-contained static site runtime; never publish or change Mod files."""
from pathlib import Path
import argparse, hashlib, json, os, shutil, subprocess, sys, tarfile, tempfile

HERE=Path(__file__).resolve().parent
WEB=HERE.parent
sys.path.insert(0,str(WEB))
import runner

LUA_SHA='2640fc56a795f29d28ef15e13c34a47e223960b0240e8cb0a82d9b0738695333'
FIELDS=('good_seasons','family_min_count','family_check_dist','nutrient_consumption','nutrient_restoration')

def lua_value(v):
 if v is None:return 'nil'
 if isinstance(v,bool):return 'true'if v else'false'
 if isinstance(v,(int,float)):return repr(v)
 if isinstance(v,str):return '"'+''.join('\\%03d'%ord(c) if ord(c)<32 or c in ('"','\\') else c for c in v)+'"'
 if isinstance(v,dict):return '{'+','.join('['+lua_value(k)+']='+lua_value(x)for k,x in v.items())+'}'
 raise TypeError(type(v))

def plain(v):
 if hasattr(v,'items'):return {k:plain(x)for k,x in v.items()}
 return v

def bundle():
 # Evaluate the inspected game definitions once at build time, then ship only
 # planning fields. Visitors and CI serving the site do not need Steam files.
 _,native=runner._execute({'season':'autumn','tiles':[[0,0]],'start':[0,0],'seeds':{},'crop_order':[]})
 definitions={k:{f:plain(native.defs[k][f])for f in FIELDS}for k in runner.CROP_ORDER}
 sources={name[:-4]: (runner.MOD/'scripts'/name).read_text()for name in runner.MODULES}
 # Top-level dependency of Dynamic; intentionally not game-only Drive/Sync code.
 for name in ('aom_plan_budget',):sources[name]=(runner.MOD/'scripts'/(name+'.lua')).read_text()
 meta=runner.metadata()
 files=[{'path':'scripts/'+k+'.lua','sha256':hashlib.sha256(v.encode()).hexdigest(),'bytes':len(v.encode())}for k,v in sources.items()]
 meta.update(runtime='Lua 5.1 WebAssembly',installed_match=None,files=files,
  fingerprint=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),
  timing_basis='browser_elapsed',snapshot=True)
 import server
 data={'schema':1,'meta':meta,'definitions':definitions,
  'native_source': 'return {PLANT_DEFS='+lua_value(definitions)+'}',
  'modules':sources,'bridge':(WEB/'lua_bridge.lua').read_text(),
  'result_adapter':(HERE/'result.lua').read_text(),'presets':server.presets()}
 output=WEB/'static/runtime';output.mkdir(parents=True,exist_ok=True)
 data['adapter_hashes']={name:hashlib.sha256(data[name].encode()).hexdigest()for name in ('native_source','bridge','result_adapter')}
 data['runtime_build']=json.loads((output/'runtime-build.json').read_text())
 temporary=output/'planner-bundle.json.tmp'
 temporary.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n')
 temporary.replace(output/'planner-bundle.json')
 print('Bundled %s original Mod Lua files; %s'%(len(files),meta['fingerprint']))

def compile_runtime(emcc):
 archive=HERE/'vendor/lua-5.1.5.tar.gz'
 if hashlib.sha256(archive.read_bytes()).hexdigest()!=LUA_SHA:raise ValueError('Lua source checksum mismatch')
 with tempfile.TemporaryDirectory(prefix='tractor-lua51-')as directory:
  with tarfile.open(archive)as tar:
   for member in tar.getmembers():
    if member.name.startswith('/')or'..'in Path(member.name).parts or member.issym()or member.islnk():raise ValueError('Unsafe Lua archive')
   tar.extractall(directory)
  source=Path(directory)/'lua-5.1.5/src'
  files=[str(p)for p in sorted(source.glob('*.c'))if p.name not in ('lua.c','luac.c','print.c')]
  output=WEB/'static/runtime/lua51.mjs'
  cmd=[emcc,'-O3','-ffp-contract=off','-I'+str(source),*files,str(HERE/'lua51_host.c'),
   '-sMODULARIZE=1','-sEXPORT_ES6=1','-sENVIRONMENT=web,worker,node','-sALLOW_MEMORY_GROWTH=1',
   '-sINITIAL_MEMORY=33554432','-sMAXIMUM_MEMORY=1073741824','-sSTACK_SIZE=8388608',
   '-sEXPORTED_FUNCTIONS=["_planner_execute","_planner_failed"]','-sEXPORTED_RUNTIME_METHODS=["ccall"]',
   '-o',str(output)]
  subprocess.run(cmd,check=True)
  (output.parent/'LUA-LICENSE.txt').write_text((Path(directory)/'lua-5.1.5/COPYRIGHT').read_text())
  build={'lua':'5.1.5','lua_source_sha256':LUA_SHA,'compiler':subprocess.check_output([emcc,'--version'],text=True).splitlines()[0],
   'floating_point':'double Lua numbers; explicit float32 game query bindings; no fast-math',
   'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in (output,output.with_suffix('.wasm'))}}
  (output.parent/'runtime-build.json').write_text(json.dumps(build,indent=2)+'\n')

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--emcc',default=os.environ.get('EMCC','emcc'))
 parser.add_argument('--bundle-only',action='store_true')
 args=parser.parse_args()
 if not args.bundle_only:compile_runtime(args.emcc)
 bundle()
