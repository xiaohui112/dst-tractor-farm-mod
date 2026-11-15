#!/usr/bin/env python3
"""Seed-layout audit: actual native rules, independent upper bounds and spatial checks.
Run explicitly; the optional SciPy MILP oracle is offline development tooling only.
"""
from pathlib import Path
from collections import Counter, deque
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse, csv, hashlib, itertools, json, math, random, re, sys, time
from functools import lru_cache
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from zipfile import ZipFile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/tests'))
import test_giant_farming as giant

SHAPES={
 'single':[(0,0)], 'horizontal-2':[(i,0) for i in range(2)],
 'vertical-2':[(0,i) for i in range(2)], 'horizontal-5':[(i,0) for i in range(5)],
 'vertical-5':[(0,i) for i in range(5)], 'L-3':[(0,0),(1,0),(1,1)],
 'T-4':[(0,0),(1,0),(2,0),(1,1)], 'S-4':[(0,0),(1,0),(1,1),(2,1)],
 'U-5':[(0,0),(0,1),(1,1),(2,1),(2,0)],
 'plus-5':[(1,0),(0,1),(1,1),(2,1),(1,2)],
 'ring-8':[(x,z) for z in range(3) for x in range(3) if (x,z)!=(1,1)],
 'notch-8':[(x,z) for z in range(3) for x in range(3) if (x,z)!=(2,2)],
 'bridge-7':[(0,0),(0,1),(1,0),(2,0),(3,0),(3,1),(4,0)],
 'snake-7':[(0,0),(1,0),(1,1),(2,1),(2,2),(3,2),(3,3)],
 'comb-9':[(x,0) for x in range(5)]+[(0,1),(2,1),(4,1),(4,2)],
 'square-9':[(x,z) for z in range(3) for x in range(3)],
}
GAME=Path.home()/"Library/Application Support/Steam/steamapps/common/Don't Starve Together/dontstarve_steam.app/Contents/data/databundles/scripts.zip"

def native_sources():
 with ZipFile(GAME) as z:
  source=z.read('scripts/prefabs/farm_plant_defs.lua').decode();tuning=z.read('scripts/tuning.lua').decode()
 constants={}
 for name in ('FARM_PLANT_SAME_FAMILY_MIN','FARM_PLANT_SAME_FAMILY_RADIUS','FARM_TILL_SPACING','FARM_PANT_OVERCROWDING_MAX_PLANTS','FARM_PLANT_CONSUME_NUTRIENT_LOW','FARM_PLANT_CONSUME_NUTRIENT_MED','FARM_PLANT_CONSUME_NUTRIENT_HIGH'):
  constants[name]=float(re.search(r'\b'+name+r'\s*=\s*([\d.]+)',tuning).group(1))
 return source,constants
NATIVE,CONSTANTS=native_sources()

def world(source_dir=None):
 w=giant.World();L=w.lua;L.globals().NATIVE_SOURCE=NATIVE
 L.globals().NATIVE_CONSTANTS=L.table_from(CONSTANTS)
 L.execute('''
local env=setmetatable({TUNING=setmetatable(NATIVE_CONSTANTS,{__index=function()return 1 end}),FRAMES=1/30},{__index=_G})
local f=assert(loadstring(NATIVE_SOURCE));setfenv(f,env);DEFS=f().PLANT_DEFS
TUNING.FARM_TILL_SPACING=NATIVE_CONSTANTS.FARM_TILL_SPACING
TUNING.FARM_PANT_OVERCROWDING_MAX_PLANTS=NATIVE_CONSTANTS.FARM_PANT_OVERCROWDING_MAX_PLANTS
''')
 if source_dir:
  L.globals().AUDIT_SCRIPTS=str(source_dir)
  L.execute("package.path=AUDIT_SCRIPTS..'/?.lua;'..package.path;package.loaded.aom_seed_layout=nil;package.loaded.aom_dynamic_farm=nil")
 return w

def rules():
 w=world();out={}
 for k,d in w.lua.globals().DEFS.items():
  if not d.good_seasons or k=='randomseed':continue
  consume=[d.nutrient_consumption[i] or 0 for i in (1,2,3)]
  restore=[i for i in (1,2,3) if d.nutrient_restoration[i]]
  per=sum(consume)/len(restore)
  out[k]={'minimum':int(d.family_min_count),'radius':d.family_check_dist,'seasons':list(d.good_seasons.keys()),'net':[int((per if i+1 in restore else 0)-v) for i,v in enumerate(consume)]}
 return out
