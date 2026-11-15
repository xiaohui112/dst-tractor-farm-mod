"""执行原版失败文案选择/玩家失败回调和BufferedAction；连续作业/RPC只喊一次。"""
import unittest
import test_world_equipment as world
import test_ivy_defense as ivy


class OverheadFeedbackTests(unittest.TestCase):
    setUp = world.WorldEquipmentTests.setUp
    run_lua = world.WorldEquipmentTests.run_lua

    def prepare_speech(self):
        self.run_lua('''
Speech=dofile(REF..'/action_speech.lua');Feedback=require('aom_feedback');Status=require('aom_work_status')
player.prefab='wilson';MESSAGES={}
player.components.talker={Say=function(_,text)MESSAGES[#MESSAGES+1]=text end}
STRINGS.CHARACTERS.WILSON={ACTIONFAIL={GENERIC={GENERIC='vanilla generic'},MOUNT={GENERIC='vanilla mount'}}}
STRINGS.CHARACTERS.WENDY={ACTIONFAIL={GENERIC={GENERIC='wendy generic'}}}
local actions={};for _,id in ipairs({'AOM_REFUEL','AOM_REPAIR','AOM_LOAD','AOM_ATTACH','AOM_POND_REFILL','AOM_STORAGE'})do actions[#actions+1]=ACTION_DEFS[id]end
Feedback.InstallActions(actions)
function fail_action(id,target,item,reason)
 local action=ACTION_DEFS[id]
 local ok,actual=action.fn({doer=player,target=target,invobject=item})
 assert(not ok and actual==reason,tostring(actual))
 assert(#MESSAGES==0,'action fn must not speak before native failure callback')
 local buffered={action=action,autoequipped=false}
 Speech.OnActionFailed(player,{action=buffered,reason=actual})
 assert(#MESSAGES==1 and MESSAGES[1]==Feedback.Text(reason))
 MESSAGES={}
end
''')

    def test_native_action_failed_selects_specific_refuel_repair_and_load_messages(self):
        self.prepare_speech()
        self.run_lua('''
t:SetFuel(800);local log=SpawnPrefab('log');log:AddComponent('fuel');log.components.fuel.fuelvalue=90
local flint=SpawnPrefab('flint');local gears=SpawnPrefab('gears')
fail_action('AOM_REFUEL',t,log,'FUEL_FULL')
fail_action('AOM_REPAIR',t,gears,'REPAIR_FULL')
fail_action('AOM_REPAIR',t,flint,'REPAIR_GEARS')
assert(log:IsValid() and flint:IsValid() and gears:IsValid())
local tool=equipment('aom_irrigator');assert(t:AttachAttachment(nil,tool))
assert(t.components.aom_attachment_store:AddWater(400)==400)
local ice=SpawnPrefab('ice');fail_action('AOM_LOAD',t,ice,'WATER_FULL');assert(ice:IsValid())
local word=Speech.GetActionFailString('wendy','AOM_REFUEL','FUEL_FULL')
assert(word==Feedback.Text('FUEL_FULL') and word~='wendy generic')
assert(STRINGS.CHARACTERS.WILSON.ACTIONFAIL.MOUNT.GENERIC=='vanilla mount')
''')

    def test_mount_failures_and_rpc_detach_report_space_without_dropping_equipment(self):
        self.prepare_speech()
        self.run_lua('''
ride();local current=equipment('aom_weeder');assert(t:AttachAttachment(nil,current))
fail_action('AOM_ATTACH',equipment('aom_harvester'),nil,'OCCUPIED')
Mount.FreePosition=function()return nil end
fail_action('AOM_ATTACH',current,nil,'NO_DROP_SPACE')
assert(t:GetAttachment()==current and current:IsValid())
RPCS.AOM_DETACH(player)
assert(#MESSAGES==1 and MESSAGES[1]==Feedback.Text('NO_DROP_SPACE'))
''')

    def test_all_failure_reason_codes_are_registered_for_native_characters_and_localized(self):
        self.prepare_speech()
        self.run_lua('''
require('aom_common').SetLanguage('en')
local action=ACTION_DEFS.AOM_REPAIR;local original=action.fn
Feedback.InstallActions({action});assert(action.fn==original)
assert(Speech.GetActionFailString('wilson','AOM_REPAIR','REPAIR_GEARS')=='Use gears to repair the tractor.')
for id,action in pairs(ACTION_DEFS)do
 if string.sub(id,1,4)=='AOM_' then
  local messages=STRINGS.CHARACTERS.GENERIC.ACTIONFAIL[id]
  assert(messages and messages.GENERIC)
 end
end
local stranger=CreateEntity();stranger.prefab='mod_character'
assert(Speech.GetActionFailString(stranger,'AOM_REPAIR','REPAIR_GEARS')=='Use gears to repair the tractor.')
player:AddTag('mime');assert(Speech.GetActionFailString(player,'AOM_REPAIR','REPAIR_GEARS')=='')
''')

    def test_work_failures_speak_once_parameters_change_and_explicit_retry_speaks_again(self):
        self.prepare_speech()
        self.run_lua('''
ride();local Drive=require('aom_drive')
for _,code in ipairs({'IVY_THREAT','CARGO_FULL','BROKEN_CHASSIS','UNCLEARABLE_WEED','WEEDING_INCOMPLETE','WORK_ERROR','MOISTURE_UNAVAILABLE','NUTRIENTS_UNAVAILABLE','NO_FUEL','PLAN_PENDING','MISSING_SEEDS','FOREIGN_CROP','COMPLETE'})do
 Status.Set(t,nil);MESSAGES={};Drive.SetWorking(t,true)
 Drive.StopForReason(t,code)
 assert(not t._working and #MESSAGES==1 and MESSAGES[1]==Status.Describe(t))
 Drive.StopForReason(t,code);assert(#MESSAGES==1)
end
MESSAGES={};t._fertilizer_missing_channels='1';Drive.StopForReason(t,'FERTILIZER_MISSING')
t._fertilizer_missing_channels='13';Drive.StopForReason(t,'FERTILIZER_MISSING')
assert(#MESSAGES==2 and MESSAGES[1]~=MESSAGES[2])
Drive.SetWorking(t,true);Drive.StopForReason(t,'FERTILIZER_MISSING');assert(#MESSAGES==3)
''')

    def test_giant_work_needs_no_manual_preview_and_planning_message_is_deduplicated(self):
        self.prepare_speech()
        self.run_lua("""
assert(t:AttachAttachment(nil,equipment('aom_seeder')));ride();t._seed_strategy='GIANT'
local seed=SpawnPrefab('tomato_seeds');seed.components.stackable:SetStackSize(40)
assert(t.components.container:GiveItem(seed,1))
local Drive=require('aom_drive')
assert(Drive.ToggleWorking(t,player));assert(t._working and #MESSAGES==0)
assert(RPCS.AOM_PLAN==nil)
Status.Report(t,'PLANNING');Status.Report(t,'PLANNING')
assert(#MESSAGES==1 and string.find(MESSAGES[1],'规划',1,true))
Status.Report(t,'NEXT_TILE');Status.Report(t,'NEXT_TILE');assert(#MESSAGES==2)
""")

    def test_refill_in_progress_and_cancellation_use_head_text_but_completion_is_quiet(self):
        self.prepare_speech()
        self.run_lua('''
local tank=equipment('aom_irrigator');assert(t:AttachAttachment(nil,tank));ride()
local pond=CreateEntity();pond.prefab='pond';pond:AddTag('pond');pond.Transform:SetPosition(4,0,0)
pond.components.watersource=dofile(REF..'/watersource.lua')(pond)
assert(require('aom_pond_refill').Start(t,player,pond,tank))
assert(not require('aom_drive').ToggleWorking(t,player))
assert(#MESSAGES==1 and string.find(MESSAGES[1],'5秒',1,true))
player.Transform:SetPosition(1,0,0);require('aom_pond_refill').Update(t)
assert(#MESSAGES==2 and string.find(MESSAGES[2],'中断',1,true))
require('aom_pond_refill').Update(t);assert(#MESSAGES==2)
''')

    def test_native_buffered_action_propagates_reason_to_player_failure_speech(self):
        self.prepare_speech()
        self.run_lua('''
dofile(REF..'/bufferedaction.lua');local gears=SpawnPrefab('gears')
local action=BufferedAction(player,t,ACTION_DEFS.AOM_REPAIR,gears)
action:AddFailAction(function()Speech.OnActionFailed(player,{action=action,reason=action.reason})end)
local ok,reason=action:Do()
assert(not ok and reason=='REPAIR_FULL' and #MESSAGES==1)
assert(MESSAGES[1]==Feedback.Text('REPAIR_FULL') and gears:IsValid())
''')

    def test_feedback_is_server_only_and_ignores_empty_removed_dead_or_mime_actors(self):
        self.prepare_speech()
        self.run_lua('''
TheWorld.ismastersim=false;assert(not Feedback.Say(player,'test') and #MESSAGES==0)
TheWorld.ismastersim=true;assert(not Feedback.Say(nil,'test') and not Feedback.Say(player,''))
player:AddTag('mime');assert(not Feedback.Say(player,'test'));player:RemoveTag('mime')
player:AddTag('playerghost');assert(not Feedback.Say(player,'test'));player:RemoveTag('playerghost')
player.components.health={IsDead=function()return true end};assert(not Feedback.Say(player,'test'))
player.components.health=nil;player:Remove();assert(not Feedback.Say(player,'test') and #MESSAGES==0)
''')

    def test_rpc_busy_missing_equipment_and_storage_failures_speak_to_actor(self):
        self.prepare_speech()
        self.run_lua('''
ride();player.sg:GoToState('mount');RPCS.AOM_TOGGLE_WORK(player)
assert(#MESSAGES==1 and MESSAGES[1]==Feedback.Text('BUSY'))
player.sg:GoToState('mounted_idle');MESSAGES={};RPCS.AOM_TOGGLE_WORK(player)
assert(#MESSAGES==1 and string.find(MESSAGES[1],'挂件',1,true))
MESSAGES={};t.components.container.CanOpen=function()return false end
RPCS.AOM_STORAGE(player);assert(#MESSAGES==1 and MESSAGES[1]==Feedback.Text('STORAGE_BLOCKED'))
''')

    def test_late_character_gets_native_failure_message_when_using_aom_action(self):
        self.prepare_speech()
        self.run_lua('''
STRINGS.CHARACTERS.MOD_CHARACTER={ACTIONFAIL={GENERIC={GENERIC='unhelpful generic'}}}
player.prefab='mod_character'
fail_action('AOM_REPAIR',t,SpawnPrefab('gears'),'REPAIR_FULL')
assert(STRINGS.CHARACTERS.MOD_CHARACTER.ACTIONFAIL.GENERIC.GENERIC=='unhelpful generic')
''')


