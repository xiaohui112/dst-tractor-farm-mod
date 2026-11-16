"""洒水完整流程，原版土壤管理器/水量组件/实体存读档真实执行。"""
from pathlib import Path
import unittest
from test_giant_farming import World

ROOT=Path(__file__).resolve().parents[2]

class IrrigatorFlowTests(unittest.TestCase):
    def setUp(self):
        self.w=World()
        self.w.lua.globals().REF=str(ROOT/'tools/api-ref')
        self.w.lua.globals().TESTS=str(ROOT/'tools/tests')
        self.w.lua.execute((ROOT/'tools/tests/irrigator_engine.lua').read_text())

    def run_lua(self,s): self.w.lua.execute(s)

    def test_new_tank_empty_and_full_capacity(self):
        self.run_lua('assert(water_count()==0 and store:GetWaterMax()==400 and tank.components.finiteuses.doesnotstartfull)')

    def test_watercan_one_use_equals_one_dose_and_fills_small_gap(self):
        self.run_lua('''
local can=watercan(1)
assert(Irrigator.Load(store,can));assert(water_count()==1 and can.components.finiteuses:GetUses()==0)
fill(384);can=watercan(20)
assert(Irrigator.Load(store,can));assert(water_count()==400 and can.components.finiteuses:GetUses()==5)
assert(not Irrigator.Load(store,can));assert(can.components.finiteuses:GetUses()==5)
''')

    def test_premium_can_and_empty_can(self):
        self.run_lua('''
local can=watercan(160,'premiumwateringcan')
assert(Irrigator.Load(store,can));assert(water_count()==160 and can.components.finiteuses:GetUses()==0)
store:TakeWater();can=watercan(0)
assert(not Irrigator.Load(store,can));assert(water_count()==159)
''')

    def test_ice_consumes_only_one_and_nothing_when_full(self):
        self.run_lua('''
local ice=CreateEntity();ice.prefab='ice';local n=5;local removed=0
ice.components.stackable={StackSize=function()return n end,Get=function(_,count)n=n-count;return {Remove=function()removed=removed+1 end}end}
assert(Irrigator.Load(store,ice));assert(n==4 and removed==1 and ice.valid and water_count()==1)
fill(400);assert(not Irrigator.Load(store,ice));assert(n==4 and removed==1)
local single=CreateEntity();single.prefab='ice';store:TakeWater()
assert(Irrigator.Load(store,single));assert(not single.valid and water_count()==400)
''')

    def test_arbitrary_fillable_is_rejected_without_spending(self):
        self.run_lua("local fake=watercan(20,'other_tool');assert(not Irrigator.Load(store,fake));assert(water_count()==0 and fake.components.finiteuses:GetUses()==20)")

    def test_store_operations_ignore_other_attachment_and_bound_integer_units(self):
        self.run_lua('''
assert(store:AddWater(-2)==0 and store:AddWater(2.9)==2)
assert(store:AddWater(999)==398 and store:ReturnWater()==0)
inst.components.container.slots[1]=SpawnPrefab('aom_landclearer')
assert(store:GetWater()==0 and store:GetWaterMax()==0 and store:AddWater(3)==0)
assert(not store:TakeWater() and store:ReturnWater()==0)
assert(inst.components.container.slots[1].components.finiteuses:GetUses()==100)
''')

    def test_empty_partial_and_full_save_roundtrip_uses_native_lifecycle(self):
        self.run_lua('''
for _,n in ipairs({0,13,40,400})do
 tank.components.finiteuses:SetUses(n)
 local data=save_water(tank)
 assert(data.aom_water_version==1 and data.finiteuses.uses==n)
 local restored=reload_water(data)
 assert(restored.components.finiteuses:GetUses()==n and restored.components.finiteuses.total==400)
end
''')

    def test_legacy_full_partial_empty_overflow_and_new_missing_data(self):
        self.run_lua('''
for _,case in ipairs({{{},40},{{finiteuses={uses=100}},40},{{finiteuses={uses=23}},23},
 {{finiteuses={uses=0}},0},{{finiteuses={uses=-3}},0},{{finiteuses={uses=9.9}},9},
 {{aom_water_version=1},0}})do
 local item=reload_water(case[1]);assert(item.components.finiteuses:GetUses()==case[2])
 local again=reload_water(save_water(item));assert(again.components.finiteuses:GetUses()==case[2])
end
''')

    def test_single_pass_fills_dry_tile_bills_four_water_one_fuel_one_chassis(self):
        self.run_lua('''
fill(40);start_water();Drive.TrackMovement(inst)
assert(moisture(0,0)==100 and water_count()==36)
assert(inst._fuel:value()==799 and inst.components.finiteuses.used==1 and inst._working)
''')

    def test_partial_moisture_uses_only_required_whole_doses(self):
        self.run_lua('''
fill(40);soil(0,0,62);assert(Drive.WorkTile(inst,0,0))
assert(moisture(0,0)==100 and water_count()==38 and inst._fuel:value()==799 and inst.components.finiteuses.used==1)
soil(4,0,99);assert(Drive.WorkTile(inst,4,0));assert(water_count()==37 and moisture(4,0)==100)
''')

    def test_full_and_nonfarmland_stop_when_empty_without_spending(self):
        self.run_lua('''
soil(0,0,100);inst._fuel:set(0);start_water()
assert(not Drive.WorkTile(inst,0,0));TILES[tkey(4,0)]=-1
assert(not Drive.WorkTile(inst,4,0))
assert(water_count()==0 and inst._fuel:value()==0 and inst.components.finiteuses.used==0 and not inst._working)
''')

    def test_parking_and_return_to_full_tile_do_not_drain(self):
        self.run_lua('''
fill(40);start_water();Drive.TrackMovement(inst)
for i=1,30 do Drive.TrackMovement(inst)end
assert(water_count()==36 and inst._fuel:value()==799)
inst.x=4;Drive.TrackMovement(inst);inst.x=0;Drive.TrackMovement(inst)
assert(water_count()==32 and inst._fuel:value()==798 and inst.components.finiteuses.used==2)
''')

    def test_rain_manual_watering_and_plant_drying_are_read_live(self):
        self.run_lua('''
fill(40);assert(Drive.WorkTile(inst,0,0));soil(0,0,60)
FM:AddSoilMoistureAtPoint(0,0,0,25) -- 玩家先浇了一次
assert(Drive.WorkTile(inst,0,0));assert(water_count()==35 and moisture(0,0)==100)
soil(4,0,nil);TheWorld.state.wetness=90 -- 原版 nil 回退世界湿度
assert(Drive.WorkTile(inst,4,0));assert(water_count()==34 and moisture(4,0)==100)
soil(8,0,0);TheWorld.state.wetness=90 -- 已有0值第一剂原版会钳到90，还需一剂
assert(Drive.WorkTile(inst,8,0));assert(water_count()==32 and moisture(8,0)==100)
''')

    def test_shortage_preserves_partial_progress_stops_and_refill_resumes(self):
        self.run_lua('''
fill(2);start_water();Drive.TrackMovement(inst)
assert(moisture(0,0)==50 and water_count()==0 and not inst._working)
assert(inst._fuel:value()==799 and inst.components.finiteuses.used==1)
assert(string.find(require('aom_work_status').Describe(inst),'水箱已空'))
assert(Irrigator.Load(store,watercan(5)));start_water();Drive.TrackMovement(inst)
assert(moisture(0,0)==100 and water_count()==3 and inst._fuel:value()==798 and inst.components.finiteuses.used==2)
''')

    def test_empty_before_start_does_not_spend(self):
        self.run_lua('start_water();Drive.TrackMovement(inst);assert(not inst._working and moisture(0,0)==0 and inst._fuel:value()==800 and inst.components.finiteuses.used==0)')

    def test_one_fuel_completes_full_tile_and_zero_fuel_does_not_spend_water(self):
        self.run_lua('''
fill(10);inst._fuel:set(1);start_water();Drive.TrackMovement(inst)
assert(moisture(0,0)==100 and water_count()==6 and inst._fuel:value()==0 and not inst._working)
start_water();inst.x=4;Drive.TrackMovement(inst)
assert(moisture(4,0)==0 and water_count()==6 and inst.components.finiteuses.used==1 and not inst._working)
''')

    def test_native_manager_no_overlay_refunds_and_stops(self):
        self.run_lua('''
fill(10);soil(0,0,0,false);start_water();Drive.TrackMovement(inst)
assert(water_count()==10 and moisture(0,0)==0 and inst._fuel:value()==800 and not inst._working)
assert(inst.components.finiteuses.used==0)
''')

    def test_unreadable_manager_or_debug_unavailable_fail_without_consumption(self):
        self.run_lua('''
fill(10);local fn=FM.IsSoilMoistAtPoint
FM.IsSoilMoistAtPoint=function()return true end
start_water();Drive.TrackMovement(inst)
assert(not inst._working and water_count()==10 and inst._fuel:value()==800)
FM.IsSoilMoistAtPoint=fn;local old=debug;debug=nil
start_water();Drive.TrackMovement(inst);debug=old
assert(not inst._working and water_count()==10 and moisture(0,0)==0)
''')

    def test_wrapped_native_getter_and_replaced_grid_are_not_cached(self):
        self.run_lua('''
fill(10);local original=FM.IsSoilMoistAtPoint
FM.IsSoilMoistAtPoint=function(...)return original(...)end
assert(Drive.WorkTile(inst,0,0));GRIDS[2]:Load({['0:0']=75})
assert(Drive.WorkTile(inst,0,0));assert(water_count()==5 and moisture(0,0)==100)
''')

    def test_native_error_before_change_refunds_and_after_change_bills_actual_progress(self):
        self.run_lua('''
fill(10);local add=FM.AddSoilMoistureAtPoint
FM.AddSoilMoistureAtPoint=function()error('failure before watering')end
start_water();Drive.TrackMovement(inst);assert(water_count()==10 and inst._fuel:value()==800 and not inst._working)
FM.AddSoilMoistureAtPoint=function(...)add(...);error('failure after watering')end
start_water();Drive.TrackMovement(inst)
assert(water_count()==9 and moisture(0,0)==25 and inst._fuel:value()==799 and not inst._working)
FM.AddSoilMoistureAtPoint=add;start_water();Drive.TrackMovement(inst)
assert(water_count()==6 and moisture(0,0)==100 and inst._fuel:value()==798)
''')

    def test_crossing_multiple_tiles_fills_each_tile_once(self):
        self.run_lua('''
fill(40);start_water();Drive.TrackMovement(inst);inst.x=12;Drive.TrackMovement(inst)
for x=0,12,4 do assert(moisture(x,0)==100)end
assert(water_count()==24 and inst._fuel:value()==796 and inst.components.finiteuses.used==4)
''')

    def test_last_dose_completes_tile_then_stops(self):
        self.run_lua('''
local messages={}
inst._rider.components.talker={Say=function(_,text)messages[#messages+1]=text end}
fill(4);start_water();Drive.TrackMovement(inst)
assert(moisture(0,0)==100 and water_count()==0 and not inst._working)
assert(not tank._aom_working:value() and tank._aom_work_effects==nil)
assert(inst._fuel:value()==799 and inst.components.finiteuses.used==1)
assert(#messages==1 and messages[1]==require('aom_work_status').Describe(inst) and string.find(messages[1],'水箱已空'))
for i=1,10 do Drive.TrackMovement(inst)end
assert(#messages==1)
''')

    def test_full_lifecycle_load_save_swap_start_shortage_resume_dismount(self):
        text=(ROOT/'mod/Tractor/modmain.lua').read_text()
        start=text.index('local AOM_LOAD = AddAction(')
        end=text.index('AOM_LOAD.distance',start)
        self.run_lua('function AddAction(id,label,fn)LoadAction=fn;return {}end')
        self.run_lua("local Feedback=require('aom_feedback')\n"+text[start:end])
        self.run_lua('''
assert(water_count()==0)
local can=watercan(2)
assert(LoadAction({target=inst,invobject=can,doer=inst._rider}))
assert(can.components.finiteuses:GetUses()==0 and water_count()==2)
local saved=save_water(tank);tank=reload_water(saved)
inst.components.container.slots[1]=tank;assert(water_count()==2)
local farmer=inst._rider
farmer.components.rider={IsRiding=function()return true end,GetMount=function()return inst end}
function inst:DoPeriodicTask(_,fn)return {Cancel=function()end,fn=fn}end
assert(Drive.ToggleWorking(inst,farmer));Drive.TrackMovement(inst)
assert(not inst._working and moisture(0,0)==50 and inst._fuel:value()==799)
assert(LoadAction({target=inst,invobject=watercan(6),doer=farmer}))
assert(Drive.ToggleWorking(inst,farmer));Drive.TrackMovement(inst)
assert(inst._working and moisture(0,0)==100 and water_count()==4 and inst._fuel:value()==798)
local new_tank=SpawnPrefab('aom_irrigator');inst.components.container.slots[1]=new_tank
assert(store:GetWater()==0 and tank.components.finiteuses:GetUses()==4)
inst.components.container.slots[1]=reload_water(save_water(tank));assert(water_count()==4)
Drive.OnDismounted(inst);assert(not inst._working and water_count()==4)
''')

    def test_tuning_controls_dose_and_target_but_tank_capacity_is_independent(self):
        self.run_lua('''
TUNING.SOIL_MAX_MOISTURE_VALUE=100 -- manager captures native max at construction
TUNING.WATERINGCAN_WATER_AMOUNT=10
fill(40);assert(Drive.WorkTile(inst,0,0));assert(water_count()==30 and moisture(0,0)==100)
TUNING.WATERINGCAN_USES=60;local item=SpawnPrefab('aom_irrigator')
assert(item.components.finiteuses.total==400 and item.components.finiteuses:GetUses()==0)
''')

if __name__=='__main__': unittest.main()
