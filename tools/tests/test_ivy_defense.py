"""执行原版护田广播/根须/Combat伤害链，验证先除刺花、收割预检和破圈。"""
import unittest
import test_vehicle_damage as damage
import test_dashboard as dashboard


class IvyDefenseTests(unittest.TestCase):
    def setUp(self):
        damage.VehicleDamageTests.setUp(self)
        self.lua.execute('''
Native=dofile(REF..'/ivy_defense.lua');Defense=require('aom_weed_defense');Drive=require('aom_drive')
TUNING.FARM_PLANT_DEFENDER_SEARCH_DIST=10;TUNING.WEED_IVY_SNARE_DAMAGE=10
TheWorld.Map.IsPointNearHole=function()return false end
local spawn=SpawnPrefab;ROOTS={};PENDING={};DIG_ORDER={}
function SpawnPrefab(name)
 local e=spawn(name)
 if name=='ivy_snare' then
  e.components.inventoryitem=nil;e.replica.inventoryitem=nil
  native_combat(e,40);e:AddTag('groundspike');e.physics_active=true
  e.RestartSnare=function()end;e.KillOff=Native.KillOff
  e:ListenForEvent('death',Native.OnDeath)
  e.PushEvent=function(self,event,data)
   local callbacks={};for _,cb in ipairs(self.events[event] or {})do callbacks[#callbacks+1]=cb.fn end
   for _,fn in ipairs(callbacks)do fn(self,data)end
  end
  ROOTS[#ROOTS+1]=e
 end
 return e
end
function mature_ivy(x,z,full)
 local e=SpawnPrefab('weed_ivy');e.Transform:SetPosition(x or 0,0,z or 0);e.weed_def={}
 e.components.inventoryitem=nil;e.replica.inventoryitem=nil
 Native.Ivy.masterpostinit(e);if full~=false then Native.Ivy.OnMakeFullFn(e,true)end
 e.DoTaskInTime=function(self,delay,fn,...)
  local task={Cancel=function(self)self.cancelled=true end};PENDING[#PENDING+1]={source=self,fn=fn,args={...},task=task};return task
 end
 e:AddComponent('workable');e.components.workable:SetWorkAction(ACTIONS.DIG);e.components.workable:SetWorkLeft(1)
 e.components.workable:SetOnFinishCallback(function(v,worker)
  DIG_ORDER[#DIG_ORDER+1]=v.prefab;Native.Broadcast(v,worker);v:Remove()
 end)
 return e
end
function crop(x,z)
 local e=SpawnPrefab('farm_plant_tomato');e.Transform:SetPosition(x or 0,0,z or 0)
 local picked=false;e.components.pickable={CanBePicked=function()return not picked end,
  Pick=function(_,worker)picked=true;Native.Broadcast(e,worker)end}
 return e
end
function ordinary_weed(x,z)
 local e=mature_ivy(x,z,false);e.prefab='weed_tillweed';return e
end
function ivy_loot(e)
 local d={};e.components.lootdropper=d
 function d:SpawnLootPrefab(name)
  local item=SpawnPrefab(name);item.Transform:SetPosition(e.Transform:GetWorldPosition());return item
 end
 e.components.workable:SetOnFinishCallback(function(v,worker)
  d:SpawnLootPrefab('twigs');DIG_ORDER[#DIG_ORDER+1]=v.prefab;Native.Broadcast(v,worker);v:Remove()
 end)
 return d
end
function attach(name)
 if t:GetAttachment()then assert(t:DetachAttachment(nil))end
 local item=SpawnPrefab(name);assert(t:AttachAttachment(nil,item));return item
end
function run_attacks()
 for _,task in ipairs(PENDING)do if task.source:IsValid() and not task.task.cancelled then task.fn(task.source,unpack(task.args))end end
 PENDING={}
end
''')
    run_lua=damage.VehicleDamageTests.run_lua

    def test_native_mature_ivy_reacts_to_plant_work_and_damage_redirects_to_vehicle(self):
        self.run_lua('''
local ivy=mature_ivy(1,0);ride();assert(#ROOTS==0)
Native.Broadcast(crop(0,0),player);assert(#ROOTS==6)
run_attacks();assert(hp(t)==590 and hp(player)==150)
require('aom_vehicle_motion').Update(t)
for _,root in ipairs(ROOTS)do assert(root.components.health:IsDead() and not root.physics_active)end
assert(player.components.rider:IsRiding() and hp(t)==590)
''')

    def test_harvest_stops_before_pick_or_cost_until_weeder_removes_mature_ivy(self):
        self.run_lua('''
local harvester=attach('aom_harvester');local ivy=mature_ivy(1,0);local plant=crop(0,0);ride();t:SetWorking(true)
local worked,reason=Drive.WorkTile(t,0,0)
assert(not worked and reason=='IVY_THREAT' and not t._working and #ROOTS==0)
assert(plant.components.pickable:CanBePicked() and ivy:IsValid())
assert(t._fuel:value()==400 and t.components.finiteuses:GetUses()==1000 and harvester.components.finiteuses:GetUses()==100)
assert(string.find(require('aom_work_status').Describe(t),'除草机',1,true))
attach('aom_weeder');assert(Drive.WorkTile(t,0,0) and not ivy:IsValid())
attach('aom_harvester');assert(Drive.WorkTile(t,0,0) and not plant.components.pickable:CanBePicked())
run_attacks();assert(hp(t)==600 and #ROOTS==0 and t._fuel:value()==398)
''')

    def test_weeder_clears_mature_ivy_before_other_weeds_and_pending_attack_dies_with_source(self):
        self.run_lua('''
attach('aom_weeder');ride()
local other=mature_ivy(0,0,false);other.prefab='weed_tillweed'
local a=mature_ivy(1,0);local b=mature_ivy(-1,0)
assert(Drive.WorkTile(t,0,0))
assert(DIG_ORDER[1]=='weed_ivy' and DIG_ORDER[2]=='weed_ivy' and DIG_ORDER[3]=='weed_tillweed')
assert(not a:IsValid() and not b:IsValid() and not other:IsValid())
run_attacks();require('aom_vehicle_motion').Update(t)
assert(hp(t)==600 and t._fuel:value()==399)
for _,root in ipairs(ROOTS)do assert(not root.physics_active)end
''')

    def test_harvester_never_breaks_existing_roots_even_when_stopped_or_turning(self):
        self.run_lua('''
attach('aom_harvester');ride()
local own=SpawnPrefab('ivy_snare');own.target=player
local vehicle_root=SpawnPrefab('ivy_snare');vehicle_root.target=t
local foreign=SpawnPrefab('ivy_snare');foreign.target=make_player()
for _,working in ipairs({false,true,false})do
 t:SetWorking(working)
 assert(Defense.ClearSnares(t,player)==0)
 player.Transform:SetRotation(90)
 require('aom_vehicle_motion').Update(t)
 for _,root in ipairs({own,vehicle_root,foreign})do
  assert(not root.components.health:IsDead() and root.physics_active)
 end
end
assert(t._fuel:value()==400 and t:GetAttachment().components.finiteuses:GetUses()==100)
attach('aom_weeder');require('aom_vehicle_motion').Update(t)
assert(own.components.health:IsDead() and not own.physics_active)
assert(vehicle_root.components.health:IsDead() and not vehicle_root.physics_active)
assert(not foreign.components.health:IsDead() and foreign.physics_active)
''')

    def test_harvester_keeps_native_bindweed_damage_and_does_not_clear_new_trap(self):
        self.run_lua('''
attach('aom_harvester');ride();local ivy=mature_ivy(1,0)
Native.Broadcast(crop(0,0),player);assert(#ROOTS==6)
run_attacks();assert(hp(t)==590 and hp(player)==150)
require('aom_vehicle_motion').Update(t)
for _,root in ipairs(ROOTS)do
 assert(not root.components.health:IsDead() and root.physics_active)
end
assert(ivy:IsValid() and player.components.rider:IsRiding())
''')

    def test_immature_burning_and_plantkin_follow_native_exceptions(self):
        self.run_lua('''
local plant=crop(0,0);local ivy=mature_ivy(1,0,false)
assert(Defense.FindIvy(plant,player)==nil)
Native.Ivy.OnMakeFullFn(ivy,true);ivy.components.burnable={burning=true}
assert(Defense.FindIvy(plant,player)==nil)
ivy.components.burnable.burning=false;assert(Defense.FindIvy(plant,player)==ivy)
player:AddTag('plantkin');assert(Defense.FindIvy(plant,player)==nil)
Native.Broadcast(plant,player);assert(#ROOTS==0)
''')

    def test_search_is_centred_on_each_crop_and_does_not_dig_neighbor_weeds(self):
        self.run_lua('''
attach('aom_harvester');ride();local plant=crop(1.9,0);local ivy=mature_ivy(11.5,0)
assert(Defense.FindIvy(plant,player)==ivy)
assert(not Drive.WorkTile(t,0,0) and ivy:IsValid() and plant.components.pickable:CanBePicked())
ivy.Transform:SetPosition(12.01,0,0)
assert(Defense.FindIvy(plant,player)==nil and Drive.WorkTile(t,0,0) and ivy:IsValid())
''')

    def test_only_own_trap_is_broken_and_clients_do_not_modify_health_or_physics(self):
        self.run_lua('''
ride();local own=SpawnPrefab('ivy_snare');own.target=player
local foreign=SpawnPrefab('ivy_snare');foreign.target=make_player()
TheWorld.ismastersim=false;assert(Defense.ClearSnares(t,player)==0 and not own.components.health:IsDead())
TheWorld.ismastersim=true;assert(Defense.ClearSnares(t,player)==1)
assert(not own.physics_active and foreign.physics_active and not foreign.components.health:IsDead())
assert(Defense.ClearSnares(t,player)==0)
player.components.rider:ActualDismount()
local walking=SpawnPrefab('ivy_snare');walking.target=player
assert(Defense.ClearSnares(t,player)==0 and walking.physics_active)
''')

    def test_remote_search_uses_target_position_and_includes_exact_ten_units(self):
        self.run_lua('''
attach('aom_weeder');ride();local weed=ordinary_weed(1.9,0)
local boundary=mature_ivy(11.9,0);local beyond=mature_ivy(11.901,0)
local neighbor=ordinary_weed(4,0);local plant=crop(8,0)
assert(Drive.WorkTile(t,0,0))
assert(not boundary:IsValid() and not weed:IsValid() and beyond:IsValid())
assert(neighbor:IsValid() and plant.components.pickable:CanBePicked())
assert(DIG_ORDER[1]=='weed_ivy' and DIG_ORDER[2]=='weed_tillweed')
assert(t._fuel:value()==399 and t:GetAttachment().components.finiteuses:GetUses()==99)
''')

    def test_overlapping_searches_clear_remote_mutual_defenders_once_before_weeds(self):
        self.run_lua('''
attach('aom_weeder');ride();ordinary_weed(1,0);ordinary_weed(0,1)
local a=mature_ivy(7,0);local b=mature_ivy(8,0);local young=mature_ivy(9,0,false)
assert(Drive.WorkTile(t,0,0));assert(#DIG_ORDER==5)
for i=1,3 do assert(DIG_ORDER[i]=='weed_ivy')end
assert(not a:IsValid() and not b:IsValid() and not young:IsValid())
run_attacks();require('aom_vehicle_motion').Update(t)
assert(hp(t)==600 and t._fuel:value()==399)
for _,root in ipairs(ROOTS)do assert(not root.physics_active)end
''')

    def test_remote_ivy_does_not_start_work_without_a_local_weeding_target(self):
        self.run_lua('''
attach('aom_weeder');ride();local ivy=mature_ivy(8,0);crop(0,0)
assert(not Drive.WorkTile(t,0,0) and ivy:IsValid() and #DIG_ORDER==0)
assert(t._fuel:value()==400)
''')

    def test_unclearable_remote_ivy_blocks_batch_before_any_changes(self):
        self.run_lua('''
attach('aom_weeder');ride();local weed=ordinary_weed(0,0)
local a=mature_ivy(7,0);local b=mature_ivy(8,0);b.components.workable:SetWorkable(false)
t:SetWorking(true);local changed,reason=Drive.WorkTile(t,0,0)
assert(not changed and reason=='UNCLEARABLE_WEED' and not t._working)
assert(weed:IsValid() and a:IsValid() and b:IsValid() and #ROOTS==0 and #DIG_ORDER==0)
assert(t._fuel:value()==400)
''')

    def test_incomplete_remote_ivy_stops_before_ordinary_weeds_and_can_resume(self):
        self.run_lua('''
attach('aom_weeder');ride();local weed=ordinary_weed(0,0);local ivy=mature_ivy(8,0)
ivy.components.workable:SetWorkLeft(2)
ivy.components.workable:SetWorkMultiplierFn(function()return .5 end)
t:SetWorking(true);local changed,reason=Drive.WorkTile(t,0,0)
assert(changed and reason=='WEEDING_INCOMPLETE' and not t._working)
assert(ivy:IsValid() and weed:IsValid() and #DIG_ORDER==0 and #ROOTS==0)
assert(t._fuel:value()==399)
ivy.components.workable:SetWorkMultiplierFn(function()return 1 end)
t:SetWorking(true);assert(Drive.WorkTile(t,0,0))
assert(not ivy:IsValid() and not weed:IsValid() and t._fuel:value()==398)
''')

    def test_remote_ivy_loot_is_collected_without_taking_neighbor_ground_items(self):
        self.run_lua('''
attach('aom_weeder');ride();ordinary_weed(0,0);local ivy=mature_ivy(8,0)
ivy_loot(ivy);local old=SpawnPrefab('twigs');old.Transform:SetPosition(8,0,0)
assert(Drive.WorkTile(t,0,0))
assert(old.components.inventoryitem.owner==nil and old:IsValid())
local stored=0
for _,item in pairs(t.components.container.slots)do if item.prefab=='twigs' then stored=stored+1 end end
assert(stored==1 and t._fuel:value()==399)
''')

    def test_full_cargo_during_remote_clear_preserves_loot_and_stops_before_other_targets(self):
        self.run_lua('''
attach('aom_weeder');ride();local weed=ordinary_weed(0,0)
local a=mature_ivy(7,0);ivy_loot(a);local b=mature_ivy(8,0)
for i=1,t.components.container:GetNumSlots() do local item=SpawnPrefab('gears');item.components.stackable:SetStackSize(40)
 assert(t.components.container:GiveItem(item,i))end
t:SetWorking(true);local changed,reason=Drive.WorkTile(t,0,0)
assert(changed and reason=='CARGO_FULL' and not t._working)
assert(not a:IsValid() and b:IsValid() and weed:IsValid() and #DIG_ORDER==1)
local ground=0
for _,e in ipairs(ENTITIES)do if e:IsValid() and e.prefab=='twigs' and e.components.inventoryitem.owner==nil then ground=ground+1 end end
assert(ground==1 and t._fuel:value()==399)
run_attacks();require('aom_vehicle_motion').Update(t)
for _,root in ipairs(ROOTS)do assert(not root.physics_active)end
''')

    def test_callback_cannot_make_remote_ivy_into_a_crop_or_chase_it_outside_range(self):
        self.run_lua('''
attach('aom_weeder');ride();local weed=ordinary_weed(0,0)
local a=mature_ivy(7,0);local crop_ivy=mature_ivy(8,0);local moved=mature_ivy(9,0)
a.components.workable:SetOnFinishCallback(function(v)
 crop_ivy.components.farmplantstress={};moved.Transform:SetPosition(20,0,0);v:Remove()
end)
local changed,reason=Drive.WorkTile(t,0,0)
assert(changed and reason=='WEEDING_INCOMPLETE')
assert(crop_ivy:IsValid() and moved:IsValid() and weed:IsValid())
assert(crop_ivy.components.workable:GetWorkLeft()==1 and moved.components.workable:GetWorkLeft()==1)
''')

    def test_new_remote_ivy_from_callback_is_reported_incomplete(self):
        self.run_lua('''
attach('aom_weeder');ride();local weed=ordinary_weed(0,0);local born
weed.components.workable:SetOnFinishCallback(function(v)born=mature_ivy(8,0);v:Remove()end)
t:SetWorking(true);local changed,reason=Drive.WorkTile(t,0,0)
assert(changed and reason=='WEEDING_INCOMPLETE' and born:IsValid() and not t._working)
assert(t._fuel:value()==399)
''')

    def test_new_defender_during_ivy_callback_stops_before_ordinary_weeding(self):
        self.run_lua('''
attach('aom_weeder');ride();local weed=ordinary_weed(0,0);local ivy=mature_ivy(8,0);local born
ivy.components.workable:SetOnFinishCallback(function(v)born=mature_ivy(9,0);v:Remove()end)
t:SetWorking(true);local changed,reason=Drive.WorkTile(t,0,0)
assert(changed and reason=='WEEDING_INCOMPLETE' and not t._working)
assert(weed:IsValid() and born:IsValid() and #ROOTS==0 and t._fuel:value()==399)
t:SetWorking(true);assert(Drive.WorkTile(t,0,0) and not born:IsValid() and not weed:IsValid())
''')

    def test_scan_does_not_recurse_and_outer_defender_still_uses_escape_fallback(self):
        self.run_lua('''
attach('aom_weeder');ride();ordinary_weed(0,0)
local inner=mature_ivy(8,0);local outer=mature_ivy(17,0)
assert(Drive.WorkTile(t,0,0) and not inner:IsValid() and outer:IsValid())
run_attacks();assert(hp(t)==590 and #ROOTS==6)
require('aom_vehicle_motion').Update(t)
for _,root in ipairs(ROOTS)do assert(root.components.health:IsDead() and not root.physics_active)end
assert(outer:IsValid())
''')

    def test_remote_ivy_without_progress_is_free_and_does_not_expose_other_weeds(self):
        self.run_lua('''
attach('aom_weeder');ride();local weed=ordinary_weed(0,0);local ivy=mature_ivy(8,0)
ivy.components.workable:SetShouldRecoilFn(function()return true end)
t:SetWorking(true);local changed,reason=Drive.WorkTile(t,0,0)
assert(not changed and reason=='WEEDING_INCOMPLETE' and not t._working)
assert(weed:IsValid() and ivy:IsValid() and #ROOTS==0 and t._fuel:value()==400)
''')

    def test_remote_dig_error_keeps_actual_loot_and_restores_drop_callback(self):
        self.run_lua('''
attach('aom_weeder');ride();local weed=ordinary_weed(0,0);local ivy=mature_ivy(8,0)
local dropper=ivy_loot(ivy);local spawn=dropper.SpawnLootPrefab
ivy.components.workable:SetOnFinishCallback(function(v)
 dropper:SpawnLootPrefab('twigs');v:Remove();error('remote native callback failed')
end)
t:SetWorking(true);local changed,reason=Drive.WorkTile(t,0,0)
assert(changed and reason=='WORK_ERROR' and not t._working)
assert(not ivy:IsValid() and weed:IsValid() and dropper.SpawnLootPrefab==spawn)
assert(t._fuel:value()==399)
local ground=0
for _,e in ipairs(ENTITIES)do if e:IsValid() and e.prefab=='twigs' and e.components.inventoryitem.owner==nil then ground=ground+1 end end
assert(ground==1)
''')