class IvyOverheadTests(unittest.TestCase):
    setUp = ivy.IvyDefenseTests.setUp
    run_lua = ivy.IvyDefenseTests.run_lua

    def test_real_harvest_ivy_error_speaks_once_and_deleted_attachment_reports_missing(self):
        self.run_lua('''
attach('aom_harvester');ride();local messages={}
player.components.talker={Say=function(_,text)messages[#messages+1]=text end}
mature_ivy(1,0);crop(0,0);t:SetWorking(true)
local changed,reason=Drive.WorkTile(t,0,0)
assert(not changed and reason=='IVY_THREAT' and #messages==1)
assert(messages[1]==require('aom_work_status').Describe(t))
Drive.WorkTile(t,0,0);assert(#messages==1 and hp(t)==600)
t:GetAttachment():Remove()
assert(#messages==2 and string.find(messages[2],'挂件',1,true))
''')

    def test_vehicle_destruction_tells_the_surviving_driver_before_dismount(self):
        self.run_lua('''
ride();local message
player.components.talker={Say=function(_,text)message=text end}
player.components.combat:GetAttacked(attacker,600)
assert(message and string.find(message,'损毁',1,true))
assert(not player.components.rider:IsRiding() and hp(player)==150)
''')


if __name__ == '__main__':
    unittest.main()
