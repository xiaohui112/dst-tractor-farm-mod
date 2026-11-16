"""100耐久/400水量、堆叠货物总数、播种设置与补给悬停信息。"""
import unittest
import test_world_equipment as world
import test_dashboard as dashboard


class SupplyFeedbackTests(unittest.TestCase):
    setUp=world.WorldEquipmentTests.setUp
    run_lua=world.WorldEquipmentTests.run_lua

    def test_real_seeder_stops_at_one_hundred_uses_and_preserves_remaining_cargo(self):
        self.run_lua(r'''
local item=equipment('aom_seeder');assert(item.components.finiteuses.total==100)
assert(t:AttachAttachment(nil,item));ride()
for slot=1,9 do
 local seed=SpawnPrefab('tomato_seeds');seed.components.stackable:SetStackSize(40)
 assert(t.components.container:GiveItem(seed,slot))
end
assert(t._cargo_count_net:value()==360 and t._seedcount_net:value()==360)
local Drive=require('aom_drive')
for tile=0,11 do
 local x=tile*4;player.Transform:SetPosition(x,0,0)
 for row=-1,1 do for col=-1,1 do SpawnPrefab('farm_soil').Transform:SetPosition(x+col*4/3,0,row*4/3)end end
 Drive.WorkTile(t,x,0)
end
assert(item:IsValid() and t:GetAttachment()==nil and Durability.GetUses(item)==0)
assert(t._fuel:value()==300 and t.components.finiteuses:GetUses()==900)
assert(t._cargo_count_net:value()==260 and t._seedcount_net:value()==260)
local planted=0;for _,e in ipairs(ENTITIES)do if e:IsValid() and e.prefab=='farm_plant_tomato' then planted=planted+1 end end
assert(planted==100)
''')

    def test_cargo_counts_all_stacks_and_updates_from_native_source_events_and_removal(self):
        self.run_lua(r'''
local cargo=t.components.container
local seeds=SpawnPrefab('tomato_seeds');seeds.components.stackable:SetStackSize(40);assert(cargo:GiveItem(seeds,1))
local rocks=SpawnPrefab('rocks');rocks.components.stackable:SetStackSize(20);assert(cargo:GiveItem(rocks,2))
local single=SpawnPrefab('nonstack_cargo');assert(cargo:GiveItem(single,3))
assert(t._cargo_used_net:value()==3 and t._cargo_count_net:value()==61)
local push=rocks.PushEvent
rocks.PushEvent=function(self,event,data)
 local callbacks={};for _,cb in ipairs(self.events[event] or {})do callbacks[#callbacks+1]=cb.fn end
 for _,fn in ipairs(callbacks)do fn(self,data)end
end
rocks.components.stackable:SetStackSize(9);assert(t._cargo_count_net:value()==50)
assert(cargo:RemoveItemBySlot(2)==rocks and t._cargo_count_net:value()==41)
rocks.components.stackable:SetStackSize(3);assert(t._cargo_count_net:value()==41)
local record=clone(t:GetSaveRecord());t:Remove();local restored=SpawnSaveRecord(record)
assert(restored._cargo_count_net:value()==41 and restored._cargo_used_net:value()==2)
''')

    def test_flint_cannot_repair_vehicle_or_attached_tool_and_never_gets_consumed(self):
        self.run_lua(r'''
local item=equipment('aom_seeder');assert(t:AttachAttachment(nil,item));item.components.finiteuses:SetUses(21)
t.components.finiteuses:SetUses(900);t.components.health:SetVal(500)
local flint=SpawnPrefab('flint');flint.components.stackable:SetStackSize(3)
local actions=prompt(flint,player,t);for _,a in ipairs(actions)do assert(a~=ACTION_DEFS.AOM_REPAIR)end
assert(not t:TryRepair(player,flint))
assert(not ACTION_DEFS.AOM_REPAIR.fn({doer=player,target=t,invobject=flint}))
assert(flint.components.stackable:StackSize()==3 and Durability.GetUses(item)==21)
assert(t.components.finiteuses:GetUses()==900 and t.components.health.currenthealth==500)
assert(t:DetachAttachment(nil));player.Transform:SetPosition(item.Transform:GetWorldPosition())
assert(ACTION_DEFS.AOM_REPAIR.fn({doer=player,target=item,invobject=flint}))
assert(Durability.GetUses(item)==31 and flint.components.stackable:StackSize()==2)
local gears=SpawnPrefab('gears');assert(t:TryRepair(player,gears))
assert(not gears:IsValid() and t.components.health.currenthealth==600 and t.components.finiteuses:GetUses()==1000)
''')

    def test_tank_capacity_and_hover_water_are_independent_from_mechanical_uses_and_survive_save(self):
        self.run_lua(r'''
local Info=require('aom_machine_info');local item=equipment('aom_irrigator')
assert(item:HasTag('hide_percentage') and item.components.finiteuses.total==400)
assert(t:AttachAttachment(nil,item));item._aom_machine_uses=23;item._durability_net:set(23)
assert(t.components.aom_attachment_store:AddWater(999)==400)
assert(item._aom_water_net:value()==400 and t._water_net:value()==400 and t._watermax_net:value()==400)
assert(Info.Describe(item)=='机械耐久 23/100\n水量 400/400')
t.components.aom_attachment_store:TakeWater();assert(item._aom_water_net:value()==399 and Durability.GetUses(item)==23)
for _,water in ipairs({0,40,400})do
 item.components.finiteuses:SetUses(water)
 local record=clone(t:GetSaveRecord());local restored=SpawnSaveRecord(record)
 assert(restored.components.aom_attachment_store:GetWater()==water)
 local tank=restored:GetAttachment();assert(tank.components.finiteuses.total==400 and Durability.GetUses(tank)==23)
 assert(tank._aom_water_net:value()==water);restored:Remove()
end
''')

    def test_new_capacity_preserves_old_remaining_seeder_uses_and_water_without_free_refills(self):
        self.run_lua(r'''
local seeder=equipment('aom_seeder');seeder.components.finiteuses:SetUses(21)
local old=clone(seeder:GetSaveRecord());local loaded=SpawnSaveRecord(old)
assert(loaded.components.finiteuses.total==100 and Durability.GetUses(loaded)==21)
local tank=equipment('aom_irrigator');tank.components.finiteuses:SetUses(40)
old=clone(tank:GetSaveRecord());loaded=SpawnSaveRecord(old)
assert(loaded.components.finiteuses.total==400 and loaded.components.finiteuses:GetUses()==40)
''')

    def test_hover_adds_fuel_while_holding_repair_or_fuel_items_and_uses_client_network_only(self):
        self.run_lua(r'''
local target=t;TheInput.GetWorldEntityUnderMouse=function()return target end
TheInput.GetHUDEntityUnderMouse=function()return nil end
local hover={text={SetString=function(self,s)self.value=s end}}
assert(POST_FNS['widgets/hoverer']);POST_FNS['widgets/hoverer'](hover)
local components=t.components;t.components={};t._fuel:set(123)
for _,action in ipairs({'存放','检查','修理','加油'})do
 hover.text:SetString(action..'\n耐久：900/1000')
 assert(hover.text.value==action..'\n耐久：900/1000\n燃料 123/800')
end
hover.text:SetString(hover.text.value);assert(select(2,hover.text.value:gsub('燃料',''))==1)
target=equipment('aom_irrigator');target.components={};target._aom_water_net:set(312);target._durability_net:set(45)
hover.text:SetString('检查 洒水机');assert(hover.text.value=='检查 洒水机\n机械耐久 45/100\n水量 312/400')
target=SpawnPrefab('rocks');hover.text:SetString('检查 岩石');assert(hover.text.value=='检查 岩石')
target=t;TheInput.GetHUDEntityUnderMouse=function()return {}end
hover.text:SetString('界面提示');assert(hover.text.value=='界面提示')
t.components=components
''')

    def test_hover_composes_with_show_me_wrappers_in_both_registration_orders(self):
        self.run_lua(r'''
TheInput.GetWorldEntityUnderMouse=function()return t end
TheInput.GetHUDEntityUnderMouse=function()return nil end
local Info=require('aom_machine_info')
local function show_me(h)
 local original=h.text.SetString
 h.text.SetString=function(text,str)
  text.cnt_lines=2;return original(text,str..'\n耐久：900/1000\n ')
 end
end
for _,ours_first in ipairs({false,true})do
 local h={text={SetString=function(self,s)self.value=s end}}
 if ours_first then Info.Install(h);show_me(h)else show_me(h);Info.Install(h)end
 h.text:SetString('修理')
 assert(string.find(h.text.value,'燃料 400/800',1,true) and string.find(h.text.value,'耐久：900/1000',1,true))
 assert(h.text.cnt_lines==3)
end
''')


