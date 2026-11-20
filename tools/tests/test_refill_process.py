"""五秒补水、车尾方向、软管与取消；音乐三态和水滴表盘。"""
import unittest
import test_pond_refill as pond
import test_dashboard as dashboard


class RefillProcessTests(unittest.TestCase):
    def setUp(self):
        pond.PondRefillTests.setUp(self)
        self.lua.execute('''
clock=0;GetTime=function()return clock end
fill_pond=begin_pond
Refill=require('aom_pond_refill')
function advance(time)clock=time;Refill.Update(t)end
''')
    run_lua=pond.PondRefillTests.run_lua

    def test_pond_refill_uses_eighty_per_second_with_one_second_minimum(self):
        self.run_lua('''
for _,initial in ipairs({0,200,399})do
 clock=0;tank.components.finiteuses:SetUses(initial)
 local fuel=t._fuel:value();local uses=t.components.finiteuses:GetUses()
 assert(fill_pond() and store:GetWater()==initial and t._refilling_net:value())
 assert(not fill_pond())
 local duration=math.max(1,(400-initial)/80)
 advance(duration/2);assert(store:GetWater()==initial+math.floor((400-initial)/2))
 advance(duration-.01);assert(store:GetWater()<400 and t._refilling_net:value())
 local hoses=t._aom_pond_refill.hoses;assert(#hoses==2)
 advance(duration);assert(store:GetWater()==400 and not t._aom_pond_refill and not t._refilling_net:value())
 for _,fx in ipairs(hoses)do assert(not fx:IsValid() and not fx.persists)end
 assert(t._fuel:value()==fuel and t.components.finiteuses:GetUses()==uses)
end
assert(water_uses==3 and not fill_pond())
''')

    def test_coast_filters_forty_per_second_and_costs_only_attachment_durability(self):
        self.run_lua('''
local Irrigator=require('aom_irrigator');local Durability=require('aom_durability')
TheWorld.Map.IsOceanAtPoint=function(_,x) return x>1 end
assert(not Irrigator.RefillFromSea(player,Vector3(1,0,0)))
assert(not Irrigator.RefillFromSea(player,Vector3(4,0,0)))
local fuel=t._fuel:value();local chassis=t.components.finiteuses:GetUses()
assert(ACTION_DEFS.AOM_SEA_REFILL.fn({doer=player,GetActionPoint=function()return Vector3(2,0,0)end}))
advance(.4);assert(store:GetWater()==16 and Durability.GetUses(tank)==200)
advance(2.5);assert(store:GetWater()==100 and Durability.GetUses(tank)==195)
advance(10);assert(store:GetWater()==400 and Durability.GetUses(tank)==180 and not t._aom_pond_refill)
assert(t._fuel:value()==fuel and t.components.finiteuses:GetUses()==chassis)
assert(water_uses==0)
''')

    def test_coast_filter_remainder_survives_reload_and_last_use_cannot_overdraw(self):
        self.run_lua('''
local Irrigator=require('aom_irrigator');local Durability=require('aom_durability')
TheWorld.Map.IsOceanAtPoint=function(_,x) return x>1 end
tank._aom_machine_uses=1
assert(Irrigator.RefillFromSea(player,Vector3(2,0,0)))
advance(.4);assert(store:GetWater()==16 and Durability.GetUses(tank)==1)
local saved=clone(t:GetSaveRecord());player.components.rider:ActualDismount();t:Remove()
t=SpawnSaveRecord(saved);tank=t:GetAttachment()
store=t.components.aom_attachment_store
assert(store:GetWater()==16 and Durability.GetUses(tank)==1)
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
assert(Irrigator.RefillFromSea(player,Vector3(2,0,0)))
advance(2)
assert(tank.components.finiteuses:GetUses()==20 and Durability.GetUses(tank)==0)
assert(not t._aom_pond_refill and not t._refilling_net:value())
''')

    def test_rear_faces_water_and_turn_or_move_cancels_with_partial_water(self):
        self.run_lua('''
assert(fill_pond());assert(player.Transform:GetRotation()==180)
advance(2);assert(store:GetWater()==160)
player.Transform:SetPosition(.2,0,0);advance(2.1)
assert(not t._aom_pond_refill and store:GetWater()==160)
clock=3;assert(fill_pond());player.Transform:SetRotation(0);advance(3.1)
assert(not t._aom_pond_refill and store:GetWater()==160)
''')

    def test_hose_extends_from_tank_into_water_before_remaining_deployed(self):
        self.run_lua('''
assert(fill_pond());local hose=t._aom_pond_refill.hoses[2]
local initial=hose.anim_scale[1];advance(.2);local partial=hose.anim_scale[1]
advance(.4);local deployed=hose.anim_scale[1]
assert(initial<partial and partial<deployed)
advance(3);assert(math.abs(hose.anim_scale[1]-deployed)<.000001)
advance(5);assert(not hose:IsValid())
''')

    def test_dismount_source_equipment_and_vehicle_removal_cleanup_immediately(self):
        for event in ['player.components.rider:ActualDismount()', 'pond:Remove()',
                      'tank:Remove()', 't:Remove()', 'pond.components.watersource.available=false;Refill.Update(t)']:
            with self.subTest(event=event):
                self.setUp();self.run_lua('''
assert(fill_pond());advance(1);local hoses=t._aom_pond_refill.hoses
'''+event+'''
assert(not t._aom_pond_refill and not t._refilling_net:value())
for _,fx in ipairs(hoses)do assert(not fx:IsValid())end
''')

    def test_save_cancels_without_losing_partial_water_or_restarting_on_reload(self):
        self.run_lua('''
assert(fill_pond());advance(2);local record=clone(t:GetSaveRecord())
assert(not t._aom_pond_refill and store:GetWater()==160)
local restored=SpawnSaveRecord(record)
assert(restored.components.aom_attachment_store:GetWater()==160 and not restored._aom_pond_refill)
assert(not restored._refilling_net:value() and not restored._working)
''')

    def test_work_is_stopped_and_cannot_be_started_during_refill(self):
        self.run_lua('''
store:AddWater(1);t:SetWorking(true);assert(fill_pond() and not t._working)
t:SetWorking(true);assert(not t._working)
advance(5);assert(not t._working);t:SetWorking(true);assert(t._working)
''')


