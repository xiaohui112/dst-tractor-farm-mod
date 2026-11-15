"""腐烂采收与残株DIG分工；执行本机原版腐烂标记、掉落、Pickable/Workable及货仓。"""
import unittest
import test_work_cargo as cargo
import test_ivy_defense as ivy


class CropRemainsTests(unittest.TestCase):
    def setUp(self):
        cargo.WorkCargoTests.setUp(self)
        self.lua.execute('''
Crops=require('aom_crop_state');NativeRot=dofile(REF..'/crop_remains.lua')
local Pickable=dofile(REF..'/pickable.lua')
local NativeFertilizer=dofile(REF..'/fertilizer.lua')
local spawn=SpawnPrefab
TUNING.FARM_PLANT_DEFENDER_SEARCH_DIST=10
TUNING.SPOILED_FOOD_NUTRIENTS={0,8,0} -- 本机tuning.lua原值。
function SpawnPrefab(name)
 local item=spawn(name)
 if name=='spoiled_food' then
  item:AddComponent('stackable');item.components.fertilizer=NativeFertilizer(item)
  item.components.fertilizer:SetNutrients(TUNING.SPOILED_FOOD_NUTRIENTS)
 end
 return item
end
LuckFormulas={FruitFlyOnPickedWeed={}}
TryLuckRoll=function()return false end
function rotted(x,z,canpick)
 local v=crop('tomato',x,z,false)
 v.plant_def={product='tomato',seed='tomato_seeds',product_oversized='tomato_oversized',
  loot_oversized_rot={'spoiled_food','spoiled_food','spoiled_food'}}
 v.components.growable={stages={{name='rotten'}},stage=1,GetCurrentStageData=NativeRot.GetCurrentStageData}
 local d=v.components.lootdropper;d.inst=v
 function d:SetLoot(loot)self.loot=loot end
 local generate=d.GenerateLoot;local drop=d.DropLoot
 function d:GenerateLoot()NativeRot.SetupLoot(self);return generate(self)end
 function d:DropLoot(...)NativeRot.SetupLoot(self);return drop(self,...)end
 local add=v.AddComponent
 function v:AddComponent(name)
  if name=='pickable' then self.components.pickable=Pickable(self)else add(self,name)end
 end
 v.components.pickable=nil
 NativeRot.MakeRotten(v,true);NativeRot.MakePickable(v,true)
 if canpick==false then v.components.pickable=nil end
 v:AddComponent('workable');v.components.workable:SetWorkAction(ACTIONS.DIG)
 v.components.workable:SetWorkLeft(1);v.components.workable:SetOnFinishCallback(NativeRot.Dig)
 return v
end
function stock(slot,name,n)
 local old=t.components.container:RemoveItemBySlot(slot);if old then old:Remove()end
 local e=SpawnPrefab(name);e.components.stackable:SetStackSize(n)
 assert(t.components.container:GiveItem(e,slot));return e
end
''')

    run_lua=cargo.WorkCargoTests.run_lua

    def test_rotten_crop_harvest_uses_native_loot_and_costs_one_batch(self):
        self.run_lua('''
local plants={}
for x=-1,1 do for z=-1,1 do plants[#plants+1]=rotted(x,z,true)end end
local picker
plants[1]:ListenForEvent('picked',function(_,data)picker=data.picker end)
t:SetWorking(true);assert(Drive.WorkTile(t,0,0))
for _,v in ipairs(plants)do assert(not v:IsValid())end
assert(picker==player and quantity(t,'spoiled_food')==9)
assert(quantity(t,'tomato')==0 and quantity(t,'tomato_seeds')==0)
assert(t._working and t._fuel:value()==399 and t:GetAttachment().components.finiteuses:GetUses()==39)
assert(not Drive.WorkTile(t,0,0) and quantity(t,'spoiled_food')==9 and t._fuel:value()==399)
''')

    def test_full_slots_merge_rot_only_into_rot_stack_and_skip_when_no_matching_stack(self):
        self.run_lua('''
fill();stock(1,'tomato',39);local plant=rotted(0,0,true)
t:SetWorking(true);assert(not Drive.WorkTile(t,0,0) and plant:IsValid() and t._working)
assert(t._fuel:value()==400 and quantity(t,'tomato')==39)
stock(1,'tomato',40);stock(2,'spoiled_food',39)
local changed,why=Drive.WorkTile(t,0,0)
assert(changed and why=='CARGO_FULL' and not plant:IsValid() and not t._working)
assert(quantity(t,'spoiled_food')==40 and quantity(t,'tomato')==40 and t._fuel:value()==399)
''')

    def test_rotten_stage_without_native_tag_uses_rot_stack_filter(self):
        self.run_lua('''
fill();stock(1,'spoiled_food',38);local plant=rotted(0,0,true)
plant:RemoveTag('farm_plant_killjoy')
-- 兼容其他Mod仅提供rotten阶段、自行定义腐烂掉落的作物。
plant.components.lootdropper.GenerateLoot=function()return {'spoiled_food'}end
assert(Drive.WorkTile(t,0,0) and not plant:IsValid())
assert(quantity(t,'spoiled_food')==39 and quantity(t,'tomato')==0)
''')

    def test_weeder_digs_only_unharvestable_remains_and_keeps_harvestable_rotten_crop(self):
        self.run_lua('''
tool('aom_weeder');local collectable=rotted(1,0,true);local remains=rotted(0,0,false)
local healthy=crop('tomato',0,1,false);healthy.components.pickable:MakeEmpty()
local calls=0;remains:ListenForEvent('worked',function()calls=calls+1 end)
t:SetWorking(true);assert(Drive.WorkTile(t,0,0) and not remains:IsValid())
assert(collectable:IsValid() and healthy:IsValid() and quantity(t,'spoiled_food')==1)
assert(t._fuel:value()==399 and t:GetAttachment().components.finiteuses:GetUses()==49)
assert(not Drive.WorkTile(t,0,0) and t._working and t._fuel:value()==399)
tool('aom_harvester');assert(Drive.WorkTile(t,0,0) and not collectable:IsValid() and healthy:IsValid())
assert(quantity(t,'spoiled_food')==2)
''')

    def test_dead_stage_or_dead_tag_is_required_and_healthy_or_withered_crop_is_preserved(self):
        self.run_lua('''
tool('aom_weeder')
for _,name in ipairs({'sprout','small','med','full','withered'})do
 local plant=rotted(0,0,false);NativeRot.MakeRotten(plant,false)
 plant.components.growable.stages[1].name=name
 assert(not Crops.CanClearRemains(plant) and not Drive.WorkTile(t,0,0) and plant:IsValid())
 plant:Remove()
end
local dead=rotted(0,0,false);NativeRot.MakeRotten(dead,false)
dead.components.growable.stages[1].name='dead'
assert(Crops.CanClearRemains(dead) and Drive.WorkTile(t,0,0) and not dead:IsValid())
local tagged=rotted(0,0,false);NativeRot.MakeRotten(tagged,false)
tagged.components.growable=nil;tagged:AddTag('deadplant')
assert(Crops.CanClearRemains(tagged) and Drive.WorkTile(t,0,0) and not tagged:IsValid())
local healthdead=rotted(0,0,false);NativeRot.MakeRotten(healthdead,false)
healthdead.components.growable=nil;healthdead.components.health={IsDead=function()return true end}
assert(Crops.CanClearRemains(healthdead) and Drive.WorkTile(t,0,0) and not healthdead:IsValid())
''')

    def test_remains_that_regrow_during_previous_dig_are_rechecked_and_preserved(self):
        self.run_lua('''
tool('aom_weeder');local a=rotted(0,0,false);local b=rotted(1,0,false)
a.components.workable:SetOnFinishCallback(function(v,worker)
 NativeRot.Dig(v,worker)
 NativeRot.MakeRotten(b,false);b.components.growable.stages[1].name='sprout'
end)
assert(Drive.WorkTile(t,0,0) and not a:IsValid() and b:IsValid())
assert(b.components.workable:GetWorkLeft()==1 and quantity(t,'spoiled_food')==1)
assert(t._fuel:value()==399 and t:GetAttachment().components.finiteuses:GetUses()==49)
''')

    def test_temporarily_disabled_or_stuck_rotten_crop_is_never_dug(self):
        self.run_lua('''
tool('aom_weeder');local plant=rotted(0,0,true)
plant.components.pickable:MakeEmpty();plant.components.pickable.caninteractwith=false
assert(not Crops.CanClearRemains(plant) and not Drive.WorkTile(t,0,0) and plant:IsValid())
plant.components.pickable.caninteractwith=true;plant.components.pickable.stuck=true
assert(not Crops.CanClearRemains(plant) and not Drive.WorkTile(t,0,0) and plant:IsValid())
assert(t._fuel:value()==400 and t:GetAttachment().components.finiteuses:GetUses()==50)
''')

    def test_healthy_crop_with_weed_tag_and_nonfarm_dead_plants_are_preserved(self):
        self.run_lua('''
tool('aom_weeder');local healthy=crop('tomato',0,0,false)
healthy:AddTag('weed');healthy.components.pickable:MakeEmpty()
local wild=SpawnPrefab('grass');wild.components.inventoryitem=nil
wild:AddTag('deadplant');wild:AddTag('plant')
wild:AddComponent('workable');wild.components.workable:SetWorkAction(ACTIONS.DIG)
wild.components.workable:SetWorkLeft(1)
assert(not Drive.WorkTile(t,0,0) and healthy:IsValid() and wild:IsValid())
assert(t._fuel:value()==400)
''')

    def test_no_dig_action_or_no_worker_preserves_remains_and_uses_no_resources(self):
        self.run_lua('''
tool('aom_weeder');local remains=rotted(0,0,false)
remains.components.workable:SetWorkAction(ACTIONS.HAMMER)
t:SetWorking(true);local changed,why=Drive.WorkTile(t,0,0)
assert(not changed and why=='UNCLEARABLE_WEED' and remains:IsValid() and not t._working)
remains.components.workable:SetWorkAction(ACTIONS.DIG)
local worked,reason=Farm.Weed(0,0,0,nil,t)
assert(not worked and reason=='NO_WORKER' and remains:IsValid())
assert(t._fuel:value()==400 and t:GetAttachment().components.finiteuses:GetUses()==50)
''')

    def test_full_cargo_after_dig_leaves_real_loot_and_retry_does_not_duplicate(self):
        self.run_lua('''
tool('aom_weeder');fill();local a=rotted(0,0,false);local b=rotted(1,0,false)
t:SetWorking(true);local changed,why=Drive.WorkTile(t,0,0)
assert(changed and why=='CARGO_FULL' and not a:IsValid() and b:IsValid() and not t._working)
assert(quantity(nil,'spoiled_food')==1 and t._fuel:value()==399)
t.components.container:RemoveItemBySlot(1):Remove()
t:SetWorking(true);assert(Drive.WorkTile(t,0,0) and not b:IsValid())
assert(quantity(t,'spoiled_food')==2 and quantity(nil,'spoiled_food')==0 and t._fuel:value()==398)
assert(not Drive.WorkTile(t,0,0) and quantity(t,'spoiled_food')==2)
''')

    def test_tile_border_no_click_and_inlimbo_remains_are_not_swept(self):
        self.run_lua('''
tool('aom_weeder');local corner=rotted(1.9,1.9,false);local neighbor=rotted(2.1,0,false)
local hidden=rotted(0,0,false);hidden:AddTag('NOCLICK')
local stored=rotted(0,0,false);stored:AddTag('INLIMBO')
assert(Drive.WorkTile(t,0,0) and not corner:IsValid())
assert(neighbor:IsValid() and hidden:IsValid() and stored:IsValid())
assert(quantity(t,'spoiled_food')==1)
''')

    def test_recovered_rot_is_native_fertilizer_and_consumes_one_stack_unit(self):
        self.run_lua('''
rotted(0,0,true);rotted(1,0,true);assert(Drive.WorkTile(t,0,0))
local store=t.components.aom_attachment_store
assert(store:GetFertilizerCount()==2)
local n={100,92,100}
TheWorld.components=TheWorld.components or {}
TheWorld.components.farming_manager={GetTileNutrients=function()return unpack(n)end,
 AddTileNutrients=function(_,tx,tz,a,b,c)n={n[1]+a,n[2]+b,n[3]+c}end}
TheWorld.Map.GetTileCoordsAtPoint=function()return 0,0 end
tool('aom_fertilizer');t:SetWorking(true);assert(Drive.WorkTile(t,0,0))
assert(n[1]==100 and n[2]==100 and n[3]==100)
assert(quantity(t,'spoiled_food')==1 and store:GetFertilizerCount()==1)
''')


class RemainsIvyTests(unittest.TestCase):
    setUp=ivy.IvyDefenseTests.setUp
    run_lua=ivy.IvyDefenseTests.run_lua

    def test_remains_dig_clears_defenders_in_ten_unit_range_first(self):
        self.run_lua('''
attach('aom_weeder');ride();local remains=crop(0,0)
remains.components.pickable=nil;remains:AddTag('farm_plant_killjoy')
remains:AddComponent('workable');remains.components.workable:SetWorkAction(ACTIONS.DIG)
remains.components.workable:SetWorkLeft(1)
remains.components.workable:SetOnFinishCallback(function(v,worker)
 DIG_ORDER[#DIG_ORDER+1]='remains';Native.Broadcast(v,worker);v:Remove()
end)
local defender=mature_ivy(10,0)
assert(Drive.WorkTile(t,0,0) and not remains:IsValid() and not defender:IsValid())
assert(DIG_ORDER[1]=='weed_ivy' and DIG_ORDER[2]=='remains')
run_attacks();assert(hp(t)==600 and t._fuel:value()==399)
''')


if __name__=='__main__':unittest.main()
