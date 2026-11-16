"""自动配比UI回归：移除规划确认入口，保留真实驾驶权限、三行信息及原图标操作。"""
import unittest
import test_dashboard as dashboard


class AutomaticGiantUITests(unittest.TestCase):
    setUp=dashboard.DashboardTests.setUp
    run_lua=dashboard.DashboardTests.run_lua

    def test_all_two_seed_modes_have_no_manual_planning_widgets_or_rpcs(self):
        self.run_lua('''
attach('aom_seeder')
for _,mode in ipairs({'SEQUENTIAL','GIANT'})do
 t._seed_strategy=mode;t._seedmode_net:set(mode);hud:Refresh(t)
 assert(hud.seedbutton==nil and hud.seedbackground==nil and hud.seedcontrols==nil)
 assert(hud.planbutton==nil and hud.rotatebutton==nil and hud._plan_markers==nil)
end
assert(RPCS.AOM_PLAN==nil and RPCS.AOM_PLAN_ROTATE==nil)
assert(AOM_RPC.PLAN==nil and AOM_RPC.PLAN_ROTATE==nil)
''')

    def test_giant_f_starts_without_any_plan_preview_or_confirmation(self):
        self.run_lua('''
attach('aom_seeder');local seed=SpawnPrefab('tomato_seeds')
seed.components.stackable:SetStackSize(20);assert(t.components.container:GiveItem(seed))
t:CycleSeedStrategy(player)
assert(t._seed_strategy=='GIANT_TEMPLATE' and t._block==nil)
RPCS.AOM_TOGGLE_WORK(player)
assert(t._working and t._worktask and t._workstate_net:value()~='PLAN_PENDING')
''')

    def test_real_prefab_rider_container_and_native_plant_action_sow_automatically(self):
        self.run_lua('''
attach('aom_seeder')
TheWorld.Map.GetTileCoordsAtPoint=function(_,x,y,z)return center(x)/4,center(z)/4 end
TheWorld.state={season='autumn'};TheWorld.components=TheWorld.components or {}
TheWorld.components.farming_manager={GetTileNutrients=function()return 100,100,100 end}
for _,kind in ipairs({'tomato','potato'})do
 local seed=SpawnPrefab(kind..'_seeds');seed.components.stackable:SetStackSize(8)
 assert(t.components.container:GiveItem(seed))
end
for x=-1,1 do for z=-1,1 do SpawnPrefab('farm_soil').Transform:SetPosition(x*4/3,0,z*4/3)end end
t:CycleSeedStrategy(player)
local queue={};t.DoTaskInTime=function(_,_,fn)queue[#queue+1]=fn end
RPCS.AOM_TOGGLE_WORK(player);assert(t._working)
require('aom_drive').TrackMovement(t)
local steps=0;while #queue>0 do steps=steps+1;assert(steps<20000);table.remove(queue,1)() end
require('aom_drive').TrackMovement(t)
local count=0
for _,v in ipairs(ENTITIES)do if v:IsValid() and v:HasTag('farm_plant')then count=count+1 end end
assert(count==8 and t._block.automatic and t._block.done==8 and t._working)
assert(t.components.aom_attachment_store:GetSeedCount()==8 and t._fuel:value()==392)
hud:Refresh(t);assert(hud.seedcontrols==nil and string.find(hud.badges.tool:GetTooltip(),'耐久 99/100',1,true))
''')

    def test_seeder_hover_has_exact_three_lines_from_synchronized_values(self):
        self.run_lua('''
local seeder=attach('aom_seeder');seeder.components.finiteuses:SetUses(61)
t:CycleSeedStrategy(player);hud:Refresh(t)
assert(hud.badges.tool:GetTooltip()=='播种机'..string.char(10)..'耐久 61/100'..string.char(10)..'播种策略：巨大化·模版')
assert(hud.badges.tool:GetText()=='61')
local old=t.components;t.components={};hud:Refresh(t)
assert(hud.badges.tool:GetTooltip()=='播种机'..string.char(10)..'耐久 61/100'..string.char(10)..'播种策略：巨大化·模版')
t.components=old
''')

    def test_existing_preview_markers_are_cleaned_without_creating_new_ones(self):
        self.run_lua('''
attach('aom_seeder');t:CycleSeedStrategy(player)
local marker=CreateEntity();hud._plan_markers={marker};hud._plan_marker_key='old'
hud:Refresh(t)
assert(not marker:IsValid() and hud._plan_markers==nil and hud._plan_marker_key==nil)
''')

    def test_stale_seed_click_after_dismount_cannot_change_strategy(self):
        self.run_lua('''
attach('aom_seeder');t:CycleSeedStrategy(player)
player.components.rider:ActualDismount();hud.badges.tool.onclick()
assert(t._seed_strategy=='GIANT_TEMPLATE')
hud:Refresh(nil);assert(not hud:IsVisible())
''')


if __name__=='__main__':unittest.main()
