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

    def test_no_attachment_has_blank_icon_and_attaching_again_restores_it(self):
        self.run_lua('''
assert(t:DetachAttachment(player));hud:Refresh(t)
assert(not hud.badges.tool.icon:IsVisible())
assert(hud.badges.tool:GetText()=='—' and hud.badges.tool:GetTooltip()=='无挂件')
for i=1,3 do
 local item=SpawnPrefab('aom_weeder');assert(t:AttachAttachment(nil,item));hud:Refresh(t)
 assert(hud.badges.tool.icon:IsVisible() and hud.badges.tool.icon_texture=='aom_weeder.tex')
 assert(t:DetachAttachment(player));hud:Refresh(t)
 assert(not hud.badges.tool.icon:IsVisible())
end
''')

    def test_five_native_dials_numbers_liquid_and_hover_without_persistent_labels(self):
        self.run_lua('''
t._health_net:set(450);t.components.finiteuses:SetUses(850)
tool._aom_machine_uses=38;require('aom_durability').Sync(t)
for i,name in ipairs({'gears','charcoal','rocks','flint','twigs','tomato_seeds'})do
 assert(t.components.container:GiveItem(SpawnPrefab(name),i))
end
hud:Refresh(t)
assert(#hud.order==6 and hud.lines==nil and hud.dismountbutton==nil and hud.detachbutton==nil)
local expected={'450','850','400','6','38','20'}
for i,key in ipairs(hud.order)do
 local badge=hud.badges[key]
 assert(badge.meter.name=='Badge' and badge:GetText()==expected[i])
 assert(badge.meter.num.visible==false and badge:GetTooltip()~='')
 assert(badge.scale[1]==1.4 and badge.meter.circleframe:GetAnimState().SetBank_args[1]=='status_meter')
end
assert(hud.badges.health.meter.percent==.75 and hud.badges.fuel.meter.percent==.5)
assert(hud.badges.tool.meter.percent==38/60 and t._cargo_used_net:value()==6)
assert(hud.badges.water:GetText()=='20' and hud.badges.water.meter.percent==.05)
assert(hud.seedbutton==nil and hud.musicbutton==nil and hud.strip==nil)
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

    def test_tool_dial_click_cycles_two_modes_stops_work_and_preserves_supplies(self):
        self.run_lua('''
local seeder=attach('aom_seeder')
local seeds=SpawnPrefab('tomato_seeds');seeds.components.stackable:SetStackSize(20)
assert(t.components.container:GiveItem(seeds,1))
for _,mode in ipairs({'GIANT','SEQUENTIAL','GIANT','SEQUENTIAL'})do
 t:SetWorking(true);hud:Refresh(t)
 local fuel=t._fuel:value();local durability=seeder.components.finiteuses:GetUses()
 click(hud.badges.tool)
 assert(t._seed_strategy==mode and t._seedmode_net:value()==mode and not t._working)
 assert(t._fuel:value()==fuel and seeder.components.finiteuses:GetUses()==durability)
 assert(seeds.components.stackable:StackSize()==20 and hud.seedbutton==nil and hud.seedbackground==nil)
 local names={GIANT='巨大化',SEQUENTIAL='顺序'}
 assert(hud.badges.tool:GetTooltip()=='播种机'..string.char(10)..'耐久 400/400'..string.char(10)..'播种策略：'..names[mode])
 assert(hud.seedcontrols==nil and hud.planbutton==nil and hud.rotatebutton==nil)
end
local saved=clone(t:GetSaveRecord());t:Remove()
local loaded=SpawnSaveRecord(saved);assert(loaded._seed_strategy=='SEQUENTIAL' and loaded._seedmode_net:value()=='SEQUENTIAL')
local legacy=clone(saved);legacy.data.seed_strategy='RANDOM'
local migrated=SpawnSaveRecord(legacy);assert(migrated._seed_strategy=='SEQUENTIAL' and migrated._seedmode_net:value()=='SEQUENTIAL')
''')

    def test_music_configuration_modes_leave_work_and_resources_unchanged(self):
        self.run_lua('''
t:SetWorking(true);AllPlayers={player};local audio=Music.New(player)
local task=t._worktask;local water=t.components.aom_attachment_store:GetWater()
for _,mode in ipairs({'on','mute','off','on'})do
 t._music_mode_net:set(mode);audio:Update()
 assert(audio.playing==(mode=='on') and Music.IsActive(t)==(mode~='off'))
 assert(t._working and t._worktask==task and t.components.aom_attachment_store:GetWater()==water)
end
''')

    def test_seed_dial_hover_is_one_localized_line_and_refresh_does_not_repeat_click(self):
        self.run_lua('''
attach('aom_seeder');require('aom_common').SetLanguage('en');hud:Refresh(t)
assert(hud.badges.tool:GetTooltip()=='Seeder'..string.char(10)..'Durability 400/400'..string.char(10)..'Seed mode: Sequential')
local button=hud.badges.tool;button:OnGainFocus()
assert(button:OnControl(CONTROL_PRIMARY,true))
for _=1,20 do hud:Refresh(t);assert(t._seed_strategy=='SEQUENTIAL')end
assert(button:OnControl(CONTROL_PRIMARY,false));hud:Refresh(t)
assert(t._seed_strategy=='GIANT' and button:GetTooltip()=='Seeder'..string.char(10)..'Durability 400/400'..string.char(10)..'Seed mode: Giant')
for _=1,20 do hud:Refresh(t)end
assert(t._seed_strategy=='GIANT' and hud.seedcontrols==nil)
''')

    def test_world_music_mode_overrides_old_saved_per_vehicle_switch(self):
        self.run_lua('''
Music.mode='mute';local other=SpawnPrefab('aom_tractor_chassis')
local saved=clone(other:GetSaveRecord());saved.data.music_enabled=false
local loaded=SpawnSaveRecord(saved)
assert(other._music_mode_net:value()=='mute' and loaded._music_mode_net:value()=='mute')
assert(hud.musicbutton==nil and RPCS.AOM_MUSIC==nil)
''')


    def test_stale_hud_callbacks_after_dismount_or_vehicle_removal_send_no_requests(self):
        self.run_lua('''
local requests=0;SendModRPCToServer=function()requests=requests+1 end
player.components.rider:ActualDismount()
t._atttype_net:set('seeder')
hud.badges.cargo.onclick();hud.badges.tool.onclick();assert(requests==0)
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
t:Remove();hud.badges.cargo.onclick();assert(requests==0)
''')


    def test_full_slot_count_is_not_full_warning_and_empty_cargo_does_not_warn(self):
        self.run_lua('''
hud:Refresh(t);assert(not hud.badges.cargo.meter.warningstarted)
for i=1,15 do assert(t.components.container:GiveItem(SpawnPrefab('gears'),i))end
hud:Refresh(t);assert(hud.badges.cargo:GetText()=='15' and not hud.badges.cargo.meter.warningstarted)
assert(hud.badges.cargo:GetTooltip()=='货仓：15/15格'..string.char(10)..'物品总数 15（含堆叠）')
require('aom_drive').StopForReason(t,'CARGO_FULL');hud:Refresh(t)
assert(hud.badges.cargo.meter.warningstarted and not string.find(hud.badges.tool:GetTooltip(),'仓库已满',1,true))
t.components.container:RemoveItemBySlot(1):Remove();assert(t._cargo_used_net:value()==14)
''')

    def test_refresh_does_not_cancel_pressed_buttons_or_reset_hover(self):
        self.run_lua('''
local button=hud.badges.cargo;button:OnGainFocus()
assert(button:OnControl(CONTROL_PRIMARY,true) and button.down)
local hide_count=button.hide_count
for i=1,20 do hud:Refresh(t);assert(button.down and button.focus and button.hide_count==hide_count)end
assert(button:OnControl(CONTROL_PRIMARY,false));assert(t.components.container:IsOpenedBy(player))
''')

    def test_client_only_netvars_cover_six_tools_and_match_native_status_scale(self):
        self.run_lua('''
local old=t.components;t.components={}
player.HUD={controls={status={GetLooseScale=function()return 1.8,1.8,1.8 end}}}
for _,kind in ipairs({'plow','seeder','irrigator','fertilizer','weeder','harvester',''})do
 t._atttype_net:set(kind);hud:Refresh(t)
 for _,key in ipairs(hud.order)do assert(hud.badges[key].scale[1]==1.8)end
 assert(hud.seedbutton==nil and hud.badges.water:IsVisible()==(kind=='irrigator'))
 if kind=='seeder' then assert(string.find(hud.badges.tool:GetTooltip(),'播种策略：顺序',1,true))end
end
t.components=old
''')

    def test_localized_hover_and_placeholder_for_absent_equipment(self):
        self.run_lua('''
require('aom_common').SetLanguage('en')
t:DetachAttachment(nil);hud:Refresh(t)
assert(hud.badges.tool:GetText()=='—' and string.find(hud.badges.tool:GetTooltip(),'No attachment',1,true)==1)
assert(string.find(hud.badges.cargo:GetTooltip(),'Cargo:',1,true))
assert(hud.badges.tool:GetTooltip()=='No attachment')
assert(hud.resource==nil and hud.seedbutton==nil and hud.musicbutton==nil)
''')

    def test_native_numeric_scale_is_safe_during_hud_construction_and_refresh(self):
        self.run_lua('''
local status=require('widgets/widget')('StatusDisplays');status:SetScale(1.8,1.6,1.4)
local x,y,z=status:GetLooseScale();assert(x==1.8 and y==1.6 and z==1.4)
player.HUD={controls={status=status}}
local fresh=HUD(player) -- 实机是在进入世界、尚未挂载仪表前构造时崩溃。
assert(not fresh.visible)
for i,key in ipairs(fresh.order)do
 assert(fresh.badges[key].scale[1]==1.8)
 assert(fresh.badges[key].position[1]==(i-3)*78*1.8)
end
status:SetScale(1.2);fresh:Refresh(t)
for _,key in ipairs(fresh.order)do assert(fresh.badges[key].scale[1]==1.2)end
''')

    def test_vector_status_override_still_matches_dial_scale(self):
        self.run_lua('''
player.HUD={controls={status={GetLooseScale=function()return Vector3(1.7,1.7,1.7)end}}}
local fresh=HUD(player);fresh:Refresh(t)
for _,key in ipairs(fresh.order)do assert(fresh.badges[key].scale[1]==1.7)end
''')

    def test_missing_or_invalid_status_scale_uses_safe_default(self):
        self.run_lua('''
for _,value in ipairs({false,0,-1,math.huge,0/0,'1.8',{},Vector3(0,1,1)})do
 player.HUD={controls={status={GetLooseScale=function()return value end}}}
 local fresh=HUD(player);fresh:Refresh(t)
 for _,key in ipairs(fresh.order)do assert(fresh.badges[key].scale[1]==1.4)end
end
for _,ownerhud in ipairs({{}, {controls={}}, {controls={status={}}}})do
 player.HUD=ownerhud;local fresh=HUD(player);fresh:Refresh(t)
 for _,key in ipairs(fresh.order)do assert(fresh.badges[key].scale[1]==1.4)end
end
''')


if __name__=='__main__':unittest.main()
