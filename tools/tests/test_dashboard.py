"""原版 Badge / ImageButton / Rider / Container 装配的仪表及 RPC 行为。"""
import unittest
import test_lifecycle_flow as lifecycle


class DashboardTests(unittest.TestCase):
    def setUp(self):
        engine=lifecycle.LifecycleFlowTests();engine.setUp();self.lua=engine.lua
        self.lua.execute('''
kit:Remove()
Music=require('aom_irrigator_music')
Music.Configure(true,MOD..'/',function()return true end,function()end)
t=SpawnPrefab('aom_tractor_chassis');tool=SpawnPrefab('aom_irrigator')
assert(t:AttachAttachment(nil,tool));assert(t.components.aom_attachment_store:AddWater(20)==20)
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
CLIENT_PLAYER=player;ThePlayer=player
hud=HUD(player);hud:Refresh(t)
function click(button)
 assert(button:IsVisible());button:OnGainFocus()
 assert(button:OnControl(CONTROL_PRIMARY,true))
 hud:Refresh(t)
 assert(button:OnControl(CONTROL_PRIMARY,false))
 hud:Refresh(t)
end
function attach(name)
 assert(t:DetachAttachment(player))
 local item=SpawnPrefab(name);item.Transform:SetPosition(player.Transform:GetWorldPosition())
 assert(t:AttachAttachment(player,item));hud:Refresh(t);return item
end
''')

    def run_lua(self,s):self.lua.execute(s)

    def test_five_native_dials_numbers_liquid_and_hover_without_persistent_labels(self):
        self.run_lua('''
t._health_net:set(450);t.components.finiteuses:SetUses(850)
tool._aom_machine_uses=38;require('aom_durability').Sync(t)
for i,name in ipairs({'gears','charcoal','rocks','flint','twigs','tomato_seeds'})do
 assert(t.components.container:GiveItem(SpawnPrefab(name),i))
end
hud:Refresh(t)
assert(#hud.order==5 and hud.lines==nil and hud.dismountbutton==nil and hud.detachbutton==nil)
local expected={'450','850','400','38','6/9'}
for i,key in ipairs(hud.order)do
 local badge=hud.badges[key]
 assert(badge.meter.name=='Badge' and badge:GetText()==expected[i])
 assert(badge.meter.num.visible==false and badge:GetTooltip()~='')
 assert(badge.scale[1]==1.4 and badge.meter.circleframe:GetAnimState().SetBank_args[1]=='status_meter')
end
assert(hud.badges.health.meter.percent==.75 and hud.badges.fuel.meter.percent==.5)
assert(hud.badges.tool.meter.percent==38/60 and t._cargo_used_net:value()==6)
assert(hud.resource_num:GetString()=='20/40' and hud.resource_fill.render_size[1]==46)
assert(not hud.seedbutton.visible and hud.musicbutton.visible and not hud.musicbutton.text.visible)
assert(not hud.badges.cargo.meter.warningstarted)
''')

    def test_cargo_native_button_and_body_click_toggle_the_same_inventory_then_right_click_dismounts(self):
        self.run_lua('''
local picker=make_mouse_picker(player)
click(hud.badges.cargo);assert(t.components.container:IsOpenedBy(player))
assert(picker:GetLeftClickActions(nil,player)[1]:Do());assert(not t.components.container:IsOpenedBy(player))
click(hud.badges.cargo);assert(t.components.container:IsOpenedBy(player))
click(hud.badges.cargo);assert(not t.components.container:IsOpenedBy(player))
assert(picker:GetRightClickActions(nil,player)[1]:Do())
player.components.rider:ActualDismount();hud:Refresh(nil)
assert(not hud.visible and hud.tractor==nil and not player.components.rider:IsRiding())
''')

    def test_seed_button_click_cycles_three_modes_stops_work_and_preserves_supplies(self):
        self.run_lua('''
local seeder=attach('aom_seeder')
local seeds=SpawnPrefab('tomato_seeds');seeds.components.stackable:SetStackSize(20)
assert(t.components.container:GiveItem(seeds,1))
for _,mode in ipairs({'RANDOM','GIANT','SEQUENTIAL','RANDOM'})do
 t:SetWorking(true);hud:Refresh(t)
 local fuel=t._fuel:value();local durability=seeder.components.finiteuses:GetUses()
 click(hud.seedbutton)
 assert(t._seed_strategy==mode and t._seedmode_net:value()==mode and not t._working)
 assert(t._fuel:value()==fuel and seeder.components.finiteuses:GetUses()==durability)
 assert(seeds.components.stackable:StackSize()==20 and hud.seedbutton.visible and not hud.musicbutton.visible)
 assert(string.find(hud.seedbutton:GetTooltip(),'点击切换为',1,true))
end
local saved=clone(t:GetSaveRecord());t:Remove()
local loaded=SpawnSaveRecord(saved);assert(loaded._seed_strategy=='RANDOM' and loaded._seedmode_net:value()=='RANDOM')
''')

    def test_music_native_button_stops_audio_and_tending_but_keeps_irrigation_task_and_stock(self):
        self.run_lua('''
t:SetWorking(true);hud:Refresh(t)
AllPlayers={player};local controller=Music.New(player);controller:Update();assert(controller.playing)
local task=t._worktask;local fuel=t._fuel:value();local durability=t.components.finiteuses:GetUses()
click(hud.musicbutton);assert(not t._music_enabled_net:value() and not Music.IsActive(t))
controller:Update();assert(not controller.playing and Music.TendPlants(t)==0)
assert(t._working and t._worktask==task and t._fuel:value()==fuel)
assert(t.components.finiteuses:GetUses()==durability and t.components.aom_attachment_store:GetWater()==20)
assert(hud.musicbutton.image_normal=='radiobutton_off.tex')
click(hud.musicbutton);controller:Update()
assert(controller.playing and t._music_enabled_net:value() and t._working and t._worktask==task)
''')

    def test_disabled_music_saves_per_vehicle_through_attachment_swap_load_and_driver_change(self):
        self.run_lua('''
click(hud.musicbutton)
local other=SpawnPrefab('aom_tractor_chassis');assert(other._music_enabled_net:value())
attach('aom_weeder');attach('aom_irrigator');assert(not t._music_enabled_net:value())
player.components.rider:ActualDismount()
local second=make_player();assert(ACTIONS.MOUNT.fn({doer=second,target=t}))
assert(not t._music_enabled_net:value())
local saved=clone(t:GetSaveRecord());t:Remove()
local loaded=SpawnSaveRecord(saved)
assert(saved.data.music_enabled==false and not loaded._music_enabled_net:value())
local legacy=SpawnSaveRecord({prefab='aom_tractor_chassis',data={fuel=200}})
assert(legacy._music_enabled_net:value())
''')

    def test_rpc_rejects_invalid_types_walking_busy_ghost_and_wrong_attachment(self):
        self.run_lua('''
for _,v in ipairs({1,0,'false',{},'on'})do RPCS.AOM_MUSIC(player,v);assert(t._music_enabled_net:value())end
RPCS.AOM_MUSIC(player,nil);assert(t._music_enabled_net:value())
local other=make_player();RPCS.AOM_MUSIC(other,false);assert(t._music_enabled_net:value())
player:AddTag('playerghost');RPCS.AOM_MUSIC(player,false);assert(t._music_enabled_net:value())
player:RemoveTag('playerghost')
player.sg:GoToState('mount');RPCS.AOM_MUSIC(player,false);assert(t._music_enabled_net:value())
player.sg:GoToState('mounted_idle')
attach('aom_seeder');RPCS.AOM_MUSIC(player,false);assert(t._music_enabled_net:value())
attach('aom_irrigator');player.components.health:SetVal(0)
RPCS.AOM_MUSIC(player,false);assert(t._music_enabled_net:value())
''')

    def test_stale_hud_callbacks_after_dismount_or_vehicle_removal_send_no_requests(self):
        self.run_lua('''
local requests=0;SendModRPCToServer=function()requests=requests+1 end
player.components.rider:ActualDismount()
hud.badges.cargo.onclick();hud.musicbutton.onclick();hud.seedbutton.onclick();assert(requests==0)
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
t:Remove();hud.badges.cargo.onclick();hud.musicbutton.onclick();assert(requests==0)
''')

    def test_server_disabled_music_is_grey_and_unavailable_without_affecting_watering(self):
        self.run_lua('''
t._music_available_net:set(false);hud:Refresh(t)
assert(string.find(hud.musicbutton:GetTooltip(),'世界设置',1,true))
click(hud.musicbutton);assert(t._music_enabled_net:value() and not Music.IsActive(t))
RPCS.AOM_MUSIC(player,false);assert(t._music_enabled_net:value())
t:SetWorking(true);assert(t._working and t.components.aom_attachment_store:GetWater()==20)
''')

    def test_full_slot_count_is_not_full_warning_and_empty_cargo_does_not_warn(self):
        self.run_lua('''
hud:Refresh(t);assert(not hud.badges.cargo.meter.warningstarted)
for i=1,9 do assert(t.components.container:GiveItem(SpawnPrefab('gears'),i))end
hud:Refresh(t);assert(hud.badges.cargo:GetText()=='9/9' and not hud.badges.cargo.meter.warningstarted)
assert(string.find(hud.badges.cargo:GetTooltip(),'仍可叠堆',1,true))
require('aom_drive').StopForReason(t,'CARGO_FULL');hud:Refresh(t)
assert(hud.badges.cargo.meter.warningstarted and hud.worklamp.tint[1]==1)
t.components.container:RemoveItemBySlot(1):Remove();assert(t._cargo_used_net:value()==8)
''')

    def test_refresh_does_not_cancel_pressed_buttons_or_reset_hover(self):
        self.run_lua('''
local button=hud.musicbutton;button:OnGainFocus()
assert(button:OnControl(CONTROL_PRIMARY,true) and button.down)
local hide_count=button.hide_count
for i=1,20 do hud:Refresh(t);assert(button.down and button.focus and button.hide_count==hide_count)end
assert(button:OnControl(CONTROL_PRIMARY,false));assert(not t._music_enabled_net:value())
''')

    def test_client_only_netvars_cover_six_tools_and_match_native_status_scale(self):
        self.run_lua('''
local old=t.components;t.components={}
player.HUD={controls={status={GetLooseScale=function()return Vector3(1.8,1.8,1.8)end}}}
for _,kind in ipairs({'plow','seeder','irrigator','fertilizer','weeder','harvester',''})do
 t._atttype_net:set(kind);hud:Refresh(t)
 for _,key in ipairs(hud.order)do assert(hud.badges[key].scale[1]==1.8)end
 assert(hud.seedbutton.visible==(kind=='seeder') and hud.musicbutton.visible==(kind=='irrigator'))
end
t.components=old
''')

    def test_localized_hover_and_placeholder_for_absent_equipment(self):
        self.run_lua('''
require('aom_common').SetLanguage('en')
t:DetachAttachment(nil);hud:Refresh(t)
assert(hud.badges.tool:GetText()=='—' and hud.badges.tool:GetTooltip()=='No attachment')
assert(string.find(hud.badges.cargo:GetTooltip(),'Cargo:',1,true))
assert(string.find(hud.worklamp:GetTooltip(),'F to start',1,true))
assert(not hud.resource.visible and not hud.seedbutton.visible and not hud.musicbutton.visible)
''')


if __name__=='__main__':unittest.main()
