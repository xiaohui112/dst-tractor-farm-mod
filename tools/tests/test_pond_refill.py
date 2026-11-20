"""骑乘池塘补水：实际 Mod 提示/动作、原版水源/骑手/水箱/容器与存读档。"""
import unittest
import test_lifecycle_flow as lifecycle


class PondRefillTests(unittest.TestCase):
    def setUp(self):
        engine=lifecycle.LifecycleFlowTests();engine.setUp();self.lua=engine.lua
        self.lua.execute('''
local WaterSource=dofile(REF..'/watersource.lua')
t=deploy_kit(kit,0,0,player)
tank=SpawnPrefab('aom_irrigator');assert(t:AttachAttachment(nil,tank))
store=t.components.aom_attachment_store
tank.components.finiteuses:SetUses(0)
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
function player:GetPhysicsRadius()return .5 end
pond=CreateEntity();pond.prefab='pond';pond:AddTag('pond');pond.Transform:SetPosition(4,0,0)
function pond:GetPhysicsRadius()return 1.5 end
pond.components.watersource=WaterSource(pond)
water_uses=0;pond.components.watersource.onusefn=function()water_uses=water_uses+1 end
refill=ACTION_DEFS.AOM_POND_REFILL
function pond_actions(right)
 local actions={};SCENE_HOOKS.watersource(pond,player,actions,right~=false);return actions
end
function begin_pond()return refill.fn({doer=player,target=pond})end
function fill_pond() -- 本文件校验补水完成后的权限/资源；显式推进到补水完成，不假定瞬时加满。
 local ok=begin_pond()
 if ok then
  local previous=GetTime;local finish=t._aom_pond_refill.started+t._aom_pond_refill.duration
  GetTime=function()return finish end;require('aom_pond_refill').Update(t);GetTime=previous
 end
 return ok
end
''')

    def run_lua(self,source):self.lua.execute(source)

    def test_right_click_fills_every_native_pond_without_dismounting_or_using_items(self):
        self.run_lua('''
local messages={};player.components.talker={Say=function(_,text)messages[#messages+1]=text end}
assert(refill.mount_valid and refill.distance==3 and refill.label=='补满水箱')
local handlers=0
for _,handler in ipairs(ACTION_HANDLERS)do
 if handler.action==refill then assert(handler.state=='doshortaction');handlers=handlers+1 end
end
assert(handlers==2)
local fuel=t._fuel:value();local durability=t.components.finiteuses:GetUses()
for i,name in ipairs({'pond','pond_mos','pond_cave'})do
 pond.prefab=name;tank.components.finiteuses:SetUses(13)
 local actions=pond_actions();assert(#actions==1 and actions[1]==refill)
 assert(fill_pond() and store:GetWater()==400 and t._water_net:value()==400)
 assert(player.components.rider:GetMount()==t and t._rider==player and water_uses==i)
 assert(t._fuel:value()==fuel and t.components.finiteuses:GetUses()==durability)
 assert(#messages==i and string.find(messages[i],'正在补水',1,true))
end
''')

    def test_full_tank_is_hidden_and_does_not_use_source_again(self):
        self.run_lua('''
assert(fill_pond() and water_uses==1)
assert(#pond_actions()==0 and not fill_pond())
assert(store:GetWater()==400 and water_uses==1)
''')

    def test_refill_distance_matches_action_range_and_collision_radii(self):
        self.run_lua('''
pond.Transform:SetPosition(5.1,0,0)
assert(not fill_pond() and store:GetWater()==0 and water_uses==0)
pond.Transform:SetPosition(5,0,0)
assert(fill_pond() and store:GetWater()==400 and water_uses==1)
''')

    def test_frozen_unavailable_pond_and_thaw_follow_native_watersource(self):
        self.run_lua('''
pond.components.watersource.available=false
assert(not pond:HasTag('watersource') and #pond_actions()==0 and not fill_pond())
assert(store:GetWater()==0 and water_uses==0)
pond.components.watersource.available=true
assert(pond:HasTag('watersource') and #pond_actions()==1 and fill_pond())
assert(store:GetWater()==400 and water_uses==1)
''')

    def test_nonpond_and_removed_or_forged_sources_are_rejected(self):
        self.run_lua('''
pond:RemoveTag('pond');assert(#pond_actions()==0 and not fill_pond())
pond:AddTag('pond');local source=pond.components.watersource
pond.components.watersource=nil;assert(not fill_pond())
pond.components.watersource=source;pond:Remove()
assert(not fill_pond() and store:GetWater()==0 and water_uses==0)
''')

    def test_actual_driver_and_installed_irrigator_are_required(self):
        self.run_lua('''
assert(#pond_actions(false)==0)
t._atttype_net:set('seeder');assert(#pond_actions()==0)
t._atttype_net:set('irrigator')
local other=make_player()
other.components.rider.IsRiding=function()return true end
other.components.rider.GetMount=function()return t end
assert(not refill.fn({doer=other,target=pond}))
local tool=t:GetAttachment();assert(t:DetachAttachment(player))
assert(not fill_pond());assert(t:AttachAttachment(nil,SpawnPrefab('aom_seeder')))
t._attachment_type='irrigator';assert(not fill_pond())
local wrong=t:GetAttachment();assert(t:DetachAttachment(player));wrong:Remove()
assert(t:AttachAttachment(nil,tool))
player.components.rider:ActualDismount()
assert(#pond_actions()==0 and not fill_pond() and water_uses==0)
''')

    def test_dead_or_destroyed_vehicle_and_ghost_driver_cannot_refill(self):
        self.run_lua('''
t._destroyed=true;assert(not fill_pond());t._destroyed=false
local dead=t.components.health.IsDead;t.components.health.IsDead=function()return true end
assert(not fill_pond());t.components.health.IsDead=dead
player:AddTag('playerghost');assert(not fill_pond())
assert(store:GetWater()==0 and water_uses==0)
''')

    def test_client_prompt_uses_only_tags_replica_and_network_fields(self):
        self.run_lua('''
TheWorld.ismastersim=false
local tc,pc=t.components,pond.components;t.components={};pond.components={}
assert(#pond_actions()==1)
t._water_net:set(400);assert(#pond_actions()==0)
t.components=tc;pond.components=pc
''')

    def test_filling_stops_work_and_requires_f_to_resume(self):
        self.run_lua('''
store:AddWater(1);t:SetWorking(true);local task=t._worktask
assert(fill_pond() and not t._working and task.cancelled)
press_f(player);release_f(player);assert(t._working)
''')

    def test_pond_fill_survives_native_container_save_reload(self):
        self.run_lua('''
assert(fill_pond())
local record=clone(t:GetSaveRecord());t:Remove()
local restored=SpawnSaveRecord(record)
assert(restored.components.aom_attachment_store:GetWater()==400)
assert(restored.components.aom_attachment_store:GetWaterMax()==400)
assert(restored:GetAttachment().prefab=='aom_irrigator')
''')

    def test_pond_action_and_overhead_feedback_are_localized(self):
        self.run_lua('''
GetModConfigData=function(name)if name=='LANGUAGE' then return 'en' end end
dofile(MOD..'/modmain.lua');refill=ACTION_DEFS.AOM_POND_REFILL
assert(refill.label=='Fill water tank')
local text;player.components.talker={Say=function(_,msg)text=msg end}
assert(fill_pond() and string.find(text,'Refilling',1,true))
''')


if __name__=='__main__':unittest.main()
