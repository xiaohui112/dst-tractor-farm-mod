"""开垦完整流程：实际执行原版杂物 prefab / Workable / Terraformer / FiniteUses。"""
from pathlib import Path
import unittest
from test_giant_farming import World, as_dict

ROOT=Path(__file__).resolve().parents[2]


class LandClearerFlowTests(unittest.TestCase):
    def setUp(self):
        self.w=World()
        self.w.lua.globals().REF=str(ROOT/'tools/api-ref')
        self.w.lua.execute((ROOT/'tools/tests/landclearer_engine.lua').read_text())
        self.w.lua.execute("inst=make_flow_inst({},'autumn');tool=inst.components.container:GetItemInSlot(1)")

    def run_lua(self,source):
        self.w.lua.execute(source)

    def test_new_land_full_sequence_uses_native_loot_before_mounds(self):
        self.run_lua('''
TILES[tkey(0,0)]=0
local restore=force_debris(4,{.1,.1,.9,.1,.1,.9,.9,.9})
inst._working=true
local worked=Drive.WorkTile(inst,0,0);restore()
assert(worked and Farm.IsFieldReady(0,0,0))
assert(TILE_WRITES==1 and TURF_DROPS==0)
assert(count_trace('debris')==4 and count_entities('farm_soil_debris')==0)
assert(count_trace('loot_roll')==4 and count_entities('flint')==4)
assert(count_entities('farm_soil')==9)
assert(inst._fuel:value()==799 and tool.components.finiteuses:GetUses()==59)
assert(inst.components.finiteuses.used==1)
local first_mound,last_roll
for i,event in ipairs(TRACE)do
 if event=='mound' and not first_mound then first_mound=i end
 if event=='loot_roll' then last_roll=i end
end
assert(TRACE[1]=='tile' and last_roll<first_mound)
''')

    def test_continuous_driving_prepares_next_tile_with_no_material_stock(self):
        self.run_lua('''
function inst:DoPeriodicTask(_,fn)return {fn=fn,Cancel=function(self)self.cancelled=true end}end
Drive.SetWorking(inst,true);local task=inst._worktask
task.fn(inst);assert(Farm.IsFieldReady(0,0,0) and inst._working)
for i=1,10 do task.fn(inst)end
assert(inst._fuel:value()==799 and tool.components.finiteuses:GetUses()==59)
inst.x=8;task.fn(inst)
assert(Farm.IsFieldReady(4,0,0) and Farm.IsFieldReady(8,0,0))
assert(inst._working and inst._worktask==task and not task.cancelled)
assert(inst._fuel:value()==797 and tool.components.finiteuses:GetUses()==57)
Drive.SetWorking(inst,false);assert(task.cancelled and not inst._worktask)
''')

    def test_standard_grid_survives_native_neighbor_collapse_on_three_adjacent_tiles(self):
        self.run_lua('''
local native=dofile(REF..'/till_map.lua')
function GetFarmTillSpacing()return 1.25 end
TheWorld.Map.CollapseSoilAtPoint=native.CollapseSoilAtPoint
local original_spawn=SpawnPrefab
function SpawnPrefab(name)
 local soil=original_spawn(name)
 if name=='farm_soil' then
  function soil:GetDistanceSqToPoint(x,y,z)return (self.x-x)^2+(self.z-z)^2 end
  function soil:PushEvent(event)
   if event=='breaksoil' then self:AddTag('NOBLOCK');self:AddTag('NOCLICK')
   elseif event=='collapsesoil' then self:RemoveTag('soil') end
  end
 end
 return soil
end
for x=0,8,4 do
 assert(Drive.WorkTile(inst,x,0))
 for done=0,x,4 do assert(Farm.IsFieldReady(done,0,0))end
end
assert(count_entities('farm_soil')==27)
for _,soil in ipairs(ENTITIES)do
 if soil.valid and soil.prefab=='farm_soil' then assert(not soil:HasTag('NOBLOCK') and not soil:HasTag('NOCLICK'))end
end
assert(not Drive.WorkTile(inst,0,0) and count_entities('farm_soil')==27)
''')

    def test_native_loot_chance_is_not_replaced_by_guaranteed_drops(self):
        self.run_lua('''
LUCK=false;TILES[tkey(0,0)]=0
local restore=force_debris(2,{.1,.1,.9,.9})
assert(Drive.WorkTile(inst,0,0));restore()
assert(count_trace('loot_roll')==2 and count_entities('flint')==0)
assert(Farm.IsFieldReady(0,0,0))
''')

    def test_all_203_grid_layouts_use_new_land_generation_cleanup_and_nine_mounds(self):
        w=self.w;total=0
        for season,combos in w.block.BLOCKS.items():
            for _,combo in combos.items():
                if not w.lua.eval("require('aom_auto_seeding').IsGrid")(combo):continue
                total+=1
                with self.subTest(layout=combo.id):
                    self.run_lua('ENTITIES={};TILES={};TRACE={};TILE_WRITES=0')
                    inst=w.lua.globals().make_flow_inst(w.lua.table_from(as_dict(combo.ratio)),season)
                    inst._seed_strategy='GIANT';w.bind(inst,combo);w.lua.globals().inst=inst
                    _,tiles=w.block.WorldSlots(inst._block)
                    for _,tile in tiles.items():
                        w.lua.globals().TheWorld.Map.SetTile(w.lua.globals().TheWorld.Map,tile.x/4,tile.z/4,0)
                    for _,tile in tiles.items():
                        result=w.drive.WorkTile(inst,tile.x,tile.z)
                        self.assertTrue(result[0] if isinstance(result,tuple) else result)
                    self.assertEqual(w.lua.globals().count_entities('farm_soil_debris'),0)
                    self.assertEqual(w.lua.globals().count_entities('farm_soil'),9*combo.width*combo.height)
                    w.lua.globals().set_flow_attachment(inst,'seeder')
                    for _,tile in tiles.items():
                        result=w.drive.WorkTile(inst,tile.x,tile.z)
                        self.assertTrue(result[0] if isinstance(result,tuple) else result)
                    self.assertEqual(inst._block.done,combo.total)
        self.assertEqual(total,203)

    def test_random_attempts_and_spacing_match_original_callback(self):
        self.run_lua('''
VecUtil_DistSq=function(x,z,a,b)return (x-a)^2+(z-b)^2 end
Finished=function()end
local original=dofile(REF..'/farm_plow_debris.lua')
local function positions()
 local out={}
 for _,v in ipairs(ENTITIES)do if v.prefab=='farm_soil_debris' then
  local x,_,z=v.Transform:GetWorldPosition();out[#out+1]=string.format('%.9f:%.9f',x,z)
 end end
 return table.concat(out,'|')
end
for seed=1,100 do
 ENTITIES={};math.randomseed(seed);original({},Vector3(0,0,0))
 local expected=positions()
 ENTITIES={};math.randomseed(seed);Farm.SpawnPloughDebris({},Vector3(0,0,0))
 assert(positions()==expected,'spawn rules differ at seed '..seed)
end
''')

    def test_colliding_attempts_are_skipped_without_forcing_two_drops(self):
        self.run_lua('''
TILES[tkey(0,0)]=0
local restore=force_debris(4,{.5,.5})
assert(Drive.WorkTile(inst,0,0));restore()
assert(count_trace('debris')==1 and count_trace('loot_roll')==1)
assert(Farm.IsFieldReady(0,0,0))
''')

    def test_repeated_pass_does_not_regenerate_debris_or_charge_again(self):
        self.run_lua('''
TILES[tkey(0,0)]=0
assert(Drive.WorkTile(inst,0,0))
local spawned=count_trace('debris');local loot=count_trace('loot_roll')
for i=1,5 do assert(not Drive.WorkTile(inst,0,0))end
assert(TILE_WRITES==1 and count_trace('debris')==spawned and count_trace('loot_roll')==loot)
assert(inst._fuel:value()==799 and tool.components.finiteuses:GetUses()==59)
''')

    def test_existing_farm_clears_corner_debris_without_generating_more(self):
        self.run_lua('''
local d=SpawnPrefab('farm_soil_debris');d.Transform:SetPosition(1.99,0,1.99)
assert(Farm.CanWorkAt('plow',0,0,0))
assert(Drive.WorkTile(inst,0,0))
assert(not d.valid and TILE_WRITES==0 and count_trace('debris')==1)
assert(count_entities('flint')==1 and Farm.IsFieldReady(0,0,0))
''')

    def test_offset_handmade_mounds_are_recognized_and_rearranged(self):
        self.run_lua('''
for x=-1,1 do for z=-1,1 do SpawnPrefab('farm_soil').Transform:SetPosition(x+.15,0,z)end end
assert(not Farm.IsFieldReady(0,0,0) and Farm.CanWorkAt('plow',0,0,0))
assert(Drive.WorkTile(inst,0,0))
assert(Farm.IsFieldReady(0,0,0) and count_entities('farm_soil')==9)
assert(TILE_WRITES==0 and count_trace('debris')==0)
''')

    def test_crop_blocks_before_terraforming_or_deleting_player_mounds(self):
        self.run_lua('''
TILES[tkey(0,0)]=0
local crop=SpawnPrefab('farm_plant_tomato');crop.Transform:SetPosition(0,0,0)
local soil=SpawnPrefab('farm_soil');soil.Transform:SetPosition(.2,0,1.5)
inst._working=true
local worked,reason=Drive.WorkTile(inst,0,0)
assert(not worked and reason=='PROTECTED_CROP' and inst._working)
assert(crop.valid and soil.valid and TILE_WRITES==0 and count_trace('debris')==0)
assert(inst._fuel:value()==800 and tool.components.finiteuses:GetUses()==60)
''')

    def test_extra_duplicate_mound_is_removed_and_field_becomes_ready(self):
        self.run_lua('''
assert(Drive.WorkTile(inst,0,0))
local duplicate=SpawnPrefab('farm_soil');duplicate.Transform:SetPosition(0,0,0)
assert(not Farm.IsFieldReady(0,0,0) and Farm.CanWorkAt('plow',0,0,0))
assert(Drive.WorkTile(inst,0,0))
assert(not duplicate.valid and Farm.IsFieldReady(0,0,0) and count_entities('farm_soil')==9)
''')

    def test_building_and_non_dig_weeds_are_preserved(self):
        self.run_lua('''
local wall=SpawnPrefab('wall_stone');wall.components.inventoryitem=nil;wall.tags.NOBLOCK=nil
wall.tags.structure=true;wall.Transform:SetPosition(1.5,0,1.5)
local changed,why,ready=Farm.Plough(0,0,0,inst._rider,Farm.GetTerraformer(inst))
assert(not changed and why=='BLOCKED_MOUND' and not ready and wall.valid)
wall:Remove()
local weed=SpawnPrefab('weed_ivy');weed.tags.weed=true
weed.components.workable=dofile(REF..'/workable.lua')(weed)
weed.components.workable:SetWorkAction(ACTIONS.CHOP)
local ok,reason=Drive.WorkTile(inst,0,0)
assert(ok and reason=='BLOCKED_MOUND' and weed.valid)
assert(count_entities('farm_soil')==8 and inst._fuel:value()==799)
''')

    def test_cleanup_failure_preserves_old_layout_and_reports_partial_work(self):
        self.run_lua('''
local soil=SpawnPrefab('farm_soil');soil.Transform:SetPosition(.15,0,.15)
local d=SpawnPrefab('farm_soil_debris');d.Transform:SetPosition(1.8,0,1.8)
d.components.workable:SetOnFinishCallback(function()end) -- 模拟其他Mod不移除杂物。
inst._working=true
local changed,reason=Drive.WorkTile(inst,0,0)
assert(changed and reason=='CLEARING_INCOMPLETE' and not inst._working)
assert(soil.valid and count_entities('farm_soil')==1 and d.valid)
assert(inst._fuel:value()==799 and tool.components.finiteuses:GetUses()==59)
assert(count_trace('loot_roll')==0)
''')

    def test_partial_tilling_is_not_complete_and_retry_does_not_respawn_debris(self):
        self.run_lua('''
TILES[tkey(0,0)]=0
local original=TheWorld.Map.CanTillSoilAtPoint
TheWorld.Map.CanTillSoilAtPoint=function(self,x,y,z)
 if x==0 and z==0 then return false end
 return original(self,x,y,z)
end
inst._working=true
local changed,reason=Drive.WorkTile(inst,0,0)
assert(changed and reason=='BLOCKED_MOUND' and inst._working)
assert(count_entities('farm_soil')==8 and not Farm.IsFieldReady(0,0,0))
local spawned=count_trace('debris');local loot=count_trace('loot_roll')
TheWorld.Map.CanTillSoilAtPoint=original;inst._working=true
assert(Drive.WorkTile(inst,0,0))
assert(Farm.IsFieldReady(0,0,0) and TILE_WRITES==1)
assert(count_trace('debris')==spawned and count_trace('loot_roll')==loot)
assert(inst._fuel:value()==798 and tool.components.finiteuses:GetUses()==58)
''')

    def test_uncultivable_land_has_no_side_effects(self):
        self.run_lua('''
TILES[tkey(0,0)]=-1;inst._working=true
local worked,reason=Drive.WorkTile(inst,0,0)
assert(not worked and reason=='CANNOT_PLOW' and inst._working)
assert(TILE_WRITES==0 and count_trace('debris')==0 and count_entities('farm_soil')==0)
assert(tool.components.finiteuses:GetUses()==60 and inst._fuel:value()==800)
''')

    def test_last_use_completes_tile_then_breaks_and_requires_new_tool(self):
        self.run_lua('''
local uses=tool.components.finiteuses;uses:SetUses(1);inst._working=true
local changed,reason=Drive.WorkTile(inst,0,0)
assert(changed and reason=='BROKEN_ATTACHMENT' and not inst._working)
assert(Farm.IsFieldReady(0,0,0) and uses:GetUses()==0 and tool:IsValid())
assert(inst.components.container:GetItemInSlot(1)==nil and inst._attachment_type==nil)
local fuel=inst._fuel:value()
local changed2,why2=Drive.WorkTile(inst,4,0)
assert(not changed2 and why2=='NO_ATTACHMENT' and inst._fuel:value()==fuel)
assert(not require('aom_landclearer_tool').Repair(inst))
tool=SpawnPrefab('aom_landclearer');inst.components.container.slots[1]=tool;inst._attachment_type='plow'
assert(Drive.WorkTile(inst,4,0) and tool.components.finiteuses:GetUses()==59)
''')

    def test_legacy_prefab_restores_durability_and_uses_new_icon(self):
        self.run_lua('''
local old=SpawnPrefab('aom_plow')
assert(old.attachment_type=='plow' and old.components.inventoryitem==nil)
old.components.finiteuses:Use(7)
local save=old.components.finiteuses:OnSave()
local loaded=SpawnPrefab('aom_plow');loaded.components.finiteuses:OnLoad(save)
assert(old.prefab=='aom_plow' and loaded.prefab=='aom_plow')
assert(loaded.components.finiteuses:GetUses()==53)
old:Remove();loaded:AddTag('NOBLOCK')
inst.components.container.slots[1]=loaded
assert(Drive.WorkTile(inst,0,0) and loaded.components.finiteuses:GetUses()==52)
''')

    def test_missing_worker_cannot_generate_debris_that_cannot_be_worked(self):
        self.run_lua('''
TILES[tkey(0,0)]=0
local changed,why,ready=Farm.Plough(0,0,0,nil,Farm.GetTerraformer(inst))
assert(not changed and why=='NO_WORKER' and not ready and TILE_WRITES==0)
''')

    def test_repreparing_giant_field_preserves_already_recorded_crop(self):
        c=self.w.combo('autumn-01-01')
        inst=self.w.lua.globals().make_flow_inst(self.w.lua.table_from(as_dict(c.ratio)),'autumn')
        inst._seed_strategy='GIANT';self.w.bind(inst,c);self.w.lua.globals().inst=inst
        self.run_lua('''
assert(Drive.WorkTile(inst,0,0));set_flow_attachment(inst,'seeder');assert(Drive.WorkHere(inst))
assert(inst._block.done==1 and crop_count()==1)
set_flow_attachment(inst,'plow')
local changed,reason,ready=Drive.WorkHere(inst)
assert(not changed and not ready and reason=='BLOCKED_MOUND')
assert(inst._block.done==1 and crop_count()==1 and count_entities('farm_soil')==8)
''')

    def test_giant_preparation_cleans_debris_but_sowing_keeps_strict_check(self):
        c=self.w.combo('autumn-01-01')
        inst=self.w.lua.globals().make_flow_inst(self.w.lua.table_from(as_dict(c.ratio)),'autumn')
        inst._seed_strategy='GIANT';self.w.bind(inst,c);self.w.lua.globals().inst=inst
        self.run_lua('''
TILES[tkey(0,0)]=0
local old=SpawnPrefab('farm_soil_debris');old.Transform:SetPosition(1.99,0,1.99)
assert(Drive.WorkTile(inst,0,0))
assert(not old.valid and count_entities('farm_soil_debris')==0 and count_entities('farm_soil')==9)
local leftover=SpawnPrefab('farm_soil_debris');leftover.Transform:SetPosition(1.5,0,1.5)
set_flow_attachment(inst,'seeder')
local ok,reason=Drive.WorkHere(inst)
assert(not ok and reason=='FOREIGN_CROP' and leftover.valid)
''')

    def test_giant_replant_cycle_allows_harvest_debris_without_wiping_crops(self):
        c=self.w.combo('autumn-01-01')
        counts={k:v*2 for k,v in as_dict(c.ratio).items()}
        inst=self.w.lua.globals().make_flow_inst(self.w.lua.table_from(counts),'autumn')
        inst._seed_strategy='GIANT';self.w.bind(inst,c);self.w.lua.globals().inst=inst
        self.run_lua('''
assert(Drive.WorkTile(inst,0,0));set_flow_attachment(inst,'seeder');assert(Drive.WorkTile(inst,0,0))
for _,v in ipairs(ENTITIES)do if v:HasTag('farm_plant') then v:Remove()end end
local leftover=SpawnPrefab('farm_soil_debris');leftover.Transform:SetPosition(.3,0,.3)
set_flow_attachment(inst,'plow')
local changed,why=Drive.WorkTile(inst,0,0)
assert(changed and not leftover.valid and count_entities('farm_soil')==9)
assert(inst._block.done==8) -- 新轮次由播种机自动选择，不需要人工确认。
set_flow_attachment(inst,'seeder');assert(Drive.WorkTile(inst,0,0))
assert(inst._block.done==8 and count_entities('farm_plant_eggplant')==4)
''')


if __name__=='__main__':unittest.main()
