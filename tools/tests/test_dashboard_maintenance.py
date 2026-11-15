"""骑乘图标维修：原版按钮/堆叠/健康/耐久、服务端活动物品与权限边界。"""
import unittest
import test_dashboard as dashboard


class DashboardMaintenanceTests(unittest.TestCase):
    def setUp(self):
        dashboard.DashboardTests.setUp(self)
        self.lua.execute('''
Maintain=require('aom_dashboard_actions');Durability=require('aom_durability')
local Getter=dofile(REF..'/active_item.lua')
player.components.inventory={GetActiveItem=Getter}
player.replica.inventory={GetActiveItem=function()return client_item end}
MESSAGES={};player.components.talker={Say=function(_,text)MESSAGES[#MESSAGES+1]=text end}
function hold(name,n)
 local item=SpawnPrefab(name)
 if n and item.components.stackable then item.components.stackable:SetStackSize(n)end
 player.components.inventory.activeitem=item;client_item=item
 item:ListenForEvent('onremove',function()if player.components.inventory.activeitem==item then player.components.inventory.activeitem=nil end end)
 return item
end
function left(button)
 button:OnGainFocus();assert(button:OnControl(CONTROL_PRIMARY,true))
 assert(button:OnControl(CONTROL_PRIMARY,false));hud:Refresh(t)
end
function right(button)
 button:OnGainFocus();assert(button:OnControl(CONTROL_SECONDARY,true))
 assert(button:OnControl(CONTROL_SECONDARY,false));hud:Refresh(t)
end
function maintain(part,target)RPCS.AOM_MAINTAIN(player,target or t,part)end
''')

    run_lua = dashboard.DashboardTests.run_lua

    def test_gears_repair_health_and_chassis_independently_without_dismounting(self):
        self.run_lua('''
t.components.health:SetVal(250);t.components.finiteuses:SetUses(300)
local gears=hold('gears',4)
left(hud.badges.health)
assert(t.components.health.currenthealth==350 and t.components.finiteuses:GetUses()==300)
assert(t._health_net:value()==350 and gears.components.stackable:StackSize()==3)
left(hud.badges.chassis)
assert(t.components.health.currenthealth==350 and t.components.finiteuses:GetUses()==400)
assert(t._uses_net:value()==400 and gears.components.stackable:StackSize()==2)
assert(player.components.rider:GetMount()==t and #MESSAGES==2)
''')

    def test_caps_apply_only_to_clicked_stat_and_full_stat_does_not_consume_gears(self):
        self.run_lua('''
t.components.health:SetVal(590);t.components.finiteuses:SetUses(995)
local gears=hold('gears',4)
left(hud.badges.health);assert(t.components.health.currenthealth==600 and t.components.finiteuses:GetUses()==995)
left(hud.badges.health);assert(gears.components.stackable:StackSize()==3)
left(hud.badges.chassis);assert(t.components.finiteuses:GetUses()==1000 and gears.components.stackable:StackSize()==2)
left(hud.badges.chassis);assert(gears.components.stackable:StackSize()==2)
assert(MESSAGES[1]=='生命 +10' and MESSAGES[3]=='底盘耐久 +5')
''')

    def test_all_six_attached_tools_repair_with_one_flint_and_water_is_unchanged(self):
        self.run_lua('''
for _,name in ipairs({'aom_landclearer','aom_seeder','aom_irrigator','aom_fertilizer','aom_weeder','aom_harvester'})do
 local item=attach(name);local def=require('aom_equipment_defs')[item.attachment_type]
 if def.separate_uses then item._aom_machine_uses=def.uses-5 else item.components.finiteuses:SetUses(def.uses-5)end
 local water=t.components.aom_attachment_store:GetWater()
 local flint=hold('flint',2);left(hud.badges.tool)
 assert(t:GetAttachment()==item and Durability.GetUses(item)==def.uses)
 assert(flint.components.stackable:StackSize()==1 and player.components.rider:IsRiding())
 assert(t.components.aom_attachment_store:GetWater()==water and hud.seedcontrols==nil)
 left(hud.badges.tool);assert(flint:IsValid() and flint.components.stackable:StackSize()==1)
end
''')

    def test_fuel_click_uses_native_value_and_never_spends_at_full_tank(self):
        self.run_lua('''
t:SetFuel(790);local fuel=hold('charcoal',3);fuel:AddComponent('fuel');fuel.components.fuel.fuelvalue=90
left(hud.badges.fuel)
assert(t._fuel:value()==800 and fuel.components.stackable:StackSize()==2)
left(hud.badges.fuel);assert(fuel.components.stackable:StackSize()==2)
assert(MESSAGES[1]=='燃料 +10' and player.components.rider:IsRiding())
''')

    def test_right_click_detaches_without_dismounting_or_using_active_item(self):
        self.run_lua('''
local item=t:GetAttachment();local flint=hold('flint',3)
right(hud.badges.tool)
assert(t:GetAttachment()==nil and item:IsValid() and item.persists)
assert(player.components.rider:IsRiding() and flint.components.stackable:StackSize()==3)
assert(hud.seedcontrols==nil)
''')

    def test_blocked_detach_keeps_tool_and_reports_failure_overhead(self):
        self.run_lua('''
local item=t:GetAttachment();require('aom_attachment_mount').FreePosition=function()return nil end
right(hud.badges.tool)
assert(t:GetAttachment()==item and #MESSAGES==1 and string.find(MESSAGES[1],'卸载空间',1,true))
''')

    def test_right_mouse_release_or_focus_loss_does_not_repeat_or_fire_left_click(self):
        self.run_lua('''
local calls=0;local b=hud.badges.tool;b:SetOnRightClick(function()calls=calls+1 end)
b:OnGainFocus();assert(b:OnControl(CONTROL_SECONDARY,true));assert(calls==0)
assert(b:OnControl(CONTROL_SECONDARY,false));assert(b:OnControl(CONTROL_SECONDARY,false));assert(calls==1)
b:OnControl(CONTROL_SECONDARY,true);b:OnLoseFocus();b:OnGainFocus();b:OnControl(CONTROL_SECONDARY,false)
assert(calls==1)
''')

    def test_server_cursor_item_is_authoritative_and_wrong_or_empty_items_are_not_consumed(self):
        self.run_lua('''
local gears=hold('gears',3);client_item=SpawnPrefab('flint');local before=Durability.GetUses(tool)
left(hud.badges.tool)
assert(Durability.GetUses(tool)==before and gears.components.stackable:StackSize()==3)
left(hud.badges.fuel);assert(gears.components.stackable:StackSize()==3)
player.components.inventory.activeitem=nil;left(hud.badges.health)
assert(string.find(MESSAGES[#MESSAGES],'拿起',1,true))
assert(t.components.health.currenthealth==600)
''')

    def test_rpc_rejects_other_vehicle_unmounted_busy_ghost_client_and_unknown_parts(self):
        self.run_lua('''
local gears=hold('gears',5);t.components.health:SetVal(250)
local other=SpawnPrefab('aom_tractor_chassis')
local ok,reason=Maintain.Perform(player,other,'health');assert(not ok and reason=='NOT_DRIVING')
ok,reason=Maintain.Perform(player,t,'invalid');assert(not ok and reason=='GENERIC')
player.sg:GoToState('mount');assert(not Maintain.Perform(player,t,'health'));player.sg:GoToState('mounted_idle')
player:AddTag('playerghost');assert(not Maintain.Perform(player,t,'health'));player:RemoveTag('playerghost')
TheWorld.ismastersim=false;assert(not Maintain.Perform(player,t,'health'));TheWorld.ismastersim=true
player.components.rider:ActualDismount();assert(not Maintain.Perform(player,t,'health'))
assert(gears.components.stackable:StackSize()==5 and t.components.health.currenthealth==250)
''')

    def test_seeder_click_cycles_strategy_but_held_flint_repairs_without_changing_it(self):
        self.run_lua('''
attach('aom_seeder');client_item=nil;left(hud.badges.tool)
assert(t._seed_strategy=='GIANT' and hud.seedcontrols==nil)
hold('flint',2);t:GetAttachment().components.finiteuses:SetUses(350)
left(hud.badges.tool)
assert(t:GetAttachment().components.finiteuses:GetUses()==360 and t._seed_strategy=='GIANT')
assert(hud.badges.tool:GetTooltip()=='播种机'..string.char(10)..'耐久 360/400'..string.char(10)..'播种策略：巨大化' and hud.seedcontrols==nil)
''')

    def test_hover_text_has_only_requested_lines_even_during_errors_or_held_items(self):
        self.run_lua('''
attach('aom_fertilizer');t.components.health:SetVal(250);t._health_net:set(250);t.components.finiteuses:SetUses(300)
require('aom_work_status').Set(t,'CARGO_FULL');hold('gears',2);hud:Refresh(t)
assert(hud.badges.health:GetTooltip()=='生命 250/600')
assert(hud.badges.chassis:GetTooltip()=='底盘 300/1000')
assert(hud.badges.fuel:GetTooltip()=='燃料 400/800')
assert(hud.badges.tool:GetTooltip()=='施肥机'..string.char(10)..'耐久 60/60')
assert(hud.badges.cargo:GetTooltip()=='货仓：0/15格'..string.char(10)..'物品总数 0（含堆叠）')
''')

    def test_single_gear_is_removed_once_and_stale_hud_buttons_send_nothing_after_dismount(self):
        self.run_lua('''
t.components.health:SetVal(250);local gear=hold('gears',1);left(hud.badges.health)
assert(not gear:IsValid() and t.components.health.currenthealth==350)
local requests=0;SendModRPCToServer=function()requests=requests+1 end
player.components.rider:ActualDismount()
left(hud.badges.health);right(hud.badges.tool)
assert(requests==0)
''')

    def test_all_six_ground_attachments_can_be_repaired_while_driving(self):
        self.run_lua('''
assert(ACTION_DEFS.AOM_REPAIR.mount_valid)
for _,name in ipairs({'aom_landclearer','aom_seeder','aom_irrigator','aom_fertilizer','aom_weeder','aom_harvester'})do
 local item=SpawnPrefab(name);item.Transform:SetPosition(2,0,0)
 local def=require('aom_equipment_defs')[item.attachment_type]
 if def.separate_uses then item._aom_machine_uses=def.uses-5 else item.components.finiteuses:SetUses(def.uses-5)end
 local water=item.prefab=='aom_irrigator' and item.components.finiteuses:GetUses()
 local flint=hold('flint',2);local actions=prompt(flint,player,item)
 assert(actions[1]==ACTION_DEFS.AOM_REPAIR)
 assert(actions[1].fn({doer=player,target=item,invobject=flint}))
 assert(Durability.GetUses(item)==def.uses and flint.components.stackable:StackSize()==1)
 assert(player.components.rider:GetMount()==t and require('aom_attachment_mount').Owner(item)==nil)
 if water then assert(item.components.finiteuses:GetUses()==water)end
 assert(not actions[1].fn({doer=player,target=item,invobject=flint}) and flint:IsValid())
end
''')

    def test_ground_repair_keeps_distance_ownership_and_mount_checks(self):
        self.run_lua('''
local item=SpawnPrefab('aom_harvester');item.components.finiteuses:SetUses(5)
local flint=hold('flint',3);item.Transform:SetPosition(10,0,0)
local ok,reason=ACTION_DEFS.AOM_REPAIR.fn({doer=player,target=item,invobject=flint})
assert(not ok and reason=='TOO_FAR' and flint.components.stackable:StackSize()==3)
item.Transform:SetPosition(2,0,0)
local mount=player.components.rider.GetMount
player.components.rider.GetMount=function()return {prefab='beefalo',IsValid=function()return true end}end
ok,reason=ACTION_DEFS.AOM_REPAIR.fn({doer=player,target=item,invobject=flint})
assert(not ok and reason=='NOT_DRIVING')
player.components.rider.GetMount=mount
local other=SpawnPrefab('aom_tractor_chassis');assert(other:AttachAttachment(nil,item))
ok,reason=ACTION_DEFS.AOM_REPAIR.fn({doer=player,target=item,invobject=flint})
assert(not ok and reason=='DETACH_FIRST' and Durability.GetUses(item)==5)
assert(flint.components.stackable:StackSize()==3)
''')


if __name__ == '__main__':unittest.main()