class IrrigatorPresentationTests(unittest.TestCase):
    setUp=dashboard.DashboardTests.setUp
    run_lua=dashboard.DashboardTests.run_lua

    def test_water_has_own_drop_badge_and_no_strip_or_music_switch(self):
        self.run_lua('''
assert(#hud.order==6 and hud.order[5]=='tool' and hud.order[6]=='water')
assert(hud.strip==nil and hud.musicbutton==nil and hud.music_icon==nil)
assert(hud.badges.water.icon_texture=='water_drop.tex' and hud.badges.water:GetText()=='20')
assert(hud.badges.water.meter.percent==.05)
attach('aom_seeder');assert(#hud.order==5 and not hud.badges.water:IsVisible())
''')

    def test_three_modes_and_muted_tending_without_audio_assets(self):
        self.run_lua('''
local assets=Music.Configure('mute',MOD..'/',function()error('mute must not read audio assets')end,function()end)
t._music_mode_net:set('mute');t:SetWorking(true)
assert(#assets==0 and not Music.ready and Music.IsActive(t))
local crop=SpawnPrefab('farm_plant_carrot');crop:AddTag('tendable_farmplant')
local tended=0;crop.components.farmplanttendable={TendTo=function()tended=tended+1;return true end}
assert(Music.TendPlants(t)==1 and tended==1)
AllPlayers={player};local audio=Music.New(player);audio:Update();assert(not audio.playing)
t._music_mode_net:set('off');assert(not Music.IsActive(t) and Music.TendPlants(t)==0)
Music.Configure('on',MOD..'/',function()return true end,function()end);t._music_mode_net:set('on')
audio:Update();assert(audio.playing and Music.IsActive(t))
assert(RPCS.AOM_MUSIC==nil and Music.SetEnabled==nil)
''')

    def test_mod_configuration_has_three_modes_and_accepts_old_booleans(self):
        self.run_lua('''
local env=setmetatable({locale='zh'},{__index=_G})
local load=assert(loadfile(MOD..'/modinfo.lua'));setfenv(load,env);load()
local option;for _,v in ipairs(env.configuration_options)do if v.name=='IRRIGATOR_MUSIC' then option=v end end
assert(option.default=='on' and #option.options==3)
assert(option.options[1].data=='on' and option.options[2].data=='off' and option.options[3].data=='mute')
Music.Configure(false,MOD..'/',function()return true end,function()end);assert(Music.mode=='off')
Music.Configure(true,MOD..'/',function()return true end,function()end);assert(Music.mode=='on')
''')


if __name__=='__main__':unittest.main()
