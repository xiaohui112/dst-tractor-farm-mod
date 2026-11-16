"""普通/巨大作物一趟收割，执行原版采摘、工作组件及巨大作物掉落函数。"""
from pathlib import Path
import unittest
from test_giant_farming import World

ROOT = Path(__file__).resolve().parents[2]


class HarvesterFlowTests(unittest.TestCase):
    def setUp(self):
        self.w = World()
        self.w.lua.globals().REF = str(ROOT / 'tools/api-ref')
        for name in ('landclearer_engine.lua', 'harvester_engine.lua'):
            self.w.lua.execute((ROOT / 'tools/tests' / name).read_text())
        self.w.lua.execute('start_harvester()')
        self.w.lua.execute("tool=inst.components.container:GetItemInSlot(1)")

    def run_lua(self, source):
        self.w.lua.execute(source)

    def test_nine_giant_plants_are_picked_and_smashed_in_one_pass(self):
        self.run_lua('''
for x=-1,1 do for z=-1,1 do crop('tomato',x,z,true)end end
Drive.SetWorking(inst,true);Drive.TrackMovement(inst)
assert(count_entities('farm_plant_tomato')==0 and count_entities('tomato_oversized')==0)
assert(count_entities('tomato')+count_entities('tomato_seeds')==45)
assert(inst._fuel:value()==799 and inst.components.finiteuses.used==1)
assert(tool.components.finiteuses:GetUses()==99)
for i=1,20 do Drive.TrackMovement(inst)end
assert(inst._fuel:value()==799 and count_entities('tomato')+count_entities('tomato_seeds')==45)
assert(tool.components.finiteuses:GetUses()==99)
''')

    def test_continuous_driving_passes_empty_tile_and_harvests_next_tile(self):
        self.run_lua('''
local first=crop('tomato',0,0,false);local next=crop('pumpkin',8,0,true)
Drive.SetWorking(inst,true);Drive.TrackMovement(inst)
assert(not first.valid and next.valid and inst._working)
for i=1,10 do Drive.TrackMovement(inst)end
assert(inst._fuel:value()==799 and tool.components.finiteuses:GetUses()==99)
inst.x=8;Drive.TrackMovement(inst)
assert(not next.valid and count_entities('pumpkin_oversized')==0 and inst._working)
assert(inst._fuel:value()==798 and tool.components.finiteuses:GetUses()==98)
Drive.SetWorking(inst,false);assert(not inst._working and not inst._worktask)
''')

    def test_all_crop_definitions_support_normal_and_giant_harvest(self):
        self.run_lua('''
for name in pairs(DEFS)do
 ENTITIES={};local a=crop(name,-1,0,false);local b=crop(name,1,0,true)
 local worked,reason,ready=Farm.Harvest(0,0,0,inst._rider)
 assert(worked and ready and reason==nil and not a.valid and not b.valid)
 assert(count_entities(name..'_oversized')==0)
 assert(count_entities(name)+count_entities(name..'_seeds')==7)
end
''')

    def test_native_giant_loot_preserves_both_random_outcomes(self):
        self.run_lua('''
local random=math.random
for _,roll in ipairs({.1,.9})do
 ENTITIES={};math.random=function()return roll end
 local v=giant('carrot');math.random=random
 assert(Drive.WorkTile(inst,0,0) and not v.valid)
 assert(count_entities('carrot')==(roll<.75 and 3 or 2))
 assert(count_entities('carrot_seeds')==(roll<.75 and 2 or 3))
end
''')

    def test_ground_giants_and_corners_are_included_but_neighbors_are_safe(self):
        self.run_lua('''
local here=giant('pumpkin',1.99,1.99)
local next=giant('pumpkin',2.01,0)
local nextplant=crop('pumpkin',2.01,1,true)
assert(Farm.CanWorkAt('harvester',0,0,0))
assert(Drive.WorkTile(inst,0,0) and not here.valid and next.valid and nextplant.valid)
assert(inst._fuel:value()==799 and inst.components.finiteuses.used==1)
assert(not Drive.WorkTile(inst,0,0) and inst._fuel:value()==799)
''')

    def test_new_giant_returned_in_driver_inventory_is_dropped_at_source_then_smashed(self):
        self.run_lua('''
give_driver_inventory(true)
local v=crop('tomato',1.99,1.99,true)
inst.x=8;inst.z=0 -- 补齐跨格路径时，驾驶员可能已经驶离本株所在地块。
assert(Drive.WorkTile(inst,0,0) and not v.valid)
assert(count_entities('tomato_oversized')==0)
assert(count_entities('tomato')+count_entities('tomato_seeds')==5)
for _,v in ipairs(ENTITIES)do if v.prefab=='tomato' or v.prefab=='tomato_seeds' then
 assert(v.x==1.99 and v.z==1.99)
end end
''')

    def test_native_drop_picked_path_is_found_without_returned_loot(self):
        self.run_lua('''
local v=crop('carrot',0,0,true);v.components.pickable.droppicked=true
assert(Drive.WorkTile(inst,0,0) and not v.valid)
assert(count_entities('carrot_oversized')==0)
assert(count_entities('carrot')+count_entities('carrot_seeds')==5)
''')

    def test_new_giant_never_enters_driver_inventory_or_calls_drop(self):
        self.run_lua('''
local inv=give_driver_inventory(true);inv.DropItem=function()error('must stay on ground')end
local v=crop('tomato',0,0,true)
local changed,reason=Drive.WorkTile(inst,0,0)
assert(changed and reason==nil and not v.valid)
assert(count_entities('tomato_oversized')==0 and #inv.items==0)
assert(inst._fuel:value()==799)
''')

    def test_waxed_owned_giants_buildings_weeds_and_unripe_crops_are_preserved(self):
        self.run_lua('''
local waxed=giant('tomato',0,0,'_waxed')
local held=giant('tomato',1,0);held.components.inventoryitem.owner=inst._rider
local crop=crop('tomato',0,1);crop.components.pickable:MakeEmpty()
local weed=CreateEntity();weed.prefab='weed_tillweed';weed.tags.farm_plant=true
weed.tags.weed=true;weed.tags.weedplantstress=true;weed.weed_def={}
weed.components.pickable={CanBePicked=function()return true end,Pick=function()error('must not pick weeds')end}
local wall=CreateEntity();wall.prefab='wall_stone';wall:AddComponent('workable')
wall.components.workable:SetWorkAction(ACTIONS.HAMMER)
wall.components.workable:SetOnFinishCallback(function()error('must not hammer buildings')end)
assert(not Drive.WorkTile(inst,0,0))
assert(waxed.valid and held.valid and crop.valid and weed.valid and wall.valid)
assert(inst._fuel:value()==800 and inst.components.finiteuses.used==0)
''')

    def test_rotten_giant_uses_its_own_loot(self):
        self.run_lua('''
local v=giant('tomato',0,0,'_rotten')
assert(Drive.WorkTile(inst,0,0) and not v.valid)
assert(count_entities('spoiled_food')==1 and count_entities('tomato')==0)
''')

    def test_failed_pick_stops_without_charging(self):
        for field in ('caninteractwith', 'stuck'):
            with self.subTest(field=field):
                self.setUp()
                self.run_lua('''
local v=crop('tomato',0,0,true)
v.components.pickable.''' + field + ('=false' if field == 'caninteractwith' else '=true') + '''
local worked,reason=Drive.WorkTile(inst,0,0)
assert(not worked and reason=='HARVEST_INCOMPLETE' and v.valid and not inst._working)
assert(inst._fuel:value()==800 and inst.components.finiteuses.used==0)
assert(tool.components.finiteuses:GetUses()==100)
''')

    def test_failed_hammer_preserves_giant_and_can_resume(self):
        self.run_lua('''
local v=crop('tomato',0,0,true)
local base=SpawnPrefab
SpawnPrefab=function(name)
 local e=base(name)
 if name=='tomato_oversized' then
  e.components.workable:SetShouldRecoilFn(function()return true end)
 end
 return e
end
local worked,reason=Drive.WorkTile(inst,0,0)
assert(worked and reason=='HARVEST_INCOMPLETE' and not v.valid and not inst._working)
assert(count_entities('tomato_oversized')==1 and inst._fuel:value()==799)
for _,v in ipairs(ENTITIES)do if v.prefab=='tomato_oversized' then
 v.components.workable:SetShouldRecoilFn(function()return false end)
end end
assert(Drive.WorkTile(inst,0,0) and count_entities('tomato_oversized')==0)
assert(inst._fuel:value()==798 and inst.components.finiteuses.used==2)
''')

    def test_ground_giant_requires_workable_hammer(self):
        self.run_lua('''
local v=giant('tomato');v.components.workable:SetWorkAction(ACTIONS.CHOP)
local worked,reason=Drive.WorkTile(inst,0,0)
assert(not worked and reason=='HARVEST_INCOMPLETE' and v.valid and not inst._working)
assert(inst._fuel:value()==800 and inst.components.finiteuses.used==0)
''')

    def test_hammer_finish_without_removal_is_not_complete_or_repeated_for_free_loot(self):
        self.run_lua('''
local v=giant('tomato');v.components.workable:SetOnFinishCallback(function()end)
local worked,reason=Drive.WorkTile(inst,0,0)
assert(worked and reason=='HARVEST_INCOMPLETE' and v.valid and not inst._working)
assert(not Drive.WorkTile(inst,0,0) and inst._fuel:value()==799)
assert(count_entities('tomato')==0)
''')

    def test_callbacks_cannot_move_next_crop_out_of_tile_and_still_harvest_it(self):
        self.run_lua('''
local first=crop('tomato');local next=crop('carrot',1,0,true)
first.components.pickable.onpickedfn=function()next.Transform:SetPosition(4,0,0)end
assert(Drive.WorkTile(inst,0,0) and next.valid)
assert(count_entities('carrot_oversized')==0)
''')

    def test_missing_fuel_or_driver_does_not_pick_or_hammer(self):
        self.run_lua('''
local plant=crop('tomato',0,0,true);local v=giant('carrot',1,0)
local worked,reason,ready=Farm.Harvest(0,0,0,nil)
assert(not worked and reason=='NO_WORKER' and not ready and plant.valid and v.valid)
inst._fuel:set(0)
worked,reason=Drive.WorkTile(inst,0,0)
assert(not worked and reason=='NO_FUEL' and plant.valid and v.valid)
assert(inst.components.finiteuses.used==0)
''')

    def test_last_use_finishes_whole_tile_then_breaks_and_replacement_resumes(self):
        self.run_lua('''
tool.components.finiteuses:SetUses(1)
local a=crop('tomato',-1,0);local b=crop('carrot',1,0,true)
local next=crop('pumpkin',4,0,true)
local worked,reason=Drive.WorkTile(inst,0,0)
assert(worked and reason=='BROKEN_HARVESTER' and not inst._working)
assert(not a.valid and not b.valid and count_entities('carrot_oversized')==0)
assert(tool:IsValid() and tool.components.finiteuses:GetUses()==0 and next.valid)
assert(string.find(require('aom_work_status').Describe(inst),'收割机已损坏'))
worked,reason=Drive.WorkTile(inst,4,0)
assert(not worked and reason=='NO_ATTACHMENT' and next.valid)
assert(inst._fuel:value()==799 and inst.components.finiteuses.used==1)
assert(not require('aom_harvester_tool').Repair(inst))
tool=SpawnPrefab('aom_harvester');inst.components.container.slots[1]=tool;inst._attachment_type='harvester'
Drive.SetWorking(inst,true)
assert(Drive.WorkTile(inst,4,0) and not next.valid)
assert(tool.components.finiteuses:GetUses()==99 and inst._fuel:value()==798)
''')

    def test_empty_field_and_repeated_pass_do_not_consume_durability(self):
        self.run_lua('''
assert(not Drive.WorkTile(inst,0,0))
assert(tool.components.finiteuses:GetUses()==100 and inst._fuel:value()==800)
crop('tomato');assert(Drive.WorkTile(inst,0,0))
assert(not Drive.WorkTile(inst,0,0))
assert(tool.components.finiteuses:GetUses()==99 and inst._fuel:value()==799)
''')

    def test_partial_work_consumes_one_use_and_zero_use_retry_cannot_work(self):
        self.run_lua('''
tool.components.finiteuses:SetUses(1)
local first=crop('tomato');local next=crop('carrot',1,0)
next.components.pickable.stuck=true
local worked,reason=Drive.WorkTile(inst,0,0)
assert(worked and reason=='BROKEN_HARVESTER' and not inst._working)
assert(not first.valid and next.valid and tool.components.finiteuses:GetUses()==0)
assert(inst._fuel:value()==799 and inst.components.finiteuses.used==1)
next.components.pickable.stuck=false
worked,reason=Drive.WorkTile(inst,0,0)
assert(not worked and reason=='NO_ATTACHMENT' and next.valid)
assert(inst._fuel:value()==799 and inst.components.finiteuses.used==1)
''')

    def test_native_save_load_retains_full_used_and_depleted_durability(self):
        self.run_lua('''
for _,remaining in ipairs({40,17,0})do
 ENTITIES={}
 tool.components.finiteuses:SetUses(remaining)
 local data=tool.components.finiteuses:OnSave()
 local restored=SpawnPrefab('aom_harvester')
 if data then restored.components.finiteuses:OnLoad(data)end
 assert(restored.components.finiteuses:GetUses()==remaining)
 inst.components.container.slots[1]=restored
 local plant=crop('tomato')
 local worked,reason=Drive.WorkTile(inst,0,0)
 if remaining==0 then
  assert(not worked and reason=='BROKEN_HARVESTER' and plant.valid and restored:IsValid())
 else
  assert(worked and not plant.valid and restored.components.finiteuses:GetUses()==remaining-1)
 end
end
''')

    def test_movement_stops_before_later_tiles_when_attachment_runs_out(self):
        self.run_lua('''
tool.components.finiteuses:SetUses(1)
local here=crop('tomato');local next=crop('carrot',4,0,true)
Drive.SetWorking(inst,true)
inst.x=8;Drive.TrackMovement(inst)
assert(not here.valid and next.valid and count_entities('carrot_oversized')==0)
assert(not inst._working and tool.components.finiteuses:GetUses()==0)
assert(inst._fuel:value()==799 and inst.components.finiteuses.used==1)
''')


if __name__ == '__main__':
    unittest.main()
