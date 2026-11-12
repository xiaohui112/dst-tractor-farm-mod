"""真实配件/驾驶/农业入口的动画生命周期与资源契约；网络渲染仍需实机验收。"""
import hashlib
import json
from pathlib import Path
import sys
import unittest
from zipfile import ZipFile
from PIL import Image

import test_world_equipment as world

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from driver_animation import parse_anim,name_hash
from test_vehicle_motion import build_frames


class AttachmentAnimationFlowTests(unittest.TestCase):
    def setUp(self):
        engine=world.WorldEquipmentTests();engine.setUp();self.lua=engine.lua
        self.lua.execute('''
Animation=require('aom_attachment_animation');Drive=require('aom_drive')
for _,def in ipairs({dofile(SCRIPTS..'/prefabs/aom_attachment_work_fx.lua')})do REGISTRY[def.name]=def end
clock=0;GetTime=function()return clock end
function mounted(kind)
 local item=equipment('aom_'..(kind=='plow' and 'landclearer' or kind))
 if not player.components.rider:IsRiding()then ride()end
 assert(act(item));return item
end
function effects(item)
 local n=0;for _,v in ipairs(item._aom_work_effects or {})do if v:IsValid()then n=n+1 end end
 return n
end
''')

    def run_lua(self,s):self.lua.execute(s)

    def test_all_six_start_once_then_stop_loop_and_remove_effects_immediately(self):
        self.run_lua('''
for _,kind in ipairs({'plow','seeder','irrigator','fertilizer','weeder','harvester'})do
 local item=mounted(kind);t:SetWorking(true)
 assert(item._aom_working:value() and item.animation==kind..'_work_pre',kind)
 assert(#item.animation_queue==1 and item.animation_queue[1].name==kind..'_work_loop'
  and item.animation_queue[1].loop,kind)
 for i=1,5 do Mount.UpdateVisual(item)end
 assert(item.animation==kind..'_work_pre' and #item.animation_queue==1)
 Animation.Success(t);assert(effects(item)>0,kind)
 local task=item._aom_effect_task;local spawned=item._aom_work_effects
 t:SetWorking(false)
 assert(not item._aom_working:value() and task.cancelled and effects(item)==0,kind)
 assert(item.animation==kind..'_work_pst' and #item.animation_queue==1
  and item.animation_queue[1].name==kind and item.animation_queue[1].loop,kind)
 for _,fx in ipairs(spawned)do assert(not fx:IsValid())end
 assert(act(item));item:Remove()
end
''')

    def test_empty_seed_water_fertilizer_stop_through_real_sampling_and_do_not_restart(self):
        self.run_lua('''
for _,kind in ipairs({'seeder','irrigator','fertilizer'})do
 local item=mounted(kind);t:SetWorking(true);Animation.Success(t)
 local fx=item._aom_work_effects[1]
 Drive.TrackMovement(t)
 assert(not t._working and not item._aom_working:value() and not fx:IsValid(),kind)
 assert(item.animation==kind..'_work_pst' and effects(item)==0)
 for i=1,10 do Mount.UpdateVisual(item);Animation.Success(t)end
 assert(effects(item)==0 and item.animation==kind..'_work_pst')
 assert(act(item));item:Remove()
end
''')

    def test_actual_last_seed_is_planted_but_all_visuals_stop_in_same_call(self):
        self.run_lua('''
local item=mounted('seeder')
t.components.container:GiveItem(SpawnPrefab('tomato_seeds'),1)
local soil=SpawnPrefab('farm_soil');soil.Transform:SetPosition(1.2,0,.3)
t:SetWorking(true);assert(Drive.WorkTile(t,0,0))
assert(not soil:IsValid() and t.components.aom_attachment_store:GetSeedCount()==0)
assert(not t._working and not item._aom_working:value() and effects(item)==0)
assert(item.animation=='seeder_work_pst')
''')

    def test_successful_plant_effect_uses_actual_hole_and_failure_does_not_emit(self):
        self.run_lua('''
local item=mounted('seeder');local seeds=SpawnPrefab('tomato_seeds');seeds.components.stackable:SetStackSize(3)
t.components.container:GiveItem(seeds,1)
local soil=SpawnPrefab('farm_soil');soil.Transform:SetPosition(1.2,0,.3)
t:SetWorking(true);assert(Drive.WorkHere(t,0,0))
assert(effects(item)==1)
local fx=item._aom_work_effects[1];assert(fx.prefab=='aom_work_seeder' and fx.x==1.2 and fx.z==.3)
assert(not fx.components.inventoryitem and not fx.components.fertilizer and not fx.components.projectile)
assert(not fx.persists and fx:HasTag('FX') and fx:HasTag('NOCLICK'))
assert(not Drive.WorkHere(t,0,0) and effects(item)==1)
''')

    def test_manual_detach_dismount_and_death_clear_every_result_effect(self):
        for action in ["assert(act(item))", "player.components.rider:ActualDismount()",
                       "t.components.health:SetVal(0)"]:
            with self.subTest(action=action):
                self.setUp()
                self.run_lua('''
local item=mounted('harvester');t:SetWorking(true);Animation.Success(t)
local fx=item._aom_work_effects[1]
'''+action+'''
assert(not t._working and not item._aom_working:value() and not fx:IsValid())
assert(effects(item)==0 and item.animation=='harvester_work_pst')
''')

    def test_breakage_removes_work_loop_and_effects_before_putting_device_on_ground(self):
        self.run_lua('''
local item=mounted('weeder');item.components.finiteuses:SetUses(1)
t:SetWorking(true);Animation.Success(t);local fx=item._aom_work_effects[1]
Durability.UseAttachment(t,item)
assert(not t._working and not item._aom_working:value() and not fx:IsValid())
assert(Mount.Owner(item)==nil and t:GetAttachment()==nil and item.persists)
assert(item.animation=='weeder_work_pst')
''')

    def test_client_update_never_spawns_network_fx_or_overwrites_replicated_animation(self):
        self.run_lua('''
local item=mounted('irrigator');t:SetWorking(true)
TheWorld.ismastersim=false
SpawnPrefab=function()error('clients must not spawn network work effects')end
item.AnimState.PlayAnimation=function()error('client must preserve server animation')end
item.AnimState.PushAnimation=item.AnimState.PlayAnimation
Animation.Success(t);Animation.SetWorking(t,true);Mount.UpdateVisual(item)
item._aom_working:set(false);t._workstatus:set(false);Mount.UpdateVisual(item)
assert(item._aom_work_effects==nil)
''')

    def test_dedicated_server_drives_network_animation_and_never_requires_audio_or_input(self):
        self.run_lua('''
TheNet.IsDedicated=function()return true end;TheInput=nil;TheFrontEnd=nil
local item=mounted('fertilizer');t:SetWorking(true);Animation.Success(t)
assert(item._aom_working:value() and item._aom_stream:IsValid())
t:SetWorking(false);assert(not item._aom_working:value() and effects(item)==0)
''')

    def test_repeated_results_extend_stream_without_duplicates_and_timeout_cleans_it(self):
        self.run_lua('''
local item=mounted('irrigator');player.Transform:SetRotation(90);Mount.UpdateVisual(item)
t:SetWorking(true);Animation.Success(t)
local fx=item._aom_stream;local oldtask=item._aom_effect_task;local timeout=fx._aom_timeout
clock=.4;Animation.Success(t)
assert(item._aom_stream==fx and effects(item)==1 and oldtask.cancelled and timeout.cancelled)
assert(fx.parent==item and fx.x==0 and fx.y==0 and fx.z==0 and fx.rotation==0 and item.rotation==90)
local current=item._aom_effect_task;current.fn(item)
assert(not fx:IsValid() and effects(item)==0 and current.cancelled)
assert(t._working and item._aom_working:value())
Animation.Success(t);assert(item._aom_stream~=fx and effects(item)==1)
''')

    def test_owner_removal_and_reload_never_restore_active_animation_or_fx(self):
        self.run_lua('''
local item=mounted('harvester');t:SetWorking(true);Animation.Success(t)
local record=clone(t:GetSaveRecord());local fx=item._aom_work_effects[1]
t:Remove();assert(not fx:IsValid() and not item._aom_working:value())
local restored=SpawnSaveRecord(record);local device=restored:GetAttachment()
assert(not restored._working and not device._aom_working:value())
assert(device.animation=='harvester' and effects(device)==0)
''')


