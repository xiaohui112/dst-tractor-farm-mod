"""音乐安抚执行原版 Tendable、Stress 及植物回调；声音输出和实体底层为桩。"""
import unittest
import test_lifecycle_flow as lifecycle


class MusicTendingTests(unittest.TestCase):
    def setUp(self):
        engine=lifecycle.LifecycleFlowTests();engine.setUp();self.lua=engine.lua
        self.lua.execute('''
package.preload['util/sourcemodifierlist']=function()return dofile(REF..'/sourcemodifierlist.lua')end
local Stress=dofile(REF..'/farmplantstress.lua')
local Tendable=dofile(REF..'/farmplanttendable.lua')
local callbacks=dofile(REF..'/farm_plant_tending.lua')
TUNING.PHONOGRAPH_TEND_RANGE=8
Music=require('aom_irrigator_music')
Music.Configure(true,MOD..'/',function()return true end,function(kind,path)return {kind,path}end)
t=deploy_kit(kit,0,0,player);assert(t:AttachAttachment(nil,SpawnPrefab('aom_irrigator')))
store=t.components.aom_attachment_store;assert(store:AddWater(40)==40)
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
function plant(x)
 local e=SpawnPrefab('farm_plant_carrot');e.Transform:SetPosition(x,0,0)
 e.components.farmplantstress=Stress(e)
 e.components.farmplantstress:AddStressCategory('happiness',nil,callbacks.on_happiness_changed)
 e.components.farmplantstress:AddStressCategory('nutrients')
 e.components.farmplantstress:AddStressCategory('moisture')
 e.components.farmplanttendable=Tendable(e)
 e.components.farmplanttendable.ontendtofn=callbacks.ontendto
 return e
end
function mode(value)if t._music_mode_net:value()~=value then t._music_mode_net:set(value);t:PushEvent('aom_work_changed')end;return true end
function start_music()press_f(player);release_f(player)end
''')

    def run_lua(self,source):self.lua.execute(source)

    def test_start_tends_native_plant_and_triggers_happy_effect_without_other_farming_changes(self):
        self.run_lua('''
local near=plant(7.9);local far=plant(8.1);local mature=plant(1)
mature.components.farmplanttendable:SetTendable(false)
local fuel=t._fuel:value();local uses=t.components.finiteuses:GetUses()
start_music()
assert(not near.components.farmplantstress.stressors.happiness)
assert(not near.components.farmplanttendable.tendable and not near:HasTag('tendable_farmplant'))
assert(near.components.farmplantstress.stressors.nutrients and near.components.farmplantstress.stressors.moisture)
assert(far.components.farmplantstress.stressors.happiness and mature.components.farmplantstress.stressors.happiness)
near.last_periodic.fn(near)
local happy=0;for _,e in ipairs(ENTITIES)do if e.prefab=='farm_plant_happy' then happy=happy+1 end end
assert(happy==1 and Music.TendPlants(t)==0)
assert(store:GetWater()==40 and t._fuel:value()==fuel and t.components.finiteuses:GetUses()==uses)
''')

    def test_periodic_tending_repeats_only_after_native_stage_becomes_tendable_again(self):
        self.run_lua('''
local crop=plant(0);start_music();assert(not crop.components.farmplanttendable.tendable)
assert(Music.TendPlants(t)==0)
crop.components.farmplantstress:SetStressed('happiness',true)
crop.components.farmplanttendable:SetTendable(true)
assert(t._aom_music_tend_task and t._aom_music_tend_task.fn==Music.TendPlants)
t._aom_music_tend_task.fn(t)
assert(not crop.components.farmplantstress.stressors.happiness and not crop:HasTag('tendable_farmplant'))
''')

    def test_disabled_stopped_empty_unfueled_swapped_ghost_and_client_states_do_not_tend(self):
        self.run_lua('''
local crop=plant(0)
mode('off');start_music();assert(crop.components.farmplanttendable.tendable)
mode('on');crop.components.farmplantstress:SetStressed('happiness',true);crop.components.farmplanttendable:SetTendable(true)
t._water_net:set(0);assert(Music.TendPlants(t)==0);t._water_net:set(40)
t._fuel:set(0);assert(Music.TendPlants(t)==0);t._fuel:set(400)
t._atttype_net:set('seeder');assert(Music.TendPlants(t)==0);t._atttype_net:set('irrigator')
t._workstatus:set(false);assert(Music.TendPlants(t)==0);t._workstatus:set(true)
player:AddTag('playerghost');assert(Music.TendPlants(t)==0);player:RemoveTag('playerghost')
TheWorld.ismastersim=false;assert(Music.TendPlants(t)==0);TheWorld.ismastersim=true
mode('off')
assert(Music.TendPlants(t)==0 and crop.components.farmplantstress.stressors.happiness)
''')

    def test_dedicated_server_tends_without_a_client_sound_emitter(self):
        self.run_lua('''
TheNet.IsDedicated=function()return true end;player.SoundEmitter=nil
local crop=plant(0);start_music()
assert(not crop.components.farmplantstress.stressors.happiness and t._working)
''')

    def test_vehicle_switch_off_keeps_water_working_and_on_immediately_tends_new_stage(self):
        self.run_lua('''
assert(mode('off'));local crop=plant(0);start_music()
local task=t._worktask
assert(t._working and crop.components.farmplanttendable.tendable)
assert(Music.TendPlants(t)==0 and store:GetWater()==40)
assert(mode('on'))
assert(not crop.components.farmplanttendable.tendable and not crop.components.farmplantstress.stressors.happiness)
assert(t._working and t._worktask==task and store:GetWater()==40)
crop.components.farmplanttendable:SetTendable(true)
assert(mode('on') and crop.components.farmplanttendable.tendable)
assert(Music.TendPlants(t)==1)
''')

    def test_dedicated_server_honors_saved_off_switch_without_sound_hardware(self):
        self.run_lua('''
TheNet.IsDedicated=function()return true end;player.SoundEmitter=nil
assert(mode('off'))
local crop=plant(0);start_music()
t._aom_music_tend_task.fn(t)
assert(crop.components.farmplantstress.stressors.happiness and t._working)
assert(mode('on') and not crop.components.farmplantstress.stressors.happiness)
''')

    def test_audio_playback_failure_does_not_block_server_tending(self):
        self.run_lua('''
mode('off');start_music();mode('on')
local crop=plant(0);AllPlayers={player}
player.SoundEmitter={PlaySound=function()error('audio unavailable')end,KillSound=function()end}
local controller=Music.New(player);controller:Update()
assert(controller.failed and Music.TendPlants(t)==1)
assert(not crop.components.farmplantstress.stressors.happiness and t._working and store:GetWater()==40)
''')

    def test_bad_plant_callback_does_not_interrupt_work_or_other_plants(self):
        self.run_lua('''
local bad=plant(0);local good=plant(1)
bad.components.farmplanttendable.ontendtofn=function()error('modded plant failure')end
start_music()
assert(t._working and bad.components.farmplanttendable.tendable)
assert(not good.components.farmplantstress.stressors.happiness)
''')

    def test_range_uses_native_tuning_and_current_rider_position_not_hidden_chassis(self):
        self.run_lua('''
TUNING.PHONOGRAPH_TEND_RANGE=4
player.Transform:SetPosition(12,0,0)
local near=plant(15.9);local far=plant(16.1);local old=plant(0)
start_music()
assert(not near.components.farmplantstress.stressors.happiness)
assert(far.components.farmplantstress.stressors.happiness and old.components.farmplantstress.stressors.happiness)
''')


if __name__=='__main__':unittest.main()
