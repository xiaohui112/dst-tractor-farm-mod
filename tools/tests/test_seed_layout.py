"""Independent inventory oracle and the validated offline webpage's layout metrics."""
import itertools
import json
from pathlib import Path
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_giant_farming as giant

class SeedLayoutTests(unittest.TestCase):
 def setUp(self):
  self.w=giant.World();self.lua=self.w.lua
  self.lua.execute("Layout=require('aom_seed_layout')")
 def test_inventory_bound_and_species_count_match_exhaustive_oracle(self):
  layout=self.lua.globals().Layout;defs=self.lua.globals().DEFS
  for stock in itertools.product((3,4,5,9),repeat=3):
   counts=dict(zip(('carrot','corn','potato'),stock))
   for capacity in (9,18):
    choices=[[0]+list(range(4,n+1)) for n in stock]
    expected=max((sum(a),sum(n>0 for n in a)) for a in itertools.product(*choices) if sum(a)<=capacity)
    stocks=self.lua.table_from(counts);crops=layout.Crops(stocks,defs,'autumn')
    allocation,total,kinds=layout.Allocate(crops,stocks,defs,capacity,0,None)
    self.assertEqual((total,kinds),expected,(stock,capacity))
    used={a.k:a.n for a in allocation.values()}
    self.assertEqual(sum(used.values()),total)
    self.assertTrue(all(4<=n<=counts[k] for k,n in used.items()))
 def test_layout_metrics_match_webpage_reference(self):
  data=json.loads((Path(__file__).parent/'fixtures/seed-layout-web-reference.json').read_text())
  for case in data['cases']:
   self.setUp();board=[k or False for tile in case['cells'] for k in tile]
   self.lua.globals().board=self.lua.table_from(board)
   self.lua.globals().width=case['w'];self.lua.globals().height=case['h']
   self.lua.execute('''tiles={};slots={}
for z=0,height-1 do for x=0,width-1 do
 tiles[#tiles+1]={x=x*4,z=z*4}
 for s=0,8 do slots[#slots+1]={x=x*4+(s%3-1)*4/3,z=z*4+(math.floor(s/3)-1)*4/3} end
end end
for _,p in ipairs(slots)do SpawnPrefab('farm_soil').Transform:SetPosition(p.x,0,p.z)end
geometry=Layout.Geometry(tiles,slots,DEFS);metrics=Layout.Metrics(board,geometry)
assert(Layout.LowerBound(board,geometry)<=metrics.score+.000001)
''')
   metrics=self.lua.globals().metrics;expected=case['metrics']
   # 网页用 b==a+1 判断横向边界，宽度为1时会把竖向相邻误认成横向。
   # 用实际坐标独立计算接缝，避免把这个旧网页缺陷也移植进游戏。
   seams=0
   for ti,tile in enumerate(case['cells']):
    x,z=ti%case['w'],ti//case['w']
    if x+1<case['w']:
     other=case['cells'][ti+1]
     seams+=sum(bool(tile[j*3+2]) and tile[j*3+2]==other[j*3] for j in range(3))
    if z+1<case['h']:
     other=case['cells'][ti+case['w']]
     seams+=sum(bool(tile[6+j]) and tile[6+j]==other[j] for j in range(3))
   # 新增分散小团评分，独立按实际坑位的八邻接计算连通分量。
   planted=[]
   for ti,tile in enumerate(case['cells']):
    for s,crop in enumerate(tile):
     if crop:planted.append((crop,ti%case['w']*3+s%3,ti//case['w']*3+s//3))
   remaining=set(range(len(planted)));components=0
   while remaining:
    components+=1;queue=[remaining.pop()]
    for i in queue:
     k,x,z=planted[i]
     near=[j for j in remaining if planted[j][0]==k and (x-planted[j][1])**2+(z-planted[j][2])**2<=2]
     remaining.difference_update(near);queue.extend(near)
   fragmentation=components-len({p[0] for p in planted})
   corrected=expected['score']-200*(seams-expected['spatial']['seams'])+3000*fragmentation
   self.assertAlmostEqual(metrics.score,corrected,places=6)
   self.assertAlmostEqual(metrics.family,expected['spatial']['family'],places=6)
   self.assertEqual(metrics.seams,seams)
   self.assertEqual(metrics.repetition,expected['repeatedMotifMismatches'])
   self.assertEqual(metrics.fragmentation,fragmentation)
   if case.get('regularized'):
    self.lua.execute('after,report=Layout.Regularize(board,geometry);assert(Layout.Valid(after,geometry))')
    self.assertLessEqual((self.lua.globals().report.after.fragmentation,self.lua.globals().report.after.family,self.lua.globals().report.after.tidy),(fragmentation,expected['spatial']['family'],corrected-expected['spatial']['family']*100-fragmentation*3000))
 def test_single_tile_alignment_reaches_webpage_reference_cost(self):
  self.lua.execute('''board={'potato','tomato','potato','tomato',false,'tomato','potato','potato','tomato'}
tiles={{x=0,z=0}};slots={};for s=0,8 do slots[#slots+1]={x=(s%3-1)*4/3,z=(math.floor(s/3)-1)*4/3} end
for _,p in ipairs(slots)do SpawnPrefab('farm_soil').Transform:SetPosition(p.x,0,p.z)end
local geometry=Layout.Geometry(tiles,slots,DEFS);geometry.balanced=true
local result,report=Layout.Regularize(board,geometry)
assert(report.after.score<=-392 and Layout.Valid(result,geometry))
local counts={};for _,k in ipairs(result) do if k then counts[k]=(counts[k] or 0)+1 end end
assert(counts.potato==4 and counts.tomato==4 and not result[5])
''')
 def test_single_tile_sowing_matches_independent_balanced_oracle(self):
  import seed_strategy_audit as audit
  for amounts in itertools.product((3,4,5,9),repeat=3):
   self.setUp();counts=dict(zip(('tomato','potato','carrot'),amounts))
   expected=audit.upper_bound(counts,'autumn',9)[0]
   self.lua.globals().stock=self.lua.table_from(counts)
   self.lua.execute("inst=make_inst(stock,'autumn');for x=-1,1 do for z=-1,1 do SpawnPrefab('farm_soil').Transform:SetPosition(x*4/3,0,z*4/3) end end;plan,why=require('aom_dynamic_farm').Build(inst,0,0)")
   plan=self.lua.globals().plan
   self.assertEqual(plan.total if plan else 0,expected,counts)
   if plan:
    points=[{k:p[k] for k in ('x','z','cx','cz','crop')} for p in plan.slots.values()]
    errors,_=audit.independent_check({'tiles':[(0,0)],'stock':counts,'season':'autumn'},points)
    self.assertFalse(errors)
    self.assertFalse(plan.slots[5].crop)
