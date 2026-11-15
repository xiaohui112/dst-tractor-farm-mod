"""真实自动播种入口：库存、现场、九宫格、跨轮、回调结算和旧计划续播。"""
import unittest
import test_giant_farming as giant

class AutoGridSeedingTests(unittest.TestCase):
 def setUp(self):
  self.w=giant.World();self.lua=self.w.lua
  self.lua.execute('''
Auto=require('aom_auto_seeding');Dynamic=require('aom_dynamic_farm')
function field(x,z,w,h,spacing)
 for tx=0,w-1 do for tz=0,h-1 do for dx=-1,1 do for dz=-1,1 do
  SpawnPrefab('farm_soil').Transform:SetPosition(x+tx*4+dx*(spacing or 4/3),0,z+tz*4+dz*(spacing or 4/3))
 end end end end
end
function drive_at(x,z)inst.x=x;inst.z=z;return Drive.WorkTile(inst,x,z) end
function seeder(counts,season)
 inst=make_inst(counts,season or 'autumn');inst._attachment_type='seeder'
 inst.DoPeriodicTask=function(_,_,fn)return {fn=fn,Cancel=function()end} end
 Drive.SetWorking(inst,true);return inst
end
function finish()
 local b=inst._block;for _,t in ipairs(b.tiles) do drive_at(t.x,t.z) end;return b
end
function used()
 local counts={};for _,p in ipairs(inst._block.slots) do if p.crop then counts[p.crop]=(counts[p.crop] or 0)+1 end end;return counts
end
''')
 def run_lua(self,s):self.lua.execute(s)
 def test_four_unrecorded_tiles_fill_without_confirmation_and_use_both_seed_types(self):
  self.run_lua('''field(0,0,2,2);seeder({tomato=20,potato=20})
assert(drive_at(0,0));local b=finish();local counts=used()
assert(b.dynamic and b.automatic and b.confirmed and b.done==32 and crop_count()==32)
assert(counts.tomato==16 and counts.potato==16 and inst._working)
assert(inst._fuel:value()==768 and inst.components.aom_attachment_store:GetSeedCount()==8)
local before=inst._fuel:value();drive_at(0,0);assert(inst._fuel:value()==before and inst._working)
''')
 def test_single_tile_mixes_large_and_unequal_stocks(self):
  for counts in ({'tomato':40,'potato':40},{'tomato':20,'potato':40},{'tomato':40,'potato':20}):
   self.setUp();self.lua.globals().stock=self.lua.table_from(counts)
   self.run_lua('''field(0,0,1,1);seeder(stock);assert(drive_at(0,0));local b=finish();local n=used()
assert(b.total==8 and b.done==8 and n.tomato==4 and n.potato==4 and not b.slots[5].crop and Dynamic.Validate(b))
''')
 def test_sparse_stock_keeps_family_groups_without_requiring_full_field_stock(self):
  self.run_lua('''field(0,0,2,2);seeder({tomato=4,potato=4})
assert(drive_at(0,0));local b=finish();assert(b.total==8 and b.done==8)
assert(inst.components.aom_attachment_store:GetSeedCount()==0 and crop_count()==8)
''')
 def test_three_crop_tails_are_used_and_packed_into_two_tiles(self):
  self.run_lua('''field(0,0,2,2);seeder({carrot=4,corn=4,potato=4})
assert(drive_at(0,0));local b=finish();assert(b.done==12 and Dynamic.Validate(b))
local occupied=0;for t=1,#b.tiles do for s=1,9 do if b.slots[(t-1)*9+s].crop then occupied=occupied+1;break end end end
assert(occupied==2 and inst.components.aom_attachment_store:GetSeedCount()==0)
''')
 def test_insufficient_families_and_random_seed_never_spend_resources(self):
  self.run_lua('''field(0,0,1,1);seeder({tomato=3,potato=3,randomseed=40})
local count=inst.components.aom_attachment_store:GetSeedCount();local ok,reason=drive_at(0,0)
assert(not ok and reason=='MISSING_SEEDS' and not inst._working)
assert(not inst._block and crop_count()==0 and inst._fuel:value()==800)
assert(inst.components.aom_attachment_store:GetSeedCount()==count)
''')
 def test_different_species_cannot_be_combined_to_fake_a_family(self):
  self.run_lua('''field(0,0,1,1);seeder({tomato=4,potato=2,eggplant=2})
local ok,why=drive_at(0,0);assert(not ok and why=='NO_BALANCED_COMBO' and not inst._block and crop_count()==0)
local n=inst.components.aom_attachment_store:CountSeedsByCrop(require('aom_seed_strategy').GetCropOfSeedItem)
assert(n.potato==2 and n.eggplant==2)
''')
 def test_out_of_season_seeds_remain_untouched(self):
  self.run_lua('''field(0,0,1,1);seeder({tomato=40,carrot=4,potato=4,asparagus=4},'winter');field(4,0,1,1)
assert(drive_at(0,0));assert(finish().done==12 and used().potato==4 and not used().tomato)
''')
 def test_legacy_matching_seedlings_only_need_missing_seeds(self):
  c=self.w.combo('autumn-01-02');inst=self.w.make({'tomato':4,'potato':4});self.w.bind(inst,c)
  self.lua.globals().inst=inst
  self.run_lua('''field(0,0,1,1)
local slots=Block.WorldSlots(inst._block)
for i=1,2 do local p=slots[i];Block.FindSoilAt(p.x,p.z):Remove()
 SpawnPrefab('farm_plant_'..p.crop).Transform:SetPosition(p.x,0,p.z)
 local seed=inst.components.aom_attachment_store:TakeSeedOfCrop(p.crop,require('aom_seed_strategy').GetCropOfSeedItem);seed:Remove()
end
inst._attachment_type='seeder';assert(drive_at(0,0))
assert(crop_count()==8 and inst._block.done==8 and inst.components.aom_attachment_store:GetSeedCount()==0)
''')
 def test_missing_reserved_seed_stops_and_refill_resumes_the_same_plan(self):
  self.run_lua('''field(0,0,2,2);seeder({tomato=16,potato=16});assert(drive_at(0,0))
local b=inst._block;local store=inst.components.aom_attachment_store;local saved
for _,item in ipairs(store:ListSeeds()) do if item.prefab=='potato_seeds' then saved=item;store.container:RemoveItem(item) end end
local fuel,count=inst._fuel:value(),crop_count();local ok,reason=drive_at(4,0)
assert(not ok and reason=='MISSING_SEEDS' and inst._block==b and not inst._working)
assert(crop_count()==count and inst._fuel:value()==fuel)
store.container:GiveItem(saved);Drive.SetWorking(inst,true);assert(finish()==b and b.done==32)
''')
 def test_corrupt_saved_coordinates_are_rejected(self):
  self.run_lua('''field(0,0,1,1);seeder({tomato=4,potato=4});assert(Drive.WorkHere(inst))
local data=Block.OnSave(inst);data.slots[1].x=999
local fresh=make_inst({},'autumn');Block.OnLoad(fresh,data);assert(not fresh._block)
''')
 def test_empty_stock_stops_without_spending_fuel(self):
  self.run_lua('''field(0,0,1,1);seeder({});drive_at(0,0)
assert(not inst._working and crop_count()==0 and inst._fuel:value()==800)
''')
 def test_native_callback_error_after_success_is_charged_once(self):
  self.run_lua('''field(0,0,1,1);seeder({tomato=4,potato=4})
local original=make_seed;local once=true
make_seed=function(crop,n)
 local item=original(crop,n);local plant=item.components.farmplantable.Plant
 item.components.farmplantable.Plant=function(...)
  local ok=plant(...);if once then once=false;error('native plant failed after spawning crop') end;return ok
 end;return item
end
local ok,reason=drive_at(0,0);assert(ok and reason=='WORK_ERROR' and not inst._working)
assert(crop_count()==1 and inst._fuel:value()==799)
Drive.SetWorking(inst,true);assert(drive_at(0,0))
assert(crop_count()==8 and inst._block.done==8 and inst._fuel:value()==792)
''')
 def test_new_and_harvested_regions_start_new_rounds(self):
  self.run_lua('''field(0,0,1,1);field(12,0,1,1);seeder({tomato=20,potato=20})
assert(drive_at(0,0));local first=inst._block;assert(first.done==8)
assert(drive_at(12,0));assert(inst._block~=first and crop_count()==16)
for _,v in ipairs(ENTITIES) do if v:IsValid() and v:HasTag('farm_plant') and v.x<4 then
 local x,_,z=v.Transform:GetWorldPosition();v:Remove();SpawnPrefab('farm_soil').Transform:SetPosition(x,0,z)
end end
assert(drive_at(0,0));assert(inst._block.done==8 and crop_count()==16)
''')
 def test_actual_soil_coordinates_and_new_stock_do_not_change_saved_plan(self):
  self.run_lua('''field(0,0,1,1,1.4);seeder({tomato=4,potato=4});assert(Drive.WorkHere(inst))
local data=Block.OnSave(inst);assert(data.dynamic and data.slots[1].x==-1.4)
inst.components.aom_attachment_store.container:GiveItem(make_seed('tomato',40))
local other=make_inst({},'autumn');other.components.aom_attachment_store=inst.components.aom_attachment_store
Block.OnLoad(other,data);inst=other;inst._attachment_type='seeder'
assert(drive_at(0,0));assert(inst._block.done==8 and used().potato==4 and used().tomato==4)
''')
 def test_conflicting_plants_and_weeds_are_preserved(self):
  self.run_lua('''field(0,0,1,1);seeder({tomato=40,potato=40})
local weed=SpawnPrefab('weed_ivy');weed.Transform:SetPosition(0,0,0)
assert(not drive_at(0,0));assert(weed:IsValid() and crop_count()==1 and inst._fuel:value()==800)
''')