RULES=rules()

def cases():
 out=[]
 for season in ('autumn','winter','spring','summer'):
  crops=[k for k in giant.CONSUME if season in RULES[k]['seasons']]
  for shape,coords in SHAPES.items():
   cap=len(coords)*9
   profiles=[('equal-two',[cap,cap]),('three-min',[4]*3),('three-tails',[5]*3),('four-min',[4]*4),('uneven',[4,5,7,11]),('thresholds',[3,4,3,9]),('user-tails',[7,7,24,17]),('all-season',[4]*len(crops)),('five-tails',[5]*5),('six-seven',[7]*6),('all-six',[6]*len(crops)),('four-season-stock',[4]*len(giant.CONSUME))]
   for name,quantities in profiles:
    stock=dict(zip(giant.CONSUME if name=='four-season-stock' else crops,quantities))
    if name!='four-season-stock':stock['randomseed']=40
    out.append({'id':season+'/'+shape+'/'+name,'season':season,'shape':shape,'tiles':coords,'stock':stock})
  # Every same-season species pair, with unequal tails and just enough stock.
  for i,(a,b) in enumerate(itertools.combinations(crops,2)):
   out.append({'id':season+'/pair/'+a+'-'+b,'season':season,'shape':'L-3','tiles':SHAPES['L-3'],'stock':{a:4+i%4,b:5+(i*3)%7}})
 return out

def holdout_cases(count=240):
 rng=random.Random(4217849);out=[]
 for i in range(count):
  season=('autumn','winter','spring','summer')[i%4]
  size=rng.choice((2,3,4,5,7,9,12,16,20));tiles={(0,0)}
  while len(tiles)<size:
   x,z=rng.choice(sorted(tiles));dx,dz=rng.choice(((1,0),(-1,0),(0,1),(0,-1)));tiles.add((x+dx,z+dz))
  minx,minz=min(x for x,z in tiles),min(z for x,z in tiles)
  tiles=sorted((x-minx,z-minz) for x,z in tiles)
  crops=[k for k in giant.CONSUME if season in RULES[k]['seasons']]
  rng.shuffle(crops);crops=crops[:rng.randint(1,len(crops))]
  stock={k:rng.choice((0,1,3,4,4,5,6,7,8,9,10,11,13,17,24,40)) for k in crops}
  out.append({'id':f'holdout-{i:03d}/{season}','season':season,'shape':'generated-connected','tiles':tiles,'stock':stock})
 return out

def symmetry_cases():
 out=[]
 for case in cases():
  if case['shape'] not in ('T-4','U-5','ring-8','snake-7') or case['id'].split('/')[-1] not in ('all-season','six-seven','user-tails'):continue
  for rotation in range(8):
   coords=[]
   for x,z in case['tiles']:
    if rotation>=4:x=-x
    for _ in range(rotation%4):x,z=-z,x
    coords.append((x,z))
   minx,minz=min(x for x,z in coords),min(z for x,z in coords)
   coords=sorted((x-minx,z-minz) for x,z in coords)
   out.append({**case,'id':case['id']+f'/D4-{rotation}','tiles':coords})
 return out

@lru_cache(maxsize=4)
def balanced_patterns(season):
 # Python exhaustive multisets, independent of Mod's Lua enumeration/search.
 crops=tuple(k for k in giant.CONSUME if season in RULES[k]['seasons']);out=[]
 for n in range(1,10):
  for combination in itertools.combinations_with_replacement(range(len(crops)),n):
   if all(sum(RULES[crops[i]]['net'][j] for i in combination)==0 for j in range(3)):
    c=Counter(combination);out.append(tuple(c.get(i,0) for i in range(len(crops))))
 return crops,tuple(out)

