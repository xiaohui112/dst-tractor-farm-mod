"""原图格子、完整块执行、篡改拒绝、策略隔离与真实坑距验收。"""
import json,sys,unittest
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import seed_strategy_audit as audit
ROOT=Path(__file__).resolve().parents[2]
class CatalogTests(unittest.TestCase):
 def test_all_transforms_recipes_keep_positions_and_reject_a_changed_cell(self):
  cases=json.loads((ROOT/'docs/template-catalog/coordinate-fixtures.json').read_text())['fixtures']
  sources={s['id']:s for s in json.loads((ROOT/'docs/template-catalog/catalog.json').read_text())['templates']}
  w=audit.world();L=w.lua
  def table(v):
   if isinstance(v,dict):return L.table_from({k:table(x) for k,x in v.items()})
   if isinstance(v,list):return L.table_from([table(x) for x in v])
   return v
  for f in cases:
   with self.subTest(id=f['id'],symmetry=f['symmetry'],crops=f['crops']):
    source=sources[f['id']];h=len(source['rows']);width=len(source['rows'][0]);expected=[False]*(width*h)
    for z,row in enumerate(source['rows']):
     for x,role in enumerate(row):
      xx=width-1-x if f['symmetry']>=4 else x;rotation=f['symmetry']%4
      if rotation==0:u,v=xx,z
      elif rotation==1:u,v=h-1-z,xx
      elif rotation==2:u,v=width-1-xx,h-1-z
      else:u,v=z,width-1-xx
      index=((v//3)*f['w']+u//3)*9+(v%3)*3+u%3
      expected[index]=f['crops'].get(role,False)
    self.assertEqual(f['board'],expected)
    tiles=[dict(x=x*4,z=z*4) for z in range(f['h']) for x in range(f['w'])]
    slots=[dict(x=t['x']+(s%3-1)*4/3,z=t['z']+(s//3-1)*4/3,cx=t['x'],cz=t['z'],crop=f['board'][i*9+s]) for i,t in enumerate(tiles) for s in range(9)]
    L.execute('ENTITIES={}')
    for point in slots:L.globals().SpawnPrefab('farm_soil').Transform.SetPosition(None,point['x'],0,point['z'])
    b=table(dict(dynamic=True,strategy='GIANT_TEMPLATE',tiles=tiles,slots=slots,season=f['seasons'][0],nutrient_balanced=True,construction=dict(modules=[dict(id=f['id'],symmetry=f['symmetry'],origin=dict(x=0,z=0),crops=f['crops'])])))
    valid=L.eval("require('aom_dynamic_farm').Validate")(b);self.assertTrue(valid[0] if isinstance(valid,tuple) else valid)
    planted=next(i for i,k in enumerate(f['board'],1) if k)
    b.slots[planted].crop=False
    self.assertFalse(L.eval("require('aom_dynamic_farm').Validate")(b))
  self.assertEqual(len(cases),364)
 def setup_plan(self,stock,tiles,season='autumn',lock=None):
  w=audit.world();L=w.lua;inst=w.make(stock,season);inst._seed_strategy='GIANT_TEMPLATE';inst._aom_template_id=lock
  for x,z in tiles:
   for s in range(9):L.globals().SpawnPrefab('farm_soil').Transform.SetPosition(None,x*4+(s%3-1)*4/3,0,z*4+(s//3-1)*4/3)
  return w,inst
 def test_source_pair_exact_rows_and_role_cannot_split_or_use_unlisted_crop(self):
  w,inst=self.setup_plan({'garlic':4,'onion':4,'potato':8},[(0,0),(1,0)],lock='autumn-09');L=w.lua
  b=L.eval("require('aom_dynamic_farm').Build")(inst,0,0)
  expected=['CAAAAC','CBBBBC','CC__CC'];mapping={'A':'garlic','B':'onion','C':'potato'}
  for p in b.slots.values():
   row=round((p.z-p.cz)/(4/3))+1;col=round((p.x-p.cx)/(4/3))+1+round(p.cx/4)*3
   self.assertEqual(p.crop,mapping.get(expected[row][col],False))
  for stock in ({'garlic':4,'onion':4,'potato':4,'eggplant':4},{'durian':4,'pomegranate':4,'potato':8}):
   w,inst=self.setup_plan(stock,[(0,0),(1,0)],season='spring',lock='autumn-09')
   result=w.lua.eval("require('aom_dynamic_farm').Build")(inst,0,0)
   self.assertIsNone(result[0] if isinstance(result,tuple) else result)
 def test_two_pairs_and_square_are_distinct_and_cache_respects_lock(self):
  w,inst=self.setup_plan({'garlic':8,'onion':8,'potato':16},[(0,0),(1,0),(0,1),(1,1)],season='spring',lock='spring-11');L=w.lua
  first=L.eval("require('aom_dynamic_farm').Build")(inst,0,0);self.assertEqual(first.total,32);self.assertEqual(len(first.construction.modules),2)
  inst._aom_template_id='spring-12';second=L.eval("require('aom_dynamic_farm').Build")(inst,0,0)
  self.assertEqual(second.total,32);self.assertEqual(len(second.construction.modules),1);self.assertFalse(second.construction.cache_hit)
  cached=L.eval("require('aom_dynamic_farm').Build")(inst,0,0);self.assertTrue(cached.construction.cache_hit)
 def test_cached_module_indices_follow_current_scan_order(self):
  w,inst=self.setup_plan({'garlic':4,'onion':4,'potato':8},[(0,0),(1,0)],lock='autumn-09');L=w.lua
  first=L.eval("require('aom_dynamic_farm').Build")(inst,0,0)
  second=L.eval("require('aom_dynamic_farm').Build")(inst,4,0)
  self.assertTrue(second.construction.cache_hit)
  module=second.construction.modules[1];self.assertEqual(list(module.tiles.values()),[2,1])
  self.assertEqual(second.tiles[module.tiles[1]].x,module.origin.x)
 def test_task_report_isolation_and_independent_entry_points(self):
  w,inst=self.setup_plan({'tomato':8,'potato':8},[(0,0)]);L=w.lua
  L.execute("require('aom_seed_initial').Build=function()error('optimal initializer called by template')end")
  plan=L.eval("require('aom_dynamic_farm').Build")(inst,0,0);task=inst._aom_planning_task
  other=w.make({'carrot':1},'autumn');other._seed_strategy='GIANT_TEMPLATE'
  L.eval("require('aom_dynamic_farm').Build")(other,0,0)
  self.assertEqual(task.last_report.total,8);self.assertEqual(other._aom_planning_task.last_report.total,0)
  self.assertIsNone(L.eval("require('aom_seed_packing').last_report"))
  w,inst=self.setup_plan({'tomato':8,'potato':8},[(0,0)]);inst._seed_strategy='GIANT';L=w.lua
  L.execute("require('aom_seed_templates').Build=function()error('template entry called by optimal')end")
  plan=L.eval("require('aom_dynamic_farm').Build")(inst,0,0);self.assertTrue(plan.optimal);self.assertEqual(plan.total,8)
 def test_real_pit_distance_is_checked_before_placing_and_budget_is_fixed(self):
  w,inst=self.setup_plan({'garlic':4,'onion':4,'potato':8},[(0,0),(1,0)],lock='autumn-09');L=w.lua
  # 两坑仍在各自扫描容差内，但间距变成0.733，必须排除。
  L.execute("for _,e in ipairs(ENTITIES)do if e.z== -4/3 and e.x==4/3 then e.x=e.x+.3 elseif e.z== -4/3 and math.abs(e.x-8/3)<.0001 then e.x=e.x-.3 end end")
  result=L.eval("require('aom_dynamic_farm').Build")(inst,0,0)
  # 可通过换方向避开冲突；无论是否有候选，输出必须合法。
  b=result[0] if isinstance(result,tuple) else result
  if b:self.assertTrue(L.eval("require('aom_dynamic_farm').Validate")(b)[0]);self.assertLessEqual(b.construction.attempts,b.construction.work_budget)
if __name__=='__main__':unittest.main()
