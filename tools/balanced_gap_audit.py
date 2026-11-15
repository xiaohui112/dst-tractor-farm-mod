#!/usr/bin/env python3
"""Offline spatial oracle for layouts below the relaxed composition bound; never used by Mod/UI."""
import argparse,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
import seed_strategy_audit as audit

def canonical(case):
 forms=[]
 for r in range(8):
  coords=[]
  for x,z in case['tiles']:
   if r>=4:x=-x
   for _ in range(r%4):x,z=-z,x
   coords.append((x,z))
  a,b=min(x for x,z in coords),min(z for x,z in coords)
  forms.append(tuple(sorted((x-a,z-b) for x,z in coords)))
 stock=tuple(sorted((k,n) for k,n in case['stock'].items() if k in audit.RULES and case['season'] in audit.RULES[k]['seasons'] and n>=audit.RULES[k]['minimum']))
 return case['season'],min(forms),stock

def native_witness(case,points):
 # Fill the whole nine-pit board and ask the actual Mod to validate it.
 # Move a reserved center plant to the existing empty pit, preserving quantities.
 points=[dict(p) for p in points]
 for tx,tz in case['tiles']:
  selected=[p for p in points if p['cx']==tx*4 and p['cz']==tz*4]
  from collections import Counter
  counts=Counter(p['crop'] for p in selected)
  if len(selected)==8 and len(counts)==2 and set(counts.values())=={4}:
   center=next((p for p in selected if abs(p['x']-tx*4)+abs(p['z']-tz*4)<1e-8),None)
   if center:
    present={(round((p['x']-tx*4)*3/4),round((p['z']-tz*4)*3/4)) for p in selected}
    dx,dz=next((x,z) for z in (-1,0,1) for x in (-1,0,1) if (x,z) not in present)
    center.update(x=tx*4+dx*4/3,z=tz*4+dz*4/3)
 w=audit.world();L=w.lua;tiles=[];slots=[]
 for tx,tz in case['tiles']:
  tiles.append(L.table_from({'x':tx*4,'z':tz*4}))
  for row in (-1,0,1):
   for col in (-1,0,1):
    x,z=tx*4+col*4/3,tz*4+row*4/3
    crop=next((p['crop'] for p in points if abs(p['x']-x)+abs(p['z']-z)<1e-7),False)
    slots.append(L.table_from({'x':x,'z':z,'cx':tx*4,'cz':tz*4,'crop':crop}))
 board=L.table_from({'dynamic':True,'nutrient_balanced':True,'season':case['season'],'tiles':L.table_from(tiles),'slots':L.table_from(slots)})
 result=L.eval("require('aom_dynamic_farm').Validate")(board)
 return bool(result[0] if isinstance(result,tuple) else result)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--seconds',type=float,default=2);p.add_argument('--source',type=Path);args=p.parse_args()
 files=[args.source] if args.source else [ROOT/f'outputs/0.5.12-final-{n}.json' for n in ('structured','holdout','symmetry','large')]
 rows=[r for f in files for r in json.loads(f.read_text())['rows'] if r['count']<r['upper']]
 cache={};report={'scope':'Independent spatial MILP plus actual Mod validation; no witness is injected into the planner.','time_limit_per_unique_case':args.seconds,'rows':[]}
 for i,case in enumerate(rows,1):
  key=canonical(case)
  if key not in cache:
   start=time.perf_counter();r=audit.exact_oracle(case,args.seconds)
   cache[key]={'count':r.get('count',0),'proven':r.get('proven',False),'status':r.get('status'),'native_witness_valid':bool(r.get('points')) and native_witness(case,r['points']),'seconds':round(time.perf_counter()-start,3)}
  oracle=cache[key]
  report['rows'].append({'id':case['id'],'mod_count':case['count'],'relaxed_upper':case['upper'],'spatial':oracle,'better_valid_witness':oracle['native_witness_valid'] and oracle['count']>case['count'],'spatial_optimum_met':oracle['proven'] and oracle['native_witness_valid'] and oracle['count']==case['count']})
  if i%10==0 or i==len(rows):
   print(f'{i}/{len(rows)} unique={len(cache)}, better-witness={sum(r["better_valid_witness"] for r in report["rows"])}',flush=True)
   args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 report['unique_cases']=len(cache);report['complete']=True;args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