@lru_cache(maxsize=4096)
def _balanced_upper(stock_key,season,tiles):
 stock=dict(stock_key);crops,patterns=balanced_patterns(season)
 patterns=[p for p in patterns if all(n<=stock.get(k,0) and (n==0 or stock[k]>=RULES[k]['minimum']) for k,n in zip(crops,p))]
 if not patterns:return {'upper':0,'witness':0,'proven':True}
 if tiles==1:
  n=max([0]+[sum(p) for p in patterns if all(n==0 or n>=RULES[k]['minimum'] for k,n in zip(crops,p))]);return {'upper':n,'witness':n,'proven':True}
 import numpy as np
 from scipy.optimize import Bounds,LinearConstraint,milp
 # Integer variables count each tile's composition, plus binary species-use flags.
 P,K=len(patterns),len(crops);mat=[];lo=[];hi=[]
 mat.append([1]*P+[0]*K);lo.append(0);hi.append(tiles)
 for i,k in enumerate(crops):
  for amount,lower,upper in ((stock.get(k,0),-np.inf,0),(RULES[k]['minimum'],0,np.inf)):
   row=[p[i] for p in patterns]+[0]*K;row[P+i]=-amount;mat.append(row);lo.append(lower);hi.append(upper)
 objective=[-sum(p) for p in patterns]+[0]*K
 r=milp(np.array(objective,dtype=float),integrality=np.ones(P+K),bounds=Bounds(np.zeros(P+K),np.r_[np.full(P,tiles),np.ones(K)]),constraints=LinearConstraint(np.array(mat),np.array(lo),np.array(hi)),options={'time_limit':2,'mip_rel_gap':0})
 witness=round(-r.fun) if r.x is not None else 0
 bound=getattr(r,'mip_dual_bound',None)
 upper=round(-r.fun) if r.status==0 else min(tiles*9,math.floor(-bound+1e-6)) if bound is not None and math.isfinite(bound) else tiles*9
 return {'upper':upper,'witness':witness,'proven':r.status==0}

def large_cases():
 grid=lambda missing=None:[(x,z) for z in range(8) for x in range(8) if (x,z)!=missing]
 return [
  {'id':'large/autumn-63','season':'autumn','shape':'grid-minus-corner','tiles':grid((7,7)),'stock':{'carrot':189,'corn':189,'potato':189}},
  {'id':'large/autumn-64','season':'autumn','shape':'grid','tiles':grid(),'stock':{'carrot':192,'corn':192,'potato':192}},
  {'id':'large/winter-64','season':'winter','shape':'grid','tiles':grid(),'stock':{'carrot':192,'asparagus':192,'potato':192}},
  {'id':'large/summer-64','season':'summer','shape':'grid','tiles':grid(),'stock':{'onion':192,'garlic':192,'pepper':192}},
  {'id':'large/paired-64','season':'autumn','shape':'grid','tiles':grid(),'stock':{'tomato':300,'potato':300}},
  {'id':'large/inner-hole-63','season':'spring','shape':'inner-hole','tiles':grid((3,3)),'stock':{'carrot':189,'corn':189,'potato':189}},
 ]

def all_balanced_cases():
 suites=(('structured',cases()),('holdout',holdout_cases(120)),('symmetry',[c for c in symmetry_cases() if '/all-season/' in c['id']]),('large',large_cases()))
 return [{**case,'suite':name} for name,rows in suites for case in rows]