class FertilizerDashboardTests(unittest.TestCase):
    setUp=dashboard.DashboardTests.setUp
    run_lua=dashboard.DashboardTests.run_lua

    def test_nine_stacks_of_fertilizer_show_360_on_cargo(self):
        self.run_lua('''
attach('aom_fertilizer')
for slot=1,9 do
 local item=SpawnPrefab('poop');item.components.stackable:SetStackSize(40)
 assert(t.components.container:GiveItem(item,slot))
end
hud:Refresh(t)
assert(hud.badges.cargo:GetText()=='360' and t._fertilizeruses_net:value()==360)
assert(hud.badges.cargo:GetTooltip()=='货仓：9/15格'..string.char(10)..'物品总数 360（含堆叠）')
assert(hud.strip==nil)
''')

    def test_all_six_have_no_status_strip_and_fertilizer_supply_is_on_cargo(self):
        self.run_lua('''
for _,name in ipairs({'aom_landclearer','aom_seeder','aom_irrigator','aom_fertilizer','aom_weeder','aom_harvester'})do
 attach(name);hud:Refresh(t)
 assert(hud.strip==nil and hud.resource==nil and hud.worklamp==nil)
end
attach('aom_fertilizer')
local fertilizer=SpawnPrefab('fertilizer');fertilizer:AddComponent('finiteuses');fertilizer.components.finiteuses:SetMaxUses(4);fertilizer.components.finiteuses:SetUses(3)
fertilizer.components.fertilizer={nutrients={0,0,8}};fertilizer:AddTag('fertilizer')
assert(t.components.container:GiveItem(fertilizer,1));hud:Refresh(t)
assert(hud.badges.cargo:GetText()=='1')
assert(t._fertilizeruses_net:value()==3 and not string.find(hud.badges.cargo:GetTooltip(),'肥料剩余',1,true))
assert(hud.badges.tool:GetText()=='100' and hud.seedcontrols==nil)
fertilizer.PushEvent=function(self,event,data)
 local callbacks={};for _,cb in ipairs(self.events[event] or {})do callbacks[#callbacks+1]=cb.fn end
 for _,fn in ipairs(callbacks)do fn(self,data)end
end
fertilizer.components.finiteuses:SetUses(2);hud:Refresh(t)
assert(hud.badges.cargo:GetText()=='1' and t._fertilizeruses_net:value()==2)
''')


if __name__=='__main__':unittest.main()
