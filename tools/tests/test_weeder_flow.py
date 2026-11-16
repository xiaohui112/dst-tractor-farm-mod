"""除草机安全与结算：执行真实挂件、原版 Workable/FiniteUses 和园艺残渣掉落。"""
from pathlib import Path
import unittest
from test_giant_farming import World

ROOT = Path(__file__).resolve().parents[2]


class WeederFlowTests(unittest.TestCase):
    def setUp(self):
        self.w = World()
        self.w.lua.globals().REF = str(ROOT / 'tools/api-ref')
        self.w.lua.execute((ROOT / 'tools/tests/landclearer_engine.lua').read_text())
        self.w.lua.execute('''
inst=make_flow_inst({},'autumn')
tool=SpawnPrefab('aom_weeder')
inst.components.container.slots[1]=tool
inst._attachment_type='weeder'
inst._working=true
function inst:DoPeriodicTask()return {Cancel=function()end}end
function weed(name,x,z)
 local v=CreateEntity();v.prefab=name or 'weed_tillweed'
 if string.sub(v.prefab,1,5)=='weed_' then
  v.tags.farm_plant=true;v.tags.weed=true;v.tags.weedplantstress=true;v.weed_def={}
 end
 v.Transform:SetPosition(x or 0,0,z or 0)
 v:AddComponent('workable')
 v.components.workable:SetWorkAction(ACTIONS.DIG)
 v.components.workable:SetWorkLeft(2)
 v.components.workable:SetOnFinishCallback(function(target)target:Remove()end)
 return v
end
function assert_cost(n)
 assert(inst._fuel:value()==800-n)
 assert(inst.components.finiteuses.used==n)
 assert(tool.components.finiteuses:GetUses()==100-n)
end
''')

    def run_lua(self, source):
        self.w.lua.execute(source)

    def test_all_weed_names_and_native_debris_clear_once_preserving_crops_and_mounds(self):
        self.run_lua('''
for i,name in ipairs({'weed_forgetmelots','weed_firenettle','weed_tillweed','weed_ivy'})do
 weed(name,-1.5+(i-1),1.8)
end
local d=SpawnPrefab('farm_soil_debris');d.Transform:SetPosition(1.99,0,1.99)
local neighbor=weed('weed_tillweed',2.01,0)
local crop=weed('farm_plant_tomato');crop.tags.farm_plant=true
local grass=weed('grass');local berry=weed('berrybush')
local soil=SpawnPrefab('farm_soil');soil.Transform:SetPosition(.3,0,.4)
local worked,reason=Drive.WorkTile(inst,0,0)
assert(worked and reason==nil and not d.valid and neighbor.valid)
assert(crop.valid and grass.valid and berry.valid and soil.valid)
assert(soil.x==.3 and soil.z==.4 and TILE_WRITES==0)
assert(count_trace('loot_roll')==1 and count_entities('flint')==1)
assert_cost(1)
assert(not Drive.WorkTile(inst,0,0));assert_cost(1)
''')

    def test_continuous_driving_passes_empty_tile_and_weeds_next_tile(self):
        self.run_lua('''
local first=weed('weed_tillweed',0,0);local next=weed('weed_firenettle',8,0)
Drive.SetWorking(inst,true);Drive.TrackMovement(inst)
assert(not first.valid and next.valid and inst._working);assert_cost(1)
for i=1,10 do Drive.TrackMovement(inst)end
inst.x=8;Drive.TrackMovement(inst)
assert(not next.valid and inst._working);assert_cost(2)
Drive.SetWorking(inst,false);assert(not inst._working and not inst._worktask)
''')

    def test_empty_field_is_free(self):
        self.run_lua("assert(not Drive.WorkTile(inst,0,0));assert_cost(0);assert(inst._working)")

    def test_non_dig_target_blocks_whole_batch_without_work_or_cost(self):
        self.run_lua('''
local good=weed();local bad=weed('weed_custom',1,0)
bad.components.workable:SetWorkAction(ACTIONS.CHOP)
local changed,reason=Drive.WorkTile(inst,0,0)
assert(not changed and reason=='UNCLEARABLE_WEED' and not inst._working)
assert(good.valid and bad.valid and good.components.workable:GetWorkLeft()==2)
assert_cost(0)
''')

    def test_disabled_or_missing_workable_is_never_called(self):
        for missing in (False, True):
            with self.subTest(missing=missing):
                self.setUp()
                self.run_lua('''
local v=weed()
''' + ("v.components.workable=nil" if missing else "v.components.workable:SetWorkable(false)") + '''
local changed,reason=Drive.WorkTile(inst,0,0)
assert(not changed and reason=='UNCLEARABLE_WEED' and v.valid and not inst._working)
assert_cost(0)
''')

    def test_tagged_mod_weed_with_dig_is_supported(self):
        self.run_lua('''
local v=weed('custom_garden_weed');v.tags.weed=true
assert(Drive.WorkTile(inst,0,0) and not v.valid);assert_cost(1)
''')

    def test_crop_protection_overrides_weed_tag_and_prefix(self):
        self.run_lua('''
local tagged=weed('farm_plant_tomato');tagged.tags.farm_plant=true;tagged.tags.weed=true
local stressed=weed('weed_custom_crop');stressed.components.farmplantstress={}
local debris_named=weed('farm_soil_debris');debris_named.tags.farm_plant=true
assert(not Farm.IsClearableDebris(tagged) and not Farm.IsClearableDebris(stressed))
assert(not Drive.WorkTile(inst,0,0));assert_cost(0)
assert(tagged.valid and stressed.valid and debris_named.valid and inst._working)
local good=weed();assert(Drive.WorkTile(inst,0,0))
assert(not good.valid and tagged.valid and stressed.valid and debris_named.valid);assert_cost(1)
''')

    def test_targets_are_revalidated_after_previous_callback(self):
        self.run_lua('''
local first=weed();local crop=weed('weed_future_crop',1,0)
local moved=weed('weed_moved',0,1)
first.components.workable:SetOnFinishCallback(function(v)
 crop.components.farmplantstress={};moved.Transform:SetPosition(4,0,0);v:Remove()
end)
assert(Drive.WorkTile(inst,0,0))
assert(crop.valid and moved.valid and crop.components.workable:GetWorkLeft()==2)
assert(moved.components.workable:GetWorkLeft()==2);assert_cost(1)
''')

    def test_ambiguous_mod_crop_is_protected_without_native_weed_identity(self):
        self.run_lua('''
local v=weed('modded_crop');v.tags.farm_plant=true;v.tags.weed=true
assert(not Farm.IsClearableDebris(v))
assert(not Drive.WorkTile(inst,0,0) and v.valid);assert_cost(0)
''')

    def test_action_changed_by_callback_stops_with_actual_partial_cost(self):
        self.run_lua('''
local first=weed();local next=weed('weed_next',1,0)
first.components.workable:SetOnFinishCallback(function(v)
 next.components.workable:SetWorkAction(ACTIONS.CHOP);v:Remove()
end)
local changed,reason=Drive.WorkTile(inst,0,0)
assert(changed and reason=='UNCLEARABLE_WEED' and not inst._working)
assert(next.valid and next.components.workable:GetWorkLeft()==2);assert_cost(1)
''')

    def test_no_progress_is_failure_and_free(self):
        self.run_lua('''
local v=weed();v.components.workable:SetShouldRecoilFn(function()return true end)
local changed,reason=Drive.WorkTile(inst,0,0)
assert(not changed and reason=='WEEDING_INCOMPLETE' and not inst._working)
assert(v.valid and v.components.workable:GetWorkLeft()==2);assert_cost(0)
assert(string.find(require('aom_work_status').Describe(inst),'除草'))
''')

    def test_partial_progress_stops_charges_once_and_can_resume(self):
        self.run_lua('''
local v=weed();v.components.workable:SetWorkMultiplierFn(function()return .5 end)
local changed,reason=Drive.WorkTile(inst,0,0)
assert(changed and reason=='WEEDING_INCOMPLETE' and not inst._working and v.valid)
assert(v.components.workable:GetWorkLeft()==1);assert_cost(1)
v.components.workable:SetWorkMultiplierFn(function()return 1 end)
Drive.SetWorking(inst,true)
assert(Drive.WorkTile(inst,0,0) and not v.valid);assert_cost(2)
''')

    def test_finish_callback_that_leaves_debris_is_not_success(self):
        self.run_lua('''
local v=SpawnPrefab('farm_soil_debris')
v.components.workable:SetOnFinishCallback(function()end)
local changed,reason=Drive.WorkTile(inst,0,0)
assert(changed and reason=='WEEDING_INCOMPLETE' and not inst._working and v.valid)
assert_cost(1)
local again=Drive.WorkTile(inst,0,0)
assert(not again);assert_cost(1)
''')

    def test_final_scan_detects_new_weed_created_by_callback(self):
        self.run_lua('''
local v=weed();local new
v.components.workable:SetOnFinishCallback(function(target)new=weed('weed_new',1,0);target:Remove()end)
local changed,reason=Drive.WorkTile(inst,0,0)
assert(changed and reason=='WEEDING_INCOMPLETE' and not inst._working and new.valid)
assert_cost(1)
''')

    def test_missing_driver_and_fuel_have_no_side_effects(self):
        self.run_lua('''
local v=weed()
local changed,reason,ready=Farm.Weed(0,0,0,nil)
assert(not changed and reason=='NO_WORKER' and ready==false and v.valid);assert_cost(0)
inst._fuel:set(0)
changed,reason=Drive.WorkTile(inst,0,0)
assert(not changed and reason=='NO_FUEL' and not inst._working and v.valid)
assert(tool.components.finiteuses:GetUses()==100 and inst.components.finiteuses.used==0)
''')

    def test_last_use_breaks_and_replacement_can_resume(self):
        self.run_lua('''
local v=weed();tool.components.finiteuses:SetUses(1)
local changed,reason=Drive.WorkTile(inst,0,0)
assert(changed and reason=='BROKEN_WEEDER' and not inst._working)
assert(not v.valid and tool:IsValid() and tool.components.finiteuses:GetUses()==0)
assert(inst.components.container:GetItemInSlot(1)==nil and inst._attachment_type==nil)
local next=weed('weed_tillweed',4,0)
assert(not Drive.WorkTile(inst,4,0) and next.valid and inst._fuel:value()==799)
local repair=require('aom_weeder_tool')
assert(not repair.Repair(inst))
tool=SpawnPrefab('aom_weeder');inst.components.container.slots[1]=tool;inst._attachment_type='weeder'
assert(Drive.WorkTile(inst,4,0) and not next.valid and tool.components.finiteuses:GetUses()==99)
tool.components.finiteuses:SetUses(99)
assert(repair.Repair(inst) and tool.components.finiteuses:GetUses()==100)
assert(not repair.Repair(inst))
''')

    def test_used_and_depleted_durability_survive_native_save_load(self):
        self.run_lua('''
for _,remaining in ipairs({37,0})do
 tool.components.finiteuses:SetUses(remaining)
 local data=tool.components.finiteuses:OnSave()
 local loaded=SpawnPrefab('aom_weeder');loaded.components.finiteuses:OnLoad(data)
 assert(loaded.components.finiteuses:GetUses()==remaining)
 inst.components.container.slots[1]=loaded
 local v=weed();local changed=Drive.WorkTile(inst,0,0)
 if remaining==0 then assert(not changed and v.valid)
 else assert(changed and not v.valid and loaded.components.finiteuses:GetUses()==36)end
end
''')

    def test_parking_is_free_and_toggle_retries_current_tile(self):
        self.run_lua('''
local v=weed();Drive.SetWorking(inst,true);Drive.TrackMovement(inst)
assert(not v.valid);assert_cost(1)
local later=weed()
for i=1,20 do Drive.TrackMovement(inst)end
assert(later.valid);assert_cost(1)
Drive.SetWorking(inst,false);Drive.SetWorking(inst,true);Drive.TrackMovement(inst)
assert(not later.valid);assert_cost(2)
''')


if __name__ == '__main__':
    unittest.main()