class AttachmentAnimationAssetTests(unittest.TestCase):
    def test_all_work_states_cover_all_directions_and_reference_real_build_frames(self):
        with ZipFile(ROOT/'mod/Tractor/anim/aom_attachment_shared.zip') as z:
            self.assertIsNone(z.testzip())
            _,symbols=build_frames(z.read('build.bin'));d=parse_anim(z.read('anim.bin'))
        for kind in ['plow','seeder','irrigator','fertilizer','weeder','harvester']:
            for suffix,n in [('pre',6),('loop',24),('pst',6)]:
                variants=[a for a in d['animations'] if a['name']==kind+'_work_'+suffix]
                self.assertEqual({a['facing']for a in variants},{5,48,192,2,8})
                for a in variants:
                    self.assertEqual(len(a['frames']),n)
                    for fr in a['frames']:
                        for e in fr['elements']:
                            self.assertIn(e['frame'],[r[0]for r in symbols[e['symbol']]])
                    if suffix=='loop':
                        self.assertGreater(len({str(f['elements'])for f in a['frames']}),3)

    def test_harvester_is_one_original_tooth_strip_with_forward_wrapping_frames(self):
        with ZipFile(ROOT/'mod/Tractor/anim/aom_attachment_shared.zip') as z:
            d=parse_anim(z.read('anim.bin'));_,symbols=build_frames(z.read('build.bin'))
        cutter=name_hash('harvester_belt')
        self.assertEqual(len(symbols[cutter]),5*24)
        self.assertNotIn(name_hash('harvester_fixed'),symbols)
        for a in d['animations']:
            if a['name']!='harvester_work_loop':continue
            rows=[[e for e in f['elements'] if e['symbol']==cutter] for f in a['frames']]
            self.assertTrue(all(len(v)==1 for v in rows))
            self.assertEqual([v[0]['frame']%24 for v in rows],list(range(24)))

    def test_native_water_reuses_only_the_native_water_symbol_and_copies_no_game_textures(self):
        report=json.loads((ROOT/'mod/Tractor/Attachment-Build-Report.json').read_text())
        self.assertEqual(report['native_water']['native_frames'],[0,1,2,3])
        self.assertFalse(report['native_water']['textures_copied'])
        self.assertTrue(all(max(size)<=4096 for size in report['atlas_sizes'].values()))
        for name,sha in report['sha256'].items():
            path=ROOT/'mod/Tractor/anim'/(name+'.zip')
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),sha)
        with ZipFile(ROOT/'mod/Tractor/anim/aom_attachment_water.zip') as z:
            self.assertEqual(z.namelist(),['anim.bin'])
            d=parse_anim(z.read('anim.bin'))
        self.assertEqual({a['facing']for a in d['animations']},{5,48,192,2,8})
        for a in d['animations']:
            for fr in a['frames']:
                self.assertTrue(all(e['symbol']==name_hash('water') and e['frame']in range(4) for e in fr['elements']))


    def test_moving_single_tooth_strip_never_escapes_rail_in_any_direction_or_phase(self):
        rig=ROOT/'assets/directional-v2/attachment-rig'
        for view in ['downside','side','upside','down','up']:
            with Image.open(rig/f'harvester-{view}-mask.png') as im:mask=list(im.getchannel('R').getdata())
            for phase in range(24):
                with self.subTest(view=view,phase=phase),Image.open(rig/f'harvester-{view}-belt-{phase:02d}.png') as im:
                    alpha=list(im.getchannel('A').getdata())
                    self.assertGreater(sum(alpha),0)
                    self.assertFalse(any(a for a,m in zip(alpha,mask)if m==0))


if __name__=='__main__':unittest.main()
