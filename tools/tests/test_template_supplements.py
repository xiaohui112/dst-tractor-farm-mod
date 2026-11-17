"""原模板不动、跨模板同族补块、实际播种与缓存/存档/预览回归。"""
import unittest
from collections import Counter
import seed_strategy_audit as audit


class TemplateSupplementTests(unittest.TestCase):
 def setup_plan(self, stock=None, tiles=None, season='autumn', lock=None, baseline=False):
  w=audit.world();L=w.lua
  inst=w.make(stock or {'carrot':40,'corn':40,'eggplant':40},season)
  inst._seed_strategy='GIANT_TEMPLATE';inst._attachment_type='seeder';inst._aom_template_id=lock
  for x,z in tiles or [(x,z) for z in range(3) for x in range(3)]:
   for s in range(9):
    L.globals().SpawnPrefab('farm_soil').Transform.SetPosition(None,x*4+(s%3-1)*w.grid_spacing,0,z*4+(s//3-1)*w.grid_spacing)
  if baseline:
   L.execute("require('aom_seed_supplement').Fill=function(board,modules)return board,modules,{added=0,attempts=0,work_budget=0}end")
  result=L.eval("require('aom_dynamic_farm').Build")(inst,0,0)
  b=result[0] if isinstance(result,tuple) else result
  if b:inst._block=b
  return w,inst,b

 def test_three_forties_fill_81_and_preserve_every_original_template_cell(self):
  for season in ('autumn','spring'):
   with self.subTest(season=season):
    _,_,old=self.setup_plan(season=season,baseline=True)
    w,_,b=self.setup_plan(season=season)
    self.assertEqual(old.total,72);self.assertEqual(b.total,81)
    self.assertEqual(b.construction.baseline_total,72)
    self.assertEqual(b.construction.supplementation.added,9)
    self.assertEqual(Counter(p.crop for p in b.slots.values()),{'carrot':27,'corn':27,'eggplant':27})
    previous={(p.x,p.z):p.crop for p in old.slots.values() if p.crop}
    current={(p.x,p.z):p.crop for p in b.slots.values()}
    self.assertTrue(all(current[k]==v for k,v in previous.items()))
    def modules(plan):
     return [(m.id,m.symmetry,m.origin.x,m.origin.z,dict(m.crops.items())) for m in plan.construction.modules.values()]
    self.assertEqual(modules(old),modules(b)[:len(old.construction.modules)])
    self.assertTrue(w.lua.eval("require('aom_dynamic_farm').Validate")(b)[0])
    points=[{k:p[k] for k in ('x','z','cx','cz','crop')} for p in b.slots.values()]
    errors,_=audit.independent_check(dict(stock={'carrot':40,'corn':40,'eggplant':40},season=season,tiles=[(x,z) for z in range(3) for x in range(3)]),points)
    self.assertEqual(errors,[])

 def test_isolated_or_scarce_supplements_do_not_fake_family_or_stock(self):
  _,_,single=self.setup_plan(tiles=[(0,0)])
  self.assertIsNone(single)
  _,_,scarce=self.setup_plan(stock={'carrot':26,'corn':26,'eggplant':26})
  self.assertEqual(scarce.total,72)
  _,_,winter=self.setup_plan(season='winter')
  self.assertIsNone(winter)

 def test_supplement_catalog_only_derives_allowed_program_layouts_and_roles(self):
  w=audit.world();L=w.lua
  L.execute('''
local Catalog=require('aom_seed_catalog');local Data=require('aom_seed_template_data')
assert(#Catalog.templates==30 and #Catalog.supplements==2)
for _,spec in ipairs(Catalog.supplements)do
 local parent=Data.Spec(spec.parent_id)
 assert(parent.source=='program'and parent.total==18 and spec.total==9 and spec.family_scope=='field')
 for _,r in ipairs(spec.recipes)do
  local found=false
  for _,pr in ipairs(parent.recipes)do
   local same=true
   for role,crop in pairs(r.map)do if pr.map[role]~=crop then same=false end end
   if same then
    found=true;for crop,n in pairs(r.needs)do assert(pr.needs[crop]==n*2)end
   end
  end
  assert(found)
 end
end
''')

 def test_picture_lock_preserves_required_holes_and_cannot_borrow_other_recipes(self):
  w,_,b=self.setup_plan(stock={'tomato':40,'potato':40},lock='autumn-01')
  self.assertEqual(b.total,72)
  self.assertTrue(all(m.id=='autumn-01' for m in b.construction.modules.values()))
  self.assertTrue(all(not b.slots[(ti-1)*9+5].crop for ti in range(1,10)))
  _,_,locked=self.setup_plan(lock='program-18-equal')
  self.assertEqual(locked.total,81)

 def test_cache_preview_partial_save_and_actual_sowing_include_supplement(self):
  w,inst,b=self.setup_plan();L=w.lua
  cached=L.eval("require('aom_dynamic_farm').Build")(inst,4,0)
  self.assertTrue(cached.construction.cache_hit);self.assertEqual(cached.total,81)
  for m in cached.construction.modules.values():
   self.assertEqual(cached.tiles[m.tiles[1]].x,m.origin.x)
   self.assertEqual(cached.tiles[m.tiles[1]].z,m.origin.z)
  L.globals().inst=inst
  L.execute('''
local D=require('aom_dynamic_farm');local Block=require('aom_block_plan');local Preview=require('aom_template_preview')
local view=Preview.Decode(Preview.Encode(inst,0,0));assert(view and #view.slots==81)
local targets,why=D.Targets(inst,0,0);assert(targets and #targets==9,why)
assert(Drive.WorkHere(inst,0,0));assert(inst._block.done==1)
local saved=Block.OnSave(inst);local other=make_inst({},'autumn')
other.components.aom_attachment_store=inst.components.aom_attachment_store
Block.OnLoad(other,saved);assert(other._block and other._block.total==81 and other._block.done==1)
other._attachment_type='seeder';inst=other
for _,tile in ipairs(inst._block.tiles)do Drive.WorkTile(inst,tile.x,tile.z)end
assert(inst._block.done==81 and crop_count()==81)
assert(inst.components.aom_attachment_store:GetSeedCount()==39)
assert(D.Validate(inst._block))
''')

 def test_supplement_sowing_rechecks_neighboring_donors_before_consuming_seed(self):
  w,inst,_=self.setup_plan();L=w.lua;L.globals().inst=inst
  L.execute('''
local D=require('aom_dynamic_farm');local before=inst.components.aom_attachment_store:GetSeedCount()
for _,e in ipairs(ENTITIES)do if e:IsValid()and tkey(e.x,e.z)==tkey(4,0)then e:Remove()end end
local targets,why=D.Targets(inst,0,0)
assert(not targets and why=='NEED_PLOW')
assert(inst.components.aom_attachment_store:GetSeedCount()==before and inst._block.done==0)
''')

 def test_large_field_supplement_rechecks_local_neighborhood_instead_of_entire_field(self):
  w,inst,b=self.setup_plan(stock={'carrot':250,'corn':250,'eggplant':250},tiles=[(x,z)for z in range(9)for x in range(9)])
  self.assertEqual(b.total,729);L=w.lua;L.globals().inst=inst
  L.execute('''
local D=require('aom_dynamic_farm');local spec=require('aom_seed_template_data');local b=inst._block
local supplement
for _,m in ipairs(b.construction.modules)do if spec.Spec(m.id).family_scope=='field'then supplement=m;break end end
assert(supplement)
local scan=D.Scan;local calls=0;D.Scan=function(...)calls=calls+1;return scan(...)end
local targets,why=D.Targets(inst,supplement.origin.x,supplement.origin.z)
assert(targets and #targets==9,why);assert(calls<=25 and calls<#b.tiles)
''')

 def test_joint_empty_blocks_can_supply_each_others_family_with_bounded_search(self):
  w,_,b=self.setup_plan(stock={'carrot':6,'corn':6,'eggplant':6},tiles=[(0,0),(1,0)])
  L=w.lua;L.globals().B=b
  L.execute('''
local Layout=require('aom_seed_layout');local Fill=require('aom_seed_supplement').Fill
local g=Layout.Geometry(B.tiles,B.slots,DEFS);g.balanced=true;g.nutrients_only=true
local empty={};for i=1,18 do empty[i]=false end
local crops={'carrot','corn','eggplant'};local stock={carrot=6,corn=6,eggplant=6}
local board,modules,report=Fill(empty,{},crops,stock,B.tiles,B.slots,DEFS,g,nil,{})
assert(report.added==18 and #modules==2 and Layout.Valid(board,g))
assert(report.attempts<=report.work_budget)
local none,unchanged,limited=Fill(empty,{},crops,stock,B.tiles,B.slots,DEFS,g,nil,{supplement_budget=1})
assert(limited.limited and limited.added==0 and #unchanged==0 and limited.attempts<=1)
for _,k in ipairs(none)do assert(not k)end
''')


if __name__=='__main__':unittest.main()