def upper_bound(stock,season,capacity):
 return _balanced_upper(tuple(sorted(stock.items())),season,capacity//9)['upper'],0

def independent_check(case,points):
 errors=[];counts=Counter(p['crop'] for p in points if p['crop']);planted=[p for p in points if p['crop']]
 tiles=set(map(tuple,case['tiles']))
 for k,n in counts.items():
  if k not in RULES or case['season'] not in RULES[k]['seasons']:errors.append('season')
  if n>case['stock'].get(k,0):errors.append('stock')
 for tx,tz in tiles:
  net=[sum(RULES[p['crop']]['net'][j] for p in planted if p['cx']==tx*4 and p['cz']==tz*4) for j in range(3)]
  if any(net):errors.append('nutrient-balance')
 family_cost=0.;components=0
 for p in planted:
  if (p['cx']/4,p['cz']/4) not in tiles:errors.append('outside')
  distances=[(p['x']-q['x'])**2+(p['z']-q['z'])**2 for q in planted if p['crop']==q['crop']]
  if sum(d<=RULES[p['crop']]['radius']**2+1e-8 for d in distances)<RULES[p['crop']]['minimum']:errors.append('family')
  ds=sorted(d for d in distances if d>1e-10);family_cost+=sum(ds[:3])
 for i,p in enumerate(planted):
  for q in planted[:i]:
   if (p['x']-q['x'])**2+(p['z']-q['z'])**2<=CONSTANTS['FARM_TILL_SPACING']**2:errors.append('spacing')
 for k in counts:
  remaining={i for i,p in enumerate(planted) if p['crop']==k}
  while remaining:
   components+=1;todo=[remaining.pop()]
   for i in todo:
    near=[j for j in remaining if (planted[i]['x']-planted[j]['x'])**2+(planted[i]['z']-planted[j]['z'])**2<=2*(4/3)**2+1e-8]
    remaining.difference_update(near);todo.extend(near)
 return sorted(set(errors)),{'count':len(planted),'kinds':len(counts),'used':dict(counts),'nearest_three_distance_sum':family_cost,'family_components':components}

def run_case(case,source_dir=None,recheck=False,case_seconds=None):
 w=world(source_dir);L=w.lua;L.globals().inst=w.make(case['stock'],case['season'])
 L.execute("inst.components.container.numslots=15;inst._attachment_type='seeder';TheWorld.components.farming_manager.GetTileNutrients=function()error('unexpected nutrient read')end;D=require('aom_dynamic_farm')")
 for x,z in case['tiles']:
  for dx in (-1,0,1):
   for dz in (-1,0,1):L.globals().SpawnPrefab('farm_soil').Transform.SetPosition(None,x*4+dx*4/3,0,z*4+dz*4/3)
 x,z=case['tiles'][0];start=time.perf_counter()
 if case_seconds:
  def guard():
   if time.perf_counter()-start>case_seconds:raise TimeoutError('case search exceeded '+str(case_seconds)+' seconds')
  L.globals().D._yield=guard
 try:result=L.globals().D.Build(L.globals().inst,x*4,z*4)
 except TimeoutError:
  packing=L.eval("require('aom_seed_packing')");timings=packing.Timings();proof=packing.last_report
  proven=bool(proof and proof.optimal)
  progress=L.eval("package.loaded.aom_seed_exact and package.loaded.aom_seed_exact.progress")
  return {**case,'errors':['timeout'],'elapsed_seconds':round(time.perf_counter()-start,5),'count':None,'upper':None,'incomplete':True,'incomplete_phase':packing.phase or 'scan','maximum_proven':proven,'maximum_quantity_count':proof.total if proven else None,'proven_upper':proof.upper if proven else None,'runtime_progress':dict(progress.items()) if progress else None,'timings':{k:timings[k] for k in ('quantity_seconds','arrangement_seconds','quantity_complete','arrangement_complete','basis')}}
 finally:L.globals().D._yield=None
 b,why=result if isinstance(result,tuple) else (result,None)
 elapsed=time.perf_counter()-start
 points=[{k:p[k] for k in ('x','z','cx','cz','crop')} for p in b.slots.values()] if b else []
 errors,metrics=independent_check(case,points)
 upper,kinds=upper_bound(case['stock'],case['season'],len(case['tiles'])*9)
 oracle=_balanced_upper(tuple(sorted(case['stock'].items())),case['season'],len(case['tiles']))
 row={**case,**metrics,'upper':upper,'composition_oracle':oracle,'kinds_upper':kinds,'errors':errors,'reason':why,'elapsed_seconds':round(elapsed,5),'points':points}
 construction=L.eval("require('aom_seed_packing').last_report")
 if construction:
  if not b and (construction.total or 0)>0:row['errors'].append('valid-plan-missing')
  if b and (not construction.optimal or construction.upper!=b.total):row['errors'].append('maximum-not-proved')
  row['timings']={'quantity_seconds':construction.quantity_seconds,'arrangement_seconds':construction.arrangement_seconds,'quantity_complete':True,'arrangement_complete':True,'basis':'process_cpu'}
  row['maximum_proven']=bool(construction.optimal);row['maximum_quantity_count']=construction.total;row['proven_upper']=construction.upper;row['quantity_nodes']=construction.nodes
 if b:
  if b.total!=row['count']:row['errors'].append('reported-count')
  row['arrangement']={k:b.arrangement[k] for k in ('trials','moves','passes','limited')}
  row['arrangement'].update(before=b.arrangement.before.score,after=b.arrangement.after.score)
  if recheck:
   L.globals().b=b
   L.execute("local A=require('aom_seed_layout');local board={};for i,p in ipairs(b.slots) do board[i]=p.crop or false end;local geometry=A.Geometry(b.tiles,b.slots,DEFS);_,second=A.Regularize(board,geometry)")
   row['second_arrangement_score']=L.globals().second.after.score
 return row

def write_timing_artifacts(report,output):
 """Separate successful timings from interrupted lower bounds; never count a timeout as zero."""
 rows=report['rows'];complete=[r for r in rows if not r.get('incomplete') and not r['errors'] and r.get('maximum_proven')]
 def stats(subset,key):
  values=sorted(r['timings'][key] for r in subset if r.get('timings') and r['timings'].get(key) is not None)
  if not values:return {'samples':0}
  def percentile(p):
   at=(len(values)-1)*p;lo=math.floor(at);hi=math.ceil(at)
   return values[lo]+(values[hi]-values[lo])*(at-lo)
  return {'samples':len(values),'total_seconds':sum(values),'p50_seconds':percentile(.5),'p95_seconds':percentile(.95),'max_seconds':values[-1]}
 summary={'basis':'process_cpu','cases':len(rows),'passed':len(complete),'incomplete':sum(bool(r.get('incomplete')) for r in rows),'failed':sum(bool(r['errors']) and not r.get('incomplete') for r in rows),'source_sha256':report['source_sha256']}
 summary['run_complete']=bool(report.get('completed_at'))
 summary['incomplete_by_phase']=dict(Counter(r.get('incomplete_phase','unknown') for r in rows if r.get('incomplete')))
 for name,subset in [('all_completed',complete),('positive_completed',[r for r in complete if r['count']>0])]:
  summary[name]={key:stats(subset,key) for key in ('quantity_seconds','arrangement_seconds')}
 summary['each_completed_phase']={key:stats([r for r in rows if r.get('timings',{}).get(flag)],key) for key,flag in [('quantity_seconds','quantity_complete'),('arrangement_seconds','arrangement_complete')]}
 summary['incomplete_cases']=[{'id':r['id'],'phase':r.get('incomplete_phase'),'timings':r.get('timings'),'elapsed_seconds':r['elapsed_seconds']} for r in rows if r.get('incomplete')]
 report['timing_summary']=summary
 with output.with_suffix('.timings.csv').open('w',newline='',encoding='utf-8-sig') as f:
  writer=csv.writer(f);writer.writerow(['case','season','tiles','status','maximum_plants','proven_upper','maximum_quantity_seconds','arrangement_seconds','quantity_complete','arrangement_complete','wall_seconds','timing_basis','case_wall_budget_seconds'])
  for r in rows:
   t=r.get('timings',{});writer.writerow([r['id'],r['season'],len(r['tiles']),'incomplete' if r.get('incomplete') else 'failed' if r['errors'] else 'passed',r.get('maximum_quantity_count',r.get('count')),r.get('proven_upper'),t.get('quantity_seconds'),t.get('arrangement_seconds'),t.get('quantity_complete'),t.get('arrangement_complete'),r['elapsed_seconds'],t.get('basis'),r.get('case_wall_budget_seconds',report.get('case_wall_budget_seconds'))])
 output.with_suffix('.timing-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')

def exact_oracle(case,time_limit=2):
 import numpy as np
 from scipy.optimize import Bounds,LinearConstraint,milp
 from scipy.sparse import coo_matrix
 crops=[k for k,n in case['stock'].items() if k in RULES and case['season'] in RULES[k]['seasons'] and n>=RULES[k]['minimum']]
 points=[(x*4+dx*4/3,z*4+dz*4/3) for x,z in case['tiles'] for dz in (-1,0,1) for dx in (-1,0,1)]
 P,K=len(points),len(crops);V=P*K+K
 if not K:return {'count':0,'kinds':0,'proven':True,'points':[]}
 rr=[];cc=[];vv=[];lo=[];hi=[]
 def row(terms,lower,upper):
  i=len(lo)
  for j,v in terms:rr.append(i);cc.append(j);vv.append(v)
  lo.append(lower);hi.append(upper)
 for p in range(P):row([(p*K+k,1) for k in range(K)],0,1)
 for k,crop in enumerate(crops):
  y=P*K+k;stock=min(case['stock'][crop],P);m=RULES[crop]['minimum']
  row([(p*K+k,1) for p in range(P)]+[(y,-stock)],-np.inf,0)
  row([(p*K+k,1) for p in range(P)]+[(y,-m)],0,np.inf)
  radius=RULES[crop]['radius']**2
  for p,(x,z) in enumerate(points):
   near=[q for q,(xx,zz) in enumerate(points) if (x-xx)**2+(z-zz)**2<=radius]
   row([(q*K+k,1-m if q==p else 1) for q in near],0,np.inf)
 for t in range(len(case['tiles'])):
  for j in range(3):row([(p*K+k,RULES[crop]['net'][j]) for p in range(t*9,(t+1)*9) for k,crop in enumerate(crops)],0,0)
 mat=coo_matrix((vv,(rr,cc)),shape=(len(lo),V)).tocsc()
 c=np.r_[np.full(P*K,-1),np.zeros(K)]
 result=milp(c,integrality=np.ones(V),bounds=Bounds(np.zeros(V),np.ones(V)),constraints=LinearConstraint(mat,np.array(lo),np.array(hi)),options={'time_limit':time_limit,'mip_rel_gap':0})
 if result.x is None:return {'proven':False,'status':result.message}
 selected=[]
 for p,(x,z) in enumerate(points):
  for k,crop in enumerate(crops):
   if result.x[p*K+k]>.5:
    tx,tz=case['tiles'][p//9];selected.append({'x':x,'z':z,'cx':tx*4,'cz':tz*4,'crop':crop})
 errors,metrics=independent_check(case,selected)
 assert not errors,errors
 return {**metrics,'proven':result.status==0,'status':result.message,'points':selected}

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--source',type=Path);parser.add_argument('--oracle',action='store_true');parser.add_argument('--limit',type=int);parser.add_argument('--only');parser.add_argument('--jobs',type=int,default=1);parser.add_argument('--case-seconds',type=float);parser.add_argument('--recheck',action='store_true');parser.add_argument('--suite',choices=('structured','holdout','symmetry','large','all'),default='structured');args=parser.parse_args()
 selected=[c for c in {'structured':cases,'holdout':holdout_cases,'symmetry':symmetry_cases,'large':large_cases,'all':all_balanced_cases}[args.suite]() if not args.only or args.only in c['id']]
 if args.limit:selected=selected[:args.limit]
 source=args.source or ROOT/'mod/Tractor/scripts'
 def hashes():return {name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in ('aom_dynamic_farm.lua','aom_seed_layout.lua','aom_seed_packing.lua','aom_seed_balance.lua','aom_seed_exact.lua','aom_seed_heuristic.lua','aom_seed_feasible.lua') if (source/name).exists()}
 initial=hashes()
 report={'source_sha256':initial,'native_rules_sha256':hashlib.sha256(NATIVE.encode()).hexdigest(),'native_constants':CONSTANTS,'rules':RULES,'started_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'source':str(source),'case_wall_budget_seconds':args.case_seconds,'rows':[]}
 args.output.parent.mkdir(parents=True,exist_ok=True)
 pool=ProcessPoolExecutor(max_workers=max(1,min(args.jobs,8)),mp_context=get_context('spawn')) if args.jobs>1 else None
 results=pool.map(run_case,selected,itertools.repeat(args.source),itertools.repeat(args.recheck),itertools.repeat(args.case_seconds),chunksize=1) if pool else (run_case(case,args.source,args.recheck,args.case_seconds) for case in selected)
 for i,row in enumerate(results,1):
  case=selected[i-1]
  if args.oracle and not row.get('incomplete') and (row['count']<row['upper'] or row['kinds']<row['kinds_upper']):row['oracle']=exact_oracle(case)
  report['rows'].append(row)
  if i%20==0 or i==len(selected):
   bad=sum(not r.get('incomplete') and r['count']<r['upper'] for r in report['rows']);invalid=sum(bool(r['errors']) and not r.get('incomplete') for r in report['rows']);unfinished=sum(bool(r.get('incomplete')) for r in report['rows'])
   print(f'{i}/{len(selected)} below-balanced-composition-bound={bad}, invalid={invalid}, incomplete={unfinished}',flush=True)
   write_timing_artifacts(report,args.output);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 if pool:pool.shutdown()
 assert hashes()==initial,'Planner source changed during the audit'
 report['completed_at']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat();write_timing_artifacts(report,args.output);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
