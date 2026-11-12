"""服务端只读规划、确认/RPC权限和客户端预览生命周期。"""
import unittest
import test_dashboard as dashboard

class PlanPreviewTests(unittest.TestCase):
    setUp=dashboard.DashboardTests.setUp
    run_lua=dashboard.DashboardTests.run_lua

    def prepare(self):
        self.run_lua('''
attach('aom_seeder');t:CycleSeedStrategy(player);t:CycleSeedStrategy(player)
assert(t._seed_strategy=='GIANT')
for _,crop in ipairs({'tomato','potato'})do
 local seed=SpawnPrefab(crop..'_seeds');seed.components.stackable:SetStackSize(4)
 t.components.container:GiveItem(seed)
end
hud:Refresh(t);click(hud.badges.tool)
''')

    def test_preview_rotation_and_confirm_never_modify_soil_or_consume_resources(self):
        self.prepare();self.run_lua('''
local fuel=t._fuel:value();local uses=t.components.finiteuses:GetUses()
local seeds=t.components.aom_attachment_store:GetSeedCount()
click(hud.planbutton)
assert(t._block and t._block.confirmed==false and t._workstate_net:value()=='PLAN_PENDING')
assert(#hud._plan_markers==8 and hud.planbutton:GetText()=='确认' and hud.rotatebutton:IsVisible())
for _,m in ipairs(hud._plan_markers)do
 assert(m:HasTag('FX') and m:HasTag('NOCLICK') and not m:HasTag('soil'))
 assert(not m.persists and not m.components.farmplantable and not m.components.inventoryitem)
end
local old=hud._plan_markers;click(hud.rotatebutton)
assert(t._block.rotation==1 and t._block.confirmed==false)
for _,m in ipairs(old)do assert(not m:IsValid())end
RPCS.AOM_TOGGLE_WORK(player);assert(not t._working and not t._block.confirmed)
click(hud.planbutton);assert(t._block.confirmed and not hud.rotatebutton:IsVisible())
assert(t._fuel:value()==fuel and t.components.finiteuses:GetUses()==uses)
assert(t.components.aom_attachment_store:GetSeedCount()==seeds)
for _,e in ipairs(ENTITIES)do assert(not (e:IsValid() and e.prefab=='farm_soil'))end
RPCS.AOM_TOGGLE_WORK(player);assert(t._working)
''')

    def test_first_f_only_previews_and_stock_change_prevents_confirmation(self):
        self.prepare();self.run_lua('''
RPCS.AOM_TOGGLE_WORK(player);assert(not t._working and t._block.confirmed==false)
local seed=t.components.container:GetItemInSlot(1)
t.components.container:RemoveItem(seed,true)
RPCS.AOM_PLAN(player)
assert(t._block.confirmed==false and t._workstate_net:value()=='MISSING_SEEDS')
''')

    def test_pending_plan_roundtrip_and_markers_removed_on_mode_change_or_dismount(self):
        self.prepare();self.run_lua('''
click(hud.planbutton);local record=clone(t:GetSaveRecord())
assert(record.data.block.version==3 and record.data.block.confirmed==false)
local old=hud._plan_markers
player.components.rider:ActualDismount();hud:Refresh(nil)
for _,m in ipairs(old)do assert(not m:IsValid())end
local restored=SpawnSaveRecord(record)
assert(restored._block.confirmed==false)
local block=require('aom_block_plan');assert(block.Decode(restored._plan_net:value()).confirmed==false)
''')

    def test_plan_rpc_rejects_non_driver_busy_and_other_attachments(self):
        self.prepare();self.run_lua('''
RPCS.AOM_PLAN(make_player());assert(t._block==nil)
player.sg:GoToState('mount');RPCS.AOM_PLAN(player);assert(t._block==nil)
player.sg:GoToState('mounted_idle')
attach('aom_weeder');RPCS.AOM_PLAN(player);assert(t._block==nil)
''')

    def test_confirmation_rechecks_buildings_added_after_preview(self):
        self.prepare();self.run_lua('''
click(hud.planbutton)
local wall=CreateEntity();wall.prefab='wall_stone';wall.Transform:SetPosition(0,0,0)
RPCS.AOM_PLAN(player)
assert(not t._block.confirmed and t._workstate_net:value()=='BLOCKED_MOUND')
wall:Remove();RPCS.AOM_PLAN(player);assert(t._block.confirmed)
''')

    def test_decoder_rejects_unknown_layout_coordinates_and_invalid_completed_indices(self):
        self.run_lua('''
local Block=require('aom_block_plan')
for _,text in ipairs({'garbage','autumn-01-02;nan;0;0;0;',
 'autumn-01-02;0;0;8;0;','autumn-01-02;0;0;0;0;999','autumn-01-02;0;0;0;0;1,1'})do
 assert(not Block.Decode(text),text)
end
''')

    def test_client_renders_from_network_only_and_cargo_warning_does_not_depend_on_language(self):
        self.prepare();self.run_lua('''
click(hud.planbutton)
local proxy={GUID=999,IsValid=function()return true end,_plan_net=t._plan_net,
 _seedmode_net=t._seedmode_net,_atttype_net=t._atttype_net,
 _workstate_net=t._workstate_net}
require('aom_work_status').Set(t,'CARGO_FULL')
require('aom_common').SetLanguage('en');hud:Refresh(proxy)
assert(hud.badges.cargo.meter.warningstarted)
assert(string.find(hud.planbutton:GetTooltip(),'area 1x1',1,true))
assert(#hud._plan_markers==8)
hud:Refresh(nil);assert(hud._plan_markers==nil)
''')

if __name__=='__main__':unittest.main()
