"""实际播种入口的动态区域、库存、存档、同步和现场变化回归。"""
import unittest
import test_giant_farming as giant
class DynamicFarmTests(unittest.TestCase):
 def setUp(self):
  self.w=giant.World();self.lua=self.w.lua
  self.lua.execute('''D=require('aom_dynamic_farm');Registry=require('aom_farm_registry')
function dynfield(x,z)
 for dx=-1,1 do for dz=-1,1 do SpawnPrefab('farm_soil').Transform:SetPosition(x+dx*4/3,0,z+dz*4/3) end end
 Registry.Record(TheWorld,x,z)
end
function dyninst(counts)
 inst=make_inst(counts,'autumn');inst._attachment_type='seeder';return inst
end
function finish_dynamic()
 local b=inst._block
 for _,t in ipairs(b.tiles) do inst.x=t.x;inst.z=t.z;Drive.WorkTile(inst,t.x,t.z) end
 return b
end
''')
 def test_five_five_five_all_seeds_used_without_templates(self):
  self.lua.execute('''dynfield(0,0);dynfield(4,0);dyninst({carrot=5,corn=5,potato=5})
assert(Drive.WorkHere(inst));assert(inst._block.dynamic and inst._block.total==15)
local b=finish_dynamic();assert(b.done==15 and crop_count()==15)
assert(inst.components.aom_attachment_store:GetSeedCount()==0)
''')
 def test_single_crop_never_reads_soil_nutrients(self):
  self.lua.execute('''dynfield(0,0);dyninst({carrot=9})
TheWorld.components.farming_manager.GetTileNutrients=function()error('seeder must not read nutrients') end
local ok,why=Drive.WorkHere(inst);assert(not ok and why=='NO_BALANCED_COMBO' and not inst._block and crop_count()==0)
''')
 def test_l_shape_only_uses_recorded_tiles(self):
  self.lua.execute('''dynfield(0,0);dynfield(4,0);dynfield(4,4);dyninst({carrot=9,corn=9,potato=9})
assert(Drive.WorkHere(inst));assert(inst._block.total==27 and #inst._block.tiles==3)
assert(finish_dynamic().done==27)
''')
 def test_saved_plan_sync_resume_and_missing_seed(self):
  self.lua.execute('''dynfield(0,0);dynfield(4,0);dyninst({carrot=4,corn=4,potato=4})
assert(Drive.WorkHere(inst));local data=Block.OnSave(inst)
assert(data.version==4 and data.dynamic and #data.completed==1)
local other=make_inst({},'autumn');other.components.aom_attachment_store=inst.components.aom_attachment_store
Block.OnLoad(other,data);assert(other._block and other._block.done==1)
inst=other;inst._attachment_type='seeder'
local value='';inst._plan_net={set=function(_,v)value=v end};Block.Sync(inst)
assert(string.sub(value,1,3)=='D5;' and string.find(Block.DescribeProgress(inst),'1/12'))
local view=Block.Decode(value);assert(view and view.dynamic and view.done==1 and view.total==12 and #view.slots>0)
assert(Block.Decode('D4;9999;0;autumn;0;0;0,0,potato')==nil)
assert(finish_dynamic().done==12)
data.slots[1].x=999;local bad=make_inst({},'autumn');Block.OnLoad(bad,data);assert(bad._block==nil)
''')
 def test_missing_pit_after_lock_does_not_consume_seed(self):
  self.lua.execute('''dynfield(0,0);dynfield(4,0);dyninst({carrot=6,corn=6,potato=6});assert(Drive.WorkHere(inst))
local b=inst._block;local seedcount=inst.components.aom_attachment_store:GetSeedCount()
local p=b.slots[10];Block.FindSoilAt(p.x,p.z):Remove()
local ok,why=Drive.WorkHere(inst);assert(not ok and why=='NEED_PLOW')
assert(b.done==1 and inst.components.aom_attachment_store:GetSeedCount()==seedcount)
''')
 def test_async_job_yields_and_completion_rechecks_scene(self):
  self.lua.execute('''dynfield(0,0);dynfield(4,0);dyninst({carrot=5,corn=5,potato=5})
local queue={};inst.DoTaskInTime=function(_,_,fn)queue[#queue+1]=fn end
inst._working=true
local ok,why=Drive.WorkHere(inst);assert(not ok and why=='PLANNING' and #queue>0 and not inst._block)
local n=0
while #queue>0 do n=n+1;assert(n<20000);local fn=table.remove(queue,1);fn() end
assert(inst._block and inst._block.total==15 and inst._block.done>0)
''')

 def test_preview_uses_the_drivers_tile_and_waits_if_they_leave_the_planned_field(self):
  self.lua.execute('''dynfield(0,0);dynfield(8,0);dyninst({tomato=12,potato=12})
local queue,preview={},nil
inst.DoTaskInTime=function(_,delay,fn)
 if delay==2 then preview=fn else queue[#queue+1]=fn end
end
inst._working=true;inst.x=1.9 -- 驾驶员靠近当前地皮边缘，规划仍从 0 格开始。
local ok,why=Drive.WorkHere(inst);assert(not ok and why=='PLANNING')
while #queue>0 do table.remove(queue,1)() end
local plan=inst._block
assert(preview and #plan.tiles==1 and plan.tiles[1].x==0)
inst.x=8;preview()
assert(inst._block==plan and plan.done==0 and crop_count()==0)
Drive.TrackMovement(inst);assert(plan.done==0)
inst.x=1.9;Drive.TrackMovement(inst)
assert(plan.done>0 and inst._block==plan)
''')

 def test_background_preparation_selects_field_under_the_driver(self):
  self.lua.execute('''dynfield(0,0);dynfield(8,0);dyninst({tomato=12,potato=12})
local now=10;GetTimeRealSeconds=function()return now end
inst.x=1.9;inst._working=false
local started=false
D.Start=function(_,x,z,background)assert(x==0 and z==0 and background);started=true end
D.PrepareNearby(inst);assert(not started)
now=12.1;D.PrepareNearby(inst);assert(started)
''')

 def test_capacity_tail_can_borrow_without_wasting_two_holes(self):
  self.lua.execute("""dynfield(0,0);dynfield(4,0);dyninst({carrot=16,potato=4,tomato=4,corn=4})
assert(Drive.WorkHere(inst));assert(inst._block.total==12 and D.Validate(inst._block))
assert(finish_dynamic().done==12)
""")
 def test_user_55_inventory_and_irregular_region(self):
  self.lua.execute("""
for x=0,3 do for z=0,3 do if not(x==3 and z==3) then dynfield(x*4,z*4) end end end
dyninst({carrot=7,corn=7,potato=24,tomato=17})
assert(Drive.WorkHere(inst));assert(inst._block.total==55 and D.Validate(inst._block))
assert(finish_dynamic().done==55)
""")
 def test_completed_harvested_region_starts_new_round(self):
  self.lua.execute("""dynfield(0,0);dyninst({tomato=8,potato=8});assert(Drive.WorkHere(inst));local b=finish_dynamic();assert(b.done==8)
for _,v in ipairs(ENTITIES) do if v:IsValid() and v:HasTag('farm_plant') then local x,_,z=v.Transform:GetWorldPosition();v:Remove();SpawnPrefab('farm_soil').Transform:SetPosition(x,0,z) end end
assert(Drive.WorkHere(inst));assert(inst._block~=b and inst._block.total==8)
""")
 def test_disappearing_bridge_is_not_used_to_join_regions(self):
  self.lua.execute("""dynfield(0,0);dynfield(4,0);dynfield(8,0)
local p=Block.FindSoilAt(4,0);p:Remove();dyninst({tomato=12,potato=12})
assert(Drive.WorkHere(inst));assert(#inst._block.tiles==1 and inst._block.total==8)
""")
 def test_supply_removal_and_refill_keep_locked_coordinates(self):
  self.lua.execute("""dynfield(0,0);dynfield(4,0);dyninst({tomato=8,potato=8});assert(Drive.WorkHere(inst));local b=inst._block
local store=inst.components.aom_attachment_store;local item=store:ListSeeds()[1];store.container:RemoveItem(item)
local ok,why=Drive.WorkHere(inst,4,0);assert(not ok and why=='MISSING_SEEDS' and b.done==1)
store.container:GiveItem(item);assert(Drive.WorkHere(inst,4,0));assert(inst._block==b and b.done==2)
""")
 def test_cancelled_job_and_mid_job_occupation_never_spend_seeds(self):
  self.lua.execute("""dynfield(0,0);dyninst({potato=9});local queue={}
inst.DoTaskInTime=function(_,_,fn)queue[#queue+1]=fn end;inst._working=true
Drive.WorkHere(inst);Block.ResetBlock(inst);while #queue>0 do table.remove(queue,1)() end
assert(not inst._block and crop_count()==0 and inst.components.aom_attachment_store:GetSeedCount()==9)
Drive.WorkHere(inst)
local p=Block.FindSoilAt(0,0);p:Remove();SpawnPrefab('weed_ivy').Transform:SetPosition(0,0,0)
local n=0;while #queue>0 do n=n+1;assert(n<20000);table.remove(queue,1)() end
assert(crop_count()==1 and inst.components.aom_attachment_store:GetSeedCount()==9 and not inst._block)
""")
 def test_maximum_region_single_crop_is_valid(self):
  self.lua.execute("""for x=0,7 do for z=0,7 do dynfield(x*4,z*4) end end
dyninst({carrot=192,corn=192,potato=192});local plan,why=D.Build(inst,0,0)
assert(plan and plan.total==576 and plan.optimal and D.Validate(plan))
""")
 def test_four_crop_small_stock_keeps_all_sixteen_plants_in_larger_field(self):
  self.lua.execute('''dynfield(0,0);dynfield(4,0);dynfield(0,4);dynfield(4,4)
dyninst({carrot=4,corn=4,potato=4,tomato=4})
assert(Drive.WorkHere(inst));local b=finish_dynamic()
assert(b.total==12 and b.done==12 and b.optimal and D.Validate(b))
local used={};for _,p in ipairs(b.slots) do if p.crop then used[p.crop]=(used[p.crop] or 0)+1 end end
assert(used.carrot==4 and used.corn==4 and used.potato==4 and not used.tomato)
''')
 def test_three_crop_whole_field_bands_are_straight_and_connected(self):
  for width,height in [(2,1),(1,2),(3,4)]:
   with self.subTest(width=width,height=height):
    self.setUp();self.lua.globals().width=width;self.lua.globals().height=height
    self.lua.execute('''for x=0,width-1 do for z=0,height-1 do dynfield(x*4,z*4) end end
dyninst({carrot=200,corn=200,potato=200});local b=D.Build(inst,0,0)
assert(b and b.total==width*height*9 and D.Validate(b))
local cells={};local w,h=width*3,height*3
for _,p in ipairs(b.slots) do
 local x=math.floor((p.x+4/3)*3/4+.5);local z=math.floor((p.z+4/3)*3/4+.5)
 cells[z*w+x+1]=p.crop
end
local rows,columns=true,true
for z=0,h-1 do for x=1,w-1 do if cells[z*w+x+1]~=cells[z*w+1] then rows=false end end end
for x=0,w-1 do for z=1,h-1 do if cells[z*w+x+1]~=cells[x+1] then columns=false end end end
local actual={};for i,p in ipairs(b.slots) do actual[i]=p.crop end;assert(require('aom_seed_balance').Board(actual,DEFS))
assert(not require('aom_seed_arrangement').Better(b.arrangement.before,b.arrangement.after))
''')
 def test_irregular_field_keeps_all_three_eligible_species_and_capacity(self):
  self.lua.execute('''dynfield(0,0);dynfield(4,0);dynfield(4,4)
dyninst({carrot=40,corn=40,potato=40});local b=D.Build(inst,0,0)
assert(b and b.total==27 and D.Validate(b))
local used={};for _,p in ipairs(b.slots) do used[p.crop]=(used[p.crop] or 0)+1 end
assert(used.carrot==9 and used.corn==9 and used.potato==9)
''')
 def test_region_above_limit_stops_before_spending_seed(self):
  self.lua.execute('''for x=0,64 do dynfield(x*4,0) end
dyninst({carrot=600});local b,why=D.Build(inst,0,0)
assert(not b and why=='FARM_TOO_LARGE' and crop_count()==0)
assert(inst.components.aom_attachment_store:GetSeedCount()==600)
''')
