"""行驶整格作业、物料结算、路径和负载反馈；执行真实农业模块，地图为桩。"""
import unittest
from test_giant_farming import World, as_dict


class DrivePassTests(unittest.TestCase):
    def setUp(self):
        self.w=World()
        self.w.lua.execute('''
Profile=require('aom_work_profile')
function start_driver(inst)
 inst._rider={Transform=inst.Transform,components={},PushEvent=function()end}
 inst.Transform.GetRotation=function()return 0 end
 function inst:DoPeriodicTask(period,fn)
  self.task={fn=fn,Cancel=function(self)self.cancelled=true end};return self.task
 end
 Drive.SetWorking(inst,true)
end
function smoke_count()
 local n=0;for _,v in ipairs(ENTITIES)do if v.prefab=='aom_exhaust_puff' then n=n+1 end end;return n
end
''')

    def make(self, counts=None, season='autumn'):
        inst=self.w.make(counts or {},season)
        self.w.lua.globals().inst=inst
        return inst

    def run_lua(self, source):
        self.w.lua.execute(source)

    def test_normal_seeding_finishes_whole_tile_without_waiting(self):
        self.make({'tomato':9})
        self.run_lua('''
inst._seed_strategy='SEQUENTIAL'
assert(Drive.WorkTile(inst,0,0))
inst._attachment_type='seeder';start_driver(inst)
Drive.TrackMovement(inst)
assert(crop_count()==9 and inst.components.aom_attachment_store:GetSeedCount()==0)
assert(inst._fuel:value()==790) -- 一次整格犁地 + 九次原版播种。
for i=1,20 do Drive.TrackMovement(inst)end
assert(crop_count()==9 and inst._fuel:value()==790 and inst._working)
''')

    def test_crossed_tiles_are_not_skipped_between_samples(self):
        self.make({'tomato':27})
        self.run_lua('''
inst._seed_strategy='SEQUENTIAL'
for x=0,8,4 do Drive.WorkTile(inst,x,0)end
inst._attachment_type='seeder';start_driver(inst);Drive.TrackMovement(inst)
inst.x=8;Drive.TrackMovement(inst)
assert(crop_count()==27 and inst._fuel:value()==770)
''')

    def test_short_seed_stock_stops_with_partial_progress_and_can_resume(self):
        self.make({'tomato':3})
        self.run_lua('''
inst._seed_strategy='SEQUENTIAL';Drive.WorkTile(inst,0,0)
inst._attachment_type='seeder';start_driver(inst);Drive.TrackMovement(inst)
assert(crop_count()==3 and not inst._working)
assert(inst.components.aom_attachment_store:GetSeedCount()==0 and inst._fuel:value()==796)
inst.components.aom_attachment_store.container:GiveItem(make_seed('tomato',6))
start_driver(inst);Drive.TrackMovement(inst)
assert(crop_count()==9 and inst._fuel:value()==790)
''')

    def test_failed_seed_is_returned_and_movement_work_stops(self):
        self.make({'tomato':9})
        self.run_lua('''
inst._seed_strategy='SEQUENTIAL';Drive.WorkTile(inst,0,0)
inst._attachment_type='seeder';start_driver(inst);PLANT_FAIL=true
Drive.TrackMovement(inst)
assert(crop_count()==0 and not inst._working)
assert(inst.components.aom_attachment_store:GetSeedCount()==9 and inst._fuel:value()==799)
''')

    def test_batch_stops_at_fuel_budget_without_free_seeds(self):
        self.make({'tomato':9})
        self.run_lua('''
inst._seed_strategy='SEQUENTIAL';Drive.WorkTile(inst,0,0)
inst._fuel:set(3);inst._attachment_type='seeder';start_driver(inst);Drive.TrackMovement(inst)
assert(crop_count()==3 and inst._fuel:value()==0 and not inst._working)
assert(inst.components.aom_attachment_store:GetSeedCount()==6)
''')

    def test_water_pass_fills_whole_tile_and_parking_never_drains(self):
        # 完整原版水分管理器流程由 test_irrigator_flow 覆盖；此处复用它验证驾驶采样。
        from pathlib import Path
        root=Path(__file__).resolve().parents[2]
        self.w.lua.globals().REF=str(root/'tools/api-ref')
        self.w.lua.globals().TESTS=str(root/'tools/tests')
        self.w.lua.execute((root/'tools/tests/irrigator_engine.lua').read_text())
        self.run_lua('''
fill(10);start_water();Drive.TrackMovement(inst)
for i=1,30 do Drive.TrackMovement(inst)end
assert(water_count()==6 and moisture(0,0)==100 and inst._fuel:value()==799)
inst.x=4;Drive.TrackMovement(inst)
assert(water_count()==2 and moisture(4,0)==100)
inst.x=0;Drive.TrackMovement(inst)
assert(water_count()==2 and inst._fuel:value()==798)
''')

    def test_fertilizer_is_one_item_per_pass(self):
        self.make()
        self.run_lua('''
local c=inst.components.aom_attachment_store.container
local n=0
TheWorld.components.farming_manager.AddTileNutrients=function()n=n+1 end
local function fertilizer()
 local item={valid=true,components={}}
 function item:IsValid()return self.valid end
 function item:Remove()self.valid=false end
 item.components.fertilizer={nutrients={0,8,0},OnApplied=function()item:Remove()end}
 return item
end
c.slots[2]=fertilizer();c.slots[3]=fertilizer()
inst._attachment_type='fertilizer';start_driver(inst);Drive.TrackMovement(inst)
for i=1,20 do Drive.TrackMovement(inst)end
assert(n==1 and inst.components.aom_attachment_store:GetFertilizerCount()==1)
inst.x=4;Drive.TrackMovement(inst)
assert(n==2 and inst.components.aom_attachment_store:GetFertilizerCount()==0)
''')

    def test_giant_plan_finishes_current_tile_and_keeps_reserved_space(self):
        w=self.w;c=w.combo('autumn-01-01');inst=self.make(as_dict(c.ratio))
        w.bind(inst,c);w.prepare(inst)
        self.run_lua('''
inst.x=0;inst.z=0;inst._attachment_type='seeder';start_driver(inst)
Drive.TrackMovement(inst)
assert(inst._block.done==8 and crop_count()==8)
for i=1,10 do Drive.TrackMovement(inst)end
assert(inst._block.done==8 and crop_count()==8)
''')

    def test_all_giant_layouts_finish_with_one_pass_per_planned_tile(self):
        w=self.w
        for season,combos in w.block.BLOCKS.items():
            for _,combo in combos.items():
                if combo.reference_only:continue
                with self.subTest(layout=combo.id):
                    w.lua.globals().reset_world()
                    inst=self.make(as_dict(combo.ratio),season);w.bind(inst,combo)
                    _,tiles=w.block.WorldSlots(inst._block)
                    for _,tile in tiles.items():
                        self.assertTrue(w.drive.WorkTile(inst,tile.x,tile.z))
                    inst._attachment_type='seeder'
                    for _,tile in tiles.items():
                        result=w.drive.WorkTile(inst,tile.x,tile.z)
                        self.assertTrue(result[0] if isinstance(result,tuple) else result)
                    self.assertEqual(inst._block.done,combo.total)

    def test_grid_trace_handles_diagonal_reverse_and_teleport(self):
        self.run_lua('''
local map=TheWorld.Map
local t=Profile.TraceTiles(map,0,0,8,8)
assert(#t==3 and t[2].x==4 and t[2].z==4 and t[3].x==8)
t=Profile.TraceTiles(map,8,0,-4,0)
assert(#t==4 and t[2].x==4 and t[3].x==0 and t[4].x==-4)
t=Profile.TraceTiles(map,2,0,1.9,0)
assert(#t==2 and t[1].x==4 and t[2].x==0)
t=Profile.TraceTiles(map,0,0,100,0)
assert(#t==1 and t[1].x==100)
''')

    def test_entire_tile_weeding_and_harvesting_do_not_touch_neighbor(self):
        self.make()
        self.run_lua('''
local weed=SpawnPrefab('weed_tillweed');weed.Transform:SetPosition(1.8,0,1.8)
local neighbor=SpawnPrefab('weed_tillweed');neighbor.Transform:SetPosition(2.1,0,0)
for _,v in ipairs({weed,neighbor})do
 local left=2
 v.components.workable={GetWorkLeft=function()return left end,
 WorkedBy=function(_,doer,n)left=left-n;if left==0 then v:Remove()end end}
end
assert(Farm.Weed(0,0,0,nil));assert(not weed.valid and neighbor.valid)
local plant=SpawnPrefab('farm_plant_tomato');plant.Transform:SetPosition(1.8,0,1.8)
local nextplant=SpawnPrefab('farm_plant_tomato');nextplant.Transform:SetPosition(2.1,0,0)
for _,v in ipairs({plant,nextplant})do
 v.components.pickable={CanBePicked=function()return true end,Pick=function()v:Remove()end}
end
assert(Farm.Harvest(0,0,0,nil));assert(not plant.valid and nextplant.valid)
''')

    def test_exhaust_requires_moving_plough_load_and_stops_when_parked(self):
        self.make()
        self.run_lua('''
inst._seed_strategy='SEQUENTIAL';start_driver(inst);Drive.TrackMovement(inst)
for i=1,6 do inst.x=i*.1;Drive.TrackMovement(inst)end
assert(smoke_count()==2)
for i=1,20 do Drive.TrackMovement(inst)end
assert(smoke_count()==2)
Drive.SetWorking(inst,false);inst.x=1;Drive.TrackMovement(inst);assert(smoke_count()==2)
start_driver(inst);Drive.TrackMovement(inst) -- 已完成的农田没有负载。
for i=1,6 do inst.x=1+i*.1;Drive.TrackMovement(inst)end
assert(smoke_count()==2)
''')

    def test_speed_order_matches_requested_work_groups(self):
        self.run_lua('''
assert(Profile.Speed('plow',true)<Profile.Speed('weeder',true))
assert(Profile.Speed('weeder',true)==Profile.Speed('harvester',true))
assert(Profile.Speed('weeder',true)<Profile.Speed('seeder',true))
assert(Profile.Speed('seeder',true)<Profile.Speed('irrigator',true))
assert(Profile.Speed('irrigator',true)<=Profile.Speed('fertilizer',true))
for attachment in pairs(Profile.REFERENCE_MPH)do assert(Profile.Speed(attachment,false)==6)end
''')


if __name__=='__main__':unittest.main()
