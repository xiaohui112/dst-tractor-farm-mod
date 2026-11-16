#!/usr/bin/env python3
"""编译固定格子；原图只允许OR替换，程序扩展在构建时枚举合法配比。"""
import argparse, hashlib, itertools, json
from collections import Counter
from pathlib import Path
from seed_strategy_audit import RULES, CONSTANTS
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'docs/template-catalog/catalog.json'
TARGET=ROOT/'mod/Tractor/scripts/aom_seed_catalog.lua'
def lua(v):
 if v is None:return 'nil'
 if isinstance(v,bool):return 'true' if v else 'false'
 if isinstance(v,(int,float)):return str(v)
 if isinstance(v,str):return json.dumps(v,ensure_ascii=False)
 if isinstance(v,list):return '{'+','.join(map(lua,v))+'}'
 return '{'+','.join('['+lua(k)+']='+lua(x) for k,x in sorted(v.items()))+'}'
def variants(rows):
 seen=set()
 for symmetry in range(8):
  grid=[list(row[::-1] if symmetry>=4 else row) for row in rows]
  for _ in range(symmetry%4):grid=[list(row) for row in zip(*grid[::-1])]
  key=tuple(''.join(row) for row in grid)
  if key in seen:continue
  seen.add(key);w,h=len(grid[0]),len(grid)
  cells=[grid[z][x] for tz in range(h//3) for tx in range(w//3) for z in range(tz*3,tz*3+3) for x in range(tx*3,tx*3+3)]
  positions={r:[i+1 for i,c in enumerate(cells) if c==r] for r in sorted(set(cells)-{'_'})}
  tile_counts=[dict(Counter(c for c in cells[t:t+9] if c!='_')) for t in range(0,len(cells),9)]
  yield dict(w=w//3,h=h//3,symmetry=symmetry,rows=list(key),cells=cells,role_pits=positions,tile_roles=tile_counts,empty_pits=[i+1 for i,c in enumerate(cells) if c=='_'])
def recipes_for(spec,counts,vv):
 roles=sorted(counts)
 preferred=itertools.product(*(spec['roles'][r] for r in roles))
 policy=spec.get('recipe_policy','source_or')
 assert policy in ('source_or','balanced_vanilla')
 if policy=='balanced_vanilla':
  assert spec['source']=='program','截图模版不能扩展原图OR范围'
  # 保留原有角色顺序，再补齐所有原版作物的配比；相同库存需求只收录一次。
  candidates=itertools.chain(preferred,itertools.permutations(sorted(RULES),len(roles)))
 else:candidates=preferred
 seen=set();recipes=[]
 for values in candidates:
  if len(set(values))!=len(values):continue
  mapping=dict(zip(roles,values));needs={mapping[r]:n for r,n in counts.items()}
  seasons=[s for s in ('autumn','winter','spring','summer') if all(s in RULES[c]['seasons'] for c in values)]
  if not seasons:continue
  if policy=='balanced_vanilla':
   if any(sum(n*RULES[mapping[r]]['net'][i] for r,n in tile.items())!=0 for v in vv for tile in v['tile_roles'] for i in range(3)):continue
   key=tuple(sorted(needs.items()))
   if key in seen:continue
   seen.add(key)
  recipe=dict(map=mapping,needs=needs,seasons=seasons,key=','.join(f'{c}:{n}' for c,n in sorted(needs.items())))
  if policy=='balanced_vanilla' and any(mapping[r] not in spec['roles'][r] for r in roles):recipe['extension']=True
  recipes.append(recipe)
 return recipes
def compile_catalog():
 data=json.loads(SOURCE.read_text());compiled=[];fixtures=[];seen=set();lines=['# 巨大化静态模版逐格审核目录','','[截图转录核对记录、原图与禁用项配比](REVIEW.md)。','','来源图保存在 sources/；行从上到下、列从左到右，每3行/列为一块地皮。`_`是必要空坑。替换只取原图OR；18株是单独的程序定义。','','| 编号 | 分类/启用 | 角色作物（一个角色只选一种） | 格子行 | 备注 |','|---|---|---|---|---|']
 for spec in data['templates']:
  assert spec['id'] not in seen;seen.add(spec['id'])
  role_text='；'.join(r+'='+','.join(cs) for r,cs in spec['roles'].items())
  if spec.get('recipe_policy')=='balanced_vanilla':role_text='所有原版作物，逐地皮养分平衡、共同应季；下列为原有角色首选：'+role_text
  lines.append('| '+spec['id']+' | '+spec['classification']+('/启用' if spec['enabled'] else '/禁用')+' | '+role_text+' | '+' / '.join(spec['rows'])+' | '+spec['note']+' |')
  if not spec['enabled']:continue
  assert spec['transforms']=='rotate_mirror'
  assert spec['size']==[len(spec['rows'][0])//3,len(spec['rows'])//3]
  rows=spec['rows'];assert len(rows)%3==0 and len(rows[0])%3==0 and all(len(row)==len(rows[0]) for row in rows)
  counts=Counter(''.join(rows));counts.pop('_',None);assert set(counts)==set(spec['roles'])
  vv=list(variants(rows))
  recipes=recipes_for(spec,counts,vv)
  for recipe in recipes:
   recipe['tile_needs']={str(v['symmetry']):[{recipe['map'][r]:n for r,n in counts.items()} for counts in v['tile_roles']] for v in vv}
  for v in vv:
   points=[dict(x=tx*4+(col-1)*4/3,z=tz*4+(row-1)*4/3) for tz in range(v['h']) for tx in range(v['w']) for row in range(3) for col in range(3)]
   for recipe in recipes:
    board=[recipe['map'].get(r,False) for r in v['cells']]
    for ti in range(v['w']*v['h']):
     crops=board[ti*9:ti*9+9];assert sum(bool(c) for c in crops)<=CONSTANTS['FARM_PANT_OVERCROWDING_MAX_PLANTS']
     assert all(sum(RULES[c]['net'][i] for c in crops if c)==0 for i in range(3)),(spec['id'],recipe,ti)
    for i,c in enumerate(board):
     if not c:continue
     near=sum(d==c and (points[i]['x']-p['x'])**2+(points[i]['z']-p['z'])**2<=RULES[c]['radius']**2+1e-9 for d,p in zip(board,points))
     assert near>=RULES[c]['minimum'],(spec['id'],i,c,near)
     assert all(not d or (points[i]['x']-points[j]['x'])**2+(points[i]['z']-points[j]['z'])**2>CONSTANTS['FARM_TILL_SPACING']**2 for j,d in enumerate(board[:i]))
    fixtures.append(dict(id=spec['id'],symmetry=v['symmetry'],w=v['w'],h=v['h'],crops=recipe['map'],seasons=recipe['seasons'],board=board))
  compiled.append({**spec,'counts':dict(counts),'total':sum(counts.values()),'variants':vv,'recipes':recipes})
 source_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
 sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((SOURCE.parent/'sources').glob('*.png'))}
 version=hashlib.sha256(json.dumps(dict(source=source_hash,templates=compiled,rules=RULES,constants=CONSTANTS),sort_keys=True).encode()).hexdigest()
 payload=dict(schema=1,version=version,templates=compiled)
 return '-- Generated by tools/build_seed_catalog.py; edit docs/template-catalog/catalog.json.\nreturn '+lua(payload)+'\n','\n'.join(lines)+'\n',dict(source_sha256=source_hash,image_sha256=sources,enabled=len(compiled),registered=len(data['templates']),coordinate_cases=len(fixtures),fixtures=fixtures)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
 generated,readme,report=compile_catalog()
 outputs={TARGET:generated,SOURCE.parent/'README.md':readme,SOURCE.parent/'coordinate-fixtures.json':json.dumps(report,ensure_ascii=False,indent=2)+'\n'}
 for path,value in outputs.items():
  if args.check:assert path.read_text()==value,f'{path} 过期'
  else:path.write_text(value)
 print(json.dumps({k:v for k,v in report.items() if k!='fixtures'},ensure_ascii=False))
if __name__=='__main__':main()
