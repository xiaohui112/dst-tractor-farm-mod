"""Native query membership is authoritative, including resume and missing soil."""
from pathlib import Path
import sys
import unittest

import test_giant_farming as giant
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cpsat_benchmark'))
import native_float


class NativeFarmNeighborTests(unittest.TestCase):
 def setUp(self):
  self.w=giant.World();native_float.install(self.w);self.L=self.w.lua
  self.L.execute("A=require('aom_seed_layout');N=require('aom_farm_neighbors');D=require('aom_dynamic_farm');Block=require('aom_block_plan')")

 def test_native_boundary_is_not_refiltered_as_double(self):
  self.L.execute('''
local a=SpawnPrefab('farm_soil');a.Transform:SetPosition(4+4/3,0,0)
local b=SpawnPrefab('farm_soil');b.Transform:SetPosition(4/3,0,0)
local x,y,z=a.Transform:GetWorldPosition();local u,v,w=b.Transform:GetWorldPosition()
assert((x-u)^2>16)
local slots={{x=x,y=y,z=z},{x=u,y=v,z=w}}
local g=A.Geometry({},slots,DEFS)
assert(g.complete and A.InRange(g,1,2,16) and A.InRange(g,2,1,16))
local found=false;for _,q in ipairs(g.near[1])do if q.j==2 then found=true;assert(q.d>16)end end;assert(found)
''')

 def test_radius_exclusion_and_height_follow_query(self):
  self.L.execute('''
local slots={}
for _,p in ipairs({{x=0,y=0,z=0},{x=4.000000476837158,y=0,z=0},{x=0,y=4,z=0},{x=0,y=4.000001,z=0}})do
 local e=SpawnPrefab('farm_soil');e.Transform:SetPosition(p.x,p.y,p.z)
 p.x,p.y,p.z=e.Transform:GetWorldPosition();slots[#slots+1]=p
end
local g=A.Geometry({},slots,DEFS)
assert(g.complete and not A.InRange(g,1,2,16) and A.InRange(g,1,3,16) and not A.InRange(g,1,4,16))
''')

 def test_query_membership_crosses_lua_bucket_boundary(self):
  self.L.execute('''
local slots={}
for _,x in ipairs({-.0000001,4})do local e=SpawnPrefab('farm_soil');e.Transform:SetPosition(x,0,0)
 local px,y,z=e.Transform:GetWorldPosition();slots[#slots+1]={x=px,y=y,z=z}end
local g=A.Geometry({},slots,DEFS)
assert(math.floor(slots[1].x/4)==-1 and math.floor(slots[2].x/4)==1)
assert(#g.near[1]==2 and A.InRange(g,1,2,16))
''')

 def test_cache_is_per_capture_and_never_saved_in_slots(self):
  self.L.execute('''
local slots={};for _,x in ipairs({0,1,2,3})do SpawnPrefab('farm_soil').Transform:SetPosition(x,0,0);slots[#slots+1]={x=x,z=0}end
local calls=0;local original=TheSim.FindEntities
TheSim.FindEntities=function(...)calls=calls+1;return original(...)end
local g=A.Geometry({},slots,DEFS);assert(calls==8)
A.Geometry({},slots,DEFS);A.Geometry({},{slots[1],slots[2]},DEFS);assert(calls==8)
for _,p in ipairs(slots)do for k in pairs(p)do assert(k=='x'or k=='z')end end
ENTITIES[1]:Remove();N.Clear(slots);local missing=A.Geometry({},slots,DEFS)
assert(not missing.complete and not A.Valid({'potato','potato','potato','potato'},missing))
''')

 def test_missing_field_cannot_produce_an_optimal_proof(self):
  self.L.execute('''
local slots={};for dx=-1,1 do for dz=-1,1 do slots[#slots+1]={x=dx*4/3,z=dz*4/3,cx=0,cz=0}end end
local board,report=require('aom_seed_packing').Balanced({'potato','tomato'},{potato=4,tomato=4},{{x=0,z=0}},slots,DEFS)
assert(not board and report.invalid_geometry and not report.optimal)
''')

 def test_killjoy_is_excluded_from_query_and_resume(self):
  self.L.execute('''
for dx=-1,1 do for dz=-1,1 do SpawnPrefab('farm_soil').Transform:SetPosition(dx*4/3,0,dz*4/3)end end
inst=make_inst({tomato=4,potato=4},'autumn');local plan=assert(D.Build(inst,0,0));inst._block=plan
local p;for _,q in ipairs(plan.slots)do if q.crop then p=q;break end end
for _,e in ipairs(ENTITIES)do local x,y,z=e.Transform:GetWorldPosition();if x==p.x and z==p.z then e:Remove();break end end
local plant=SpawnPrefab('farm_plant_'..p.crop);plant.Transform:SetPosition(p.x,p.y or 0,p.z);plant:AddTag('farm_plant_killjoy')
N.Clear(plan.slots);assert(not A.Geometry(plan.tiles,plan.slots,DEFS).complete)
local targets,why=D.Targets(inst,0,0);assert(not targets and why=='FOREIGN_CROP')
''')

 def test_native_counts_across_field_translations(self):
  for offset in (-100,0,100):
   self.setUp();self.L.globals().offset=offset
   self.L.execute('''
for x=0,2 do for z=0,2 do for dx=-1,1 do for dz=-1,1 do SpawnPrefab('farm_soil').Transform:SetPosition(offset+x*4+dx*4/3,0,offset+z*4+dz*4/3)end end end end
inst=make_inst({carrot=40,corn=40,potato=40,tomato=40,eggplant=40,pumpkin=40,garlic=40,onion=40,pepper=40},'autumn')
plan,why=D.Build(inst,offset,offset);assert(plan,why);assert(plan.total==81 and plan.optimal and D.Validate(plan))
''')

 def test_load_defers_until_entities_exist_and_rechecks_before_sowing(self):
  self.L.execute('''
for dx=-1,1 do for dz=-1,1 do SpawnPrefab('farm_soil').Transform:SetPosition(dx*4/3,0,dz*4/3)end end
inst=make_inst({tomato=4,potato=4},'autumn');inst._block=assert(D.Build(inst,0,0))
local data=Block.OnSave(inst);local saved=ENTITIES;ENTITIES={}
local other=make_inst({tomato=4,potato=4},'autumn');Block.OnLoad(other,data)
assert(other._block and other._block._native_needs_validation)
local targets,why=D.Targets(other,0,0);assert(not targets and why=='NEED_PLOW')
ENTITIES=saved;targets,why=D.Targets(other,0,0)
assert(targets and #targets==8 and not other._block._native_needs_validation)
assert(other.components.aom_attachment_store:GetSeedCount()==8)
''')


if __name__=='__main__':unittest.main()