class SupplyDashboardTests(unittest.TestCase):
    setUp=dashboard.DashboardTests.setUp
    run_lua=dashboard.DashboardTests.run_lua

    def test_cargo_before_tool_shows_360_items_and_seeder_has_no_permanent_strip(self):
        self.run_lua(r'''
attach('aom_seeder')
for slot=1,9 do local seed=SpawnPrefab('tomato_seeds');seed.components.stackable:SetStackSize(40);assert(t.components.container:GiveItem(seed,slot))end
hud:Refresh(t)
assert(hud.order[4]=='cargo' and hud.order[5]=='tool')
assert(hud.badges.cargo:GetText()=='360' and hud.badges.cargo.meter.percent==9/15)
assert(string.find(hud.badges.cargo:GetTooltip(),'9/15格',1,true))
assert(hud.strip==nil and hud.seedcontrols==nil and hud.seedbutton==nil)
click(hud.badges.tool);assert(t._seed_strategy=='GIANT_TEMPLATE' and hud.seedcontrols==nil)
click(hud.badges.tool);assert(t._seed_strategy=='GIANT' and hud.planbutton==nil)
assert(hud.seedbackground==nil and hud.seedcontrols==nil)
click(hud.badges.tool);assert(hud.seedcontrols==nil)
attach('aom_irrigator');assert(hud.strip==nil and hud.badges.water:IsVisible() and hud.seedcontrols==nil)
''')


if __name__=='__main__':unittest.main()
