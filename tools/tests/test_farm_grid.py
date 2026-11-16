"""Actual tilling, native float geometry, old pits and current grid compatibility."""
import sys
import unittest
from pathlib import Path
import test_giant_farming as giant
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cpsat_benchmark'))
import native_float

class FarmGridTests(unittest.TestCase):
 def world(self):
  w=giant.World();native_float.install(w)
  w.lua.execute("Grid=require('aom_farm_grid');D=require('aom_dynamic_farm')")
  return w

 def test_tilling_25_tiles_survives_native_collapse_and_plans_225(self):
  w=self.world();L=w.lua
  L.execute('''
for x=0,4 do for z=0,4 do
 local changed,why,ready=Farm.Plough(x*4,0,z*4)
 assert(ready,why)
end end
local count=0
for _,e in ipairs(ENTITIES)do if e:IsValid()and e.prefab=='farm_soil'then
 count=count+1;assert(not e:HasTag('NOCLICK')and not e:HasTag('NOBLOCK'))
 local x,_,z=e.Transform:GetWorldPosition();local cx,_,cz=TheWorld.Map:GetTileCenterPoint(x,0,z)
 assert((x-cx==0 or math.abs(x-cx)==Grid.SPACING)and(z-cz==0 or math.abs(z-cz)==Grid.SPACING))
end end
assert(count==225)
inst=make_inst({garlic=100,onion=100,pepper=100},'autumn')
local plan,why=D.Build(inst,0,0);assert(plan,why)
assert(plan.total==225 and plan.optimal and D.Validate(plan))
''')

 def test_empty_old_grid_is_rebuilt_but_adjacent_old_pits_survive(self):
  w=self.world();w.lua.execute('''
for tx=0,1 do for x=-1,1 do for z=-1,1 do SpawnPrefab('farm_soil').Transform:SetPosition(tx*4+x*4/3,0,z*4/3)end end end
local neighbours=TheWorld.Map:GetEntitiesOnTileAtPoint(4,0,0)
assert(not Farm.IsFieldReady(0,0,0))
local changed,why,ready=Farm.Plough(0,0,0);assert(changed and ready,why)
assert(Farm.IsFieldReady(0,0,0))
for _,e in ipairs(neighbours)do assert(e:IsValid()and not e:HasTag('NOCLICK'))end
local again,reason,done=Farm.Plough(0,0,0);assert(not again and done and reason=='ALREADY_TILLED')
''')

 def test_existing_crop_does_not_move_during_retiling(self):
  w=self.world();w.lua.execute('''
local e=SpawnPrefab('farm_plant_potato');e.Transform:SetPosition(4/3,0,4/3)
local x,y,z=e.Transform:GetWorldPosition()
Farm.Plough(0,0,0)
local px,py,pz=e.Transform:GetWorldPosition();assert(e:IsValid()and px==x and py==y and pz==z)
''')

 def test_native_boundary_and_spacing_at_positive_negative_large_origins(self):
  for origin in (0,2,-100,8184,-8200,999960):
   w=self.world();w.lua.globals().origin=origin
   w.lua.execute('''
local slots={};for tx=0,1 do for x=-1,1 do for z=-1,1 do
 local e=SpawnPrefab('farm_soil');e.Transform:SetPosition(origin+4*tx+x*Grid.SPACING,0,origin+z*Grid.SPACING)
 local px,py,pz=e.Transform:GetWorldPosition();slots[#slots+1]={x=px,y=py,z=pz}
end end end
local A=require('aom_seed_layout');local g=A.Geometry({},slots,DEFS)
assert(g.complete)
for i=1,9 do assert(A.InRange(g,i,i+9,16))end
for _,conflicts in ipairs(g.conflicts)do assert(#conflicts==0)end
''')

if __name__=='__main__':unittest.main()
