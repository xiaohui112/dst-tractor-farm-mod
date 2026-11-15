"""本轮实机反馈：静态暂停检测、精简悬停、占用跳过和真实死亡动画资产。"""
from pathlib import Path
from zipfile import ZipFile
import unittest
from PIL import Image
from driver_animation import parse_anim, name_hash, build_symbols
import test_dashboard as dashboard
import test_landclearer_flow as land
from test_giant_farming import as_dict

ROOT=Path(__file__).resolve().parents[2]


class PauseAndTooltipTests(unittest.TestCase):
    setUp=dashboard.DashboardTests.setUp
    run_lua=dashboard.DashboardTests.run_lua

    def test_water_tooltip_has_only_quantity_when_idle_filling_or_empty(self):
        self.run_lua('''
for _,filling in ipairs({false,true})do
 t._refilling_net:set(filling);hud:Refresh(t)
 assert(hud.badges.water:GetTooltip()=='水量 20/400')
end
t._water_net:set(0);hud:Refresh(t)
assert(hud.badges.water:GetTooltip()=='水量 0/400')
''')

    def test_actual_hud_uses_static_task_to_stop_audio_while_sim_tasks_are_paused(self):
        self.run_lua('''
local static={};local simulated={}
function player:DoStaticPeriodicTask(period,fn)
 local task={fn=fn,Cancel=function(self)self.cancelled=true end}
 static[#static+1]=task;return task
end
function player:DoPeriodicTask(period,fn)
 local task={fn=fn,Cancel=function(self)self.cancelled=true end}
 simulated[#simulated+1]=task;return task
end
local active=false;local plays=0
player.SoundEmitter.PlaySound=function(_,event,handle)if handle==Music.HANDLE then active=true;plays=plays+1 end end
player.SoundEmitter.KillSound=function(_,handle)if handle==Music.HANDLE then active=false end end
player.SoundEmitter.PlayingSound=function()return active end
player.SoundEmitter.SetVolume=function()end
AllPlayers={player};t._workstatus:set(true)
local frame={inst=CreateEntity(),controls={bottom_root={AddChild=function(_,child)return child end}}}
function frame:SetMainCharacter(owner)self.owner=owner;owner.HUD=self end
POST_FNS['screens/playerhud'](frame);frame:SetMainCharacter(player)
assert(#static==1 and #simulated==1)
static[1].fn();assert(active and plays==1)
-- 暂停期间不运行任何模拟时钟任务；只有静态任务继续执行。
PAUSED=true;static[1].fn();assert(not active)
PAUSED=false;static[1].fn();assert(active and plays==2)
frame.inst:Remove();assert(static[1].cancelled and simulated[1].cancelled and not active)
''')

    def test_health_death_keeps_vehicle_scale_and_loads_wreck_animation(self):
        self.run_lua('''
local scale=t.anim_scale[1]
t.components.health:SetVal(0)
assert(t._wreck_net:value() and t.animation=='death' and t.anim_scale[1]==scale)
assert(not player.components.rider:IsRiding())
local record=clone(t:GetSaveRecord());t:Remove();local loaded=SpawnSaveRecord(record)
assert(loaded.animation=='death' and loaded.anim_scale[1]==scale)
assert(loaded.components.health:IsDead())
''')


class PloughSkipTests(unittest.TestCase):
    setUp=land.LandClearerFlowTests.setUp
    run_lua=land.LandClearerFlowTests.run_lua

    def test_plants_and_rock_tiles_are_skipped_then_continuous_work_reaches_clean_tile(self):
        self.run_lua('''
function inst:DoPeriodicTask(_,fn)return {fn=fn,Cancel=function()end}end
TILES[tkey(0,0)]=0;TILES[tkey(4,0)]=0
local plant=SpawnPrefab('farm_plant_tomato');plant.Transform:SetPosition(0,0,0)
local rock=SpawnPrefab('rock1');rock.components.inventoryitem=nil;rock:RemoveTag('NOBLOCK')
rock.Transform:SetPosition(4,0,0)
Drive.SetWorking(inst,true);local task=inst._worktask
task.fn(inst);assert(inst._working and inst._fuel:value()==800)
inst.x=8;task.fn(inst)
assert(inst._working and inst._worktask==task and Farm.IsFieldReady(8,0,0))
assert(plant.valid and rock.valid and TheWorld.Map:GetTileAtPoint(0,0,0)==0)
assert(TheWorld.Map:GetTileAtPoint(4,0,0)==0 and inst._fuel:value()==799)
assert(tool.components.finiteuses:GetUses()==59)
''')

    def test_existing_farmland_skips_occupied_pit_without_stopping_or_charging_twice(self):
        self.run_lua('''
local crop=SpawnPrefab('farm_plant_tomato');crop.Transform:SetPosition(0,0,0)
inst._working=true;local changed,why=Drive.WorkTile(inst,0,0)
assert(changed and why=='BLOCKED_MOUND' and inst._working and crop.valid)
assert(count_entities('farm_soil')==8 and not Farm.IsFieldReady(0,0,0))
assert(inst._fuel:value()==799 and tool.components.finiteuses:GetUses()==59)
assert(not Drive.WorkTile(inst,0,0) and inst._working)
assert(inst._fuel:value()==799 and tool.components.finiteuses:GetUses()==59)
crop:Remove();assert(Drive.WorkTile(inst,0,0) and Farm.IsFieldReady(0,0,0))
assert(inst._fuel:value()==798 and tool.components.finiteuses:GetUses()==58)
''')

    def test_weeds_and_wild_plants_are_preserved_at_occupied_pits(self):
        self.run_lua('''
local weed=SpawnPrefab('weed_ivy');weed.Transform:SetPosition(0,0,0)
weed.components.workable=dofile(REF..'/workable.lua')(weed)
weed.components.workable:SetWorkAction(ACTIONS.DIG)
weed.components.workable:SetWorkLeft(1)
weed.components.workable:SetOnFinishCallback(function()error('must not dig protected plant')end)
inst._working=true;assert(Drive.WorkTile(inst,0,0) and weed.valid and inst._working)
assert(count_entities('farm_soil')==8)
weed:Remove()
local grass=SpawnPrefab('grass');grass:AddTag('plant');grass.Transform:SetPosition(0,0,0)
assert(not Drive.WorkTile(inst,0,0) and grass.valid and inst._working)
assert(inst._fuel:value()==799)
''')

    def test_neighbor_crop_is_not_collapsed_by_tilling_a_border_pit(self):
        self.run_lua('''
local crop=SpawnPrefab('farm_plant_tomato');crop.Transform:SetPosition(2.1,0,0)
local collapse=TheWorld.Map.CollapseSoilAtPoint
TheWorld.Map.CollapseSoilAtPoint=function(self,x,y,z)
 assert((crop.x-x)^2+(crop.z-z)^2>=1.25^2)
 return collapse(self,x,y,z)
end
inst._working=true;assert(Drive.WorkTile(inst,0,0) and crop.valid and inst._working)
assert(count_entities('farm_soil')<9)
''')

    def test_confirmed_giant_plan_can_prepare_other_tiles_but_cannot_plant_through_foreign_crop(self):
        w=self.w;combo=w.combo('autumn-01-02')
        inst=w.lua.globals().make_flow_inst(w.lua.table_from(as_dict(combo.ratio)),'autumn')
        inst._seed_strategy='GIANT';w.bind(inst,combo);w.lua.globals().inst=inst
        self.run_lua('''
local slots,tiles=Block.WorldSlots(inst._block)
local crop=SpawnPrefab('farm_plant_garlic');crop.Transform:SetPosition(slots[1].x,0,slots[1].z)
inst._working=true
for _,tile in pairs(tiles)do Drive.WorkTile(inst,tile.x,tile.z);assert(inst._working)end
assert(crop.valid and inst._block.done==0 and count_entities('farm_soil')>0)
set_flow_attachment(inst,'seeder')
local changed,why=Drive.WorkHere(inst,slots[1].cx,slots[1].cz)
assert(not changed and why=='FOREIGN_CROP' and inst._block.done==0 and crop.valid)
''')


class DeathAssetTests(unittest.TestCase):
    def test_all_death_facings_use_full_scale_wreck_symbol_and_packed_stays_half_scale(self):
        with ZipFile(ROOT/'mod/Tractor/anim/aom_tractor_chassis.zip') as z:
            bank=parse_anim(z.read('anim.bin'));symbols=build_symbols(z.read('build.bin'))[1]
        self.assertIn(name_hash('wreck'),symbols)
        death=[a for a in bank['animations'] if a['name']=='death']
        self.assertEqual({a['facing'] for a in death},{5,48,192,2,8})
        for a in death:
            e=a['frames'][0]['elements']
            self.assertEqual(len(e),1)
            self.assertEqual(e[0]['symbol'],name_hash('wreck'))
            self.assertEqual(e[0]['matrix'],[1.,0.,0.,1.,0.,0.])
        for a in bank['animations']:
            if a['name']=='idle_packed':self.assertEqual(a['frames'][0]['elements'][0]['matrix'][0],.5)
        with Image.open(ROOT/'assets/directional-v2/sprites/tractor/death.png') as im:
            self.assertEqual(im.width,260)
            self.assertGreater(im.height,190)


if __name__=='__main__':unittest.main()
