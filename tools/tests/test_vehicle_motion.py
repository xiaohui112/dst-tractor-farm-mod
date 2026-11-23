"""驾驶八向、音效状态与已编译资源；不替代 DST 实机视听验收。"""
import json
from pathlib import Path
import struct
import sys
import unittest
import wave
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import test_native_riding as riding

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from driver_animation import Reader,parse_anim,name_hash
from music_bank import riff_chunks


def build_frames(raw):
    r=Reader(raw);assert r.read(8)==b'BILD\x06\x00\x00\x00'
    count,total=r.unpack('2I');name=r.string()
    for _ in range(r.unpack('I')[0]):r.string()
    symbols={}
    for _ in range(count):
        key,n=r.unpack('2I');symbols[key]=[r.unpack('2I4f2I') for _ in range(n)]
    assert sum(len(v) for v in symbols.values())==total
    return name,symbols


class VehicleAssetTests(unittest.TestCase):
    def test_wheel_spokes_rotate_around_both_measured_hubs(self):
        hubs=[{(43.5,211.),(131.,237.5)}, {(59.5,197.),(193.,219.5)}, {(156.5,215.),(215.,221.)}]
        rig=ROOT/'assets/directional-v2/rig'
        for view,expected in enumerate(hubs):
            for phase in range(12):
                with self.subTest(view=view,phase=phase):
                    svg=ET.parse(rig/f'wheel-{view}-{phase}.svg')
                    spokes=svg.findall('{http://www.w3.org/2000/svg}path')
                    origins={tuple(map(float,spoke.attrib['d'][1:].split(' L')[0].split())) for spoke in spokes}
                    self.assertEqual(len(spokes),10)
                    self.assertEqual(origins,expected)

    def test_tractor_and_every_attachment_include_distinct_front_and_rear_frames(self):
        for name,kinds in [('aom_tractor_chassis',['body']),
                           ('aom_attachment_shared',['plow','seeder','irrigator','fertilizer','weeder','harvester']),
                           ('aom_attachment_symbols',['plow','seeder','irrigator','fertilizer','weeder','harvester'])]:
            with self.subTest(package=name),ZipFile(ROOT/'mod/Tractor/anim'/(name+'.zip')) as z:
                self.assertIsNone(z.testzip())
                _,symbols=build_frames(z.read('build.bin'));anim=parse_anim(z.read('anim.bin'))
                for kind in kinds:
                    records=symbols[name_hash(kind)]
                    self.assertEqual([r[0] for r in records],list(range(5)))
                    self.assertNotEqual(records[3][-2],records[4][-2])
                    variants=[a for a in anim['animations'] if a['bank']==name_hash(name) and a['name']==('idle' if kind=='body' else kind)]
                    self.assertEqual({a['facing'] for a in variants},{5,48,192,2,8})
                    frames={a['facing']:next(e['frame'] for e in a['frames'][0]['elements'] if e['symbol']==name_hash(kind)) for a in variants}
                    self.assertEqual(frames[8],3);self.assertEqual(frames[2],4)

    def test_wheel_lines_only_animate_when_the_wheel_faces_are_visible(self):
        wheel=name_hash('aom_wheels')
        for name in ('aom_tractor_chassis','aom_tractor_cabin','aom_tractor_driver',
                     'aom_tractor_driver_075','aom_tractor_driver_125','aom_tractor_driver_150'):
            with self.subTest(bank=name),ZipFile(ROOT/'mod/Tractor/anim'/(name+'.zip')) as z:
                self.assertIsNone(z.testzip())
                anim=parse_anim(z.read('anim.bin'))
                for a in anim['animations']:
                    wheels={e['frame'] for f in a['frames'] for e in f['elements'] if e['symbol']==wheel}
                    if a['facing'] in (2,8):
                        self.assertFalse(wheels,(a['name'],a['facing']))
                    elif a['name']=='run_loop':
                        self.assertGreater(len(wheels),3,a['facing'])
                del anim

    def test_real_driver_run_has_suspension_in_every_direction(self):
        with ZipFile(ROOT/'mod/Tractor/anim/aom_tractor_driver.zip') as z:
            with ZipFile(ROOT/'mod/Tractor/anim/aom_tractor_cabin.zip') as shared:
                _,symbols=build_frames(shared.read('build.bin'))
            anim=parse_anim(z.read('anim.bin'))
            self.assertEqual(len(symbols[name_hash('aom_wheels')]),60)
            for name in ['mount','dismount','idle_loop','run_pre','run_loop','run_pst']:
                self.assertEqual({a['facing'] for a in anim['animations'] if a['name']==name},{5,48,192,2,8})
            for a in [a for a in anim['animations'] if a['name']=='run_loop']:
                body=[next(e['matrix'][5] for e in f['elements'] if e['symbol']==name_hash('aom_cabin_front')) for f in a['frames']]
                self.assertGreater(max(body)-min(body),2)
            for a in [a for a in anim['animations'] if a['name'].startswith(('run_','walk_','sprint_')) or a['name']=='idle_loop']:
                reference=None
                for f in a['frames']:
                    shell=next(e for e in f['elements'] if e['symbol']==name_hash('aom_cabin_front'))
                    driver=[e for e in f['elements'] if e['symbol'] not in symbols]
                    pose=[(e['symbol'],e['frame'],e['layer'],e['matrix'][:4],
                           e['matrix'][4]-shell['matrix'][4],e['matrix'][5]-shell['matrix'][5]) for e in driver]
                    if reference is None:reference=pose
                    self.assertEqual(len(reference),len(pose))
                    for first,current in zip(reference,pose):
                        self.assertEqual(first[:4],current[:4])
                        self.assertAlmostEqual(first[4],current[4],delta=.0001)
                        self.assertAlmostEqual(first[5],current[5],delta=.0001)

    def test_native_character_world_size_is_preserved_for_every_vehicle_size(self):
        # 历史Windows交付包已清理；直接以已安装游戏的原版角色头部为尺寸基准。
        game=Path.home()/"Library/Application Support/Steam/steamapps/common/Don't Starve Together/dontstarve_steam.app/Contents"
        with ZipFile(game/'data/anim/player_idles.zip') as z:old=parse_anim(z.read('anim.bin'))
        def head(bank):
            a=next(a for a in bank['animations'] if a['name']=='idle_loop' and a['facing']==5)
            return next(e['matrix'] for e in a['frames'][0]['elements'] if bank['strings'].get(e['symbol'])=='headbase')
        before=head(old)
        keys={(name,facing) for name in ['mount','dismount','idle_loop','run_pre','run_loop','run_pst'] for facing in [5,48,192,2,8]}
        del old
        config=json.loads((ROOT/'assets/directional-v2/seat-layout.json').read_text())
        for name,vehicle_scale in config['vehicle_scales'].items():
            with self.subTest(bank=name),ZipFile(ROOT/'mod/Tractor/anim'/(name+'.zip')) as z:
                self.assertIsNone(z.testzip());new=parse_anim(z.read('anim.bin'))
                after=head(new)
                for i in range(4):
                    self.assertAlmostEqual(after[i]*vehicle_scale,before[i],places=5)
                self.assertTrue(all(a['bank']==name_hash(name) for a in new['animations']))
                self.assertTrue(keys.issubset({(a['name'],a['facing']) for a in new['animations']}))
                del new

    def test_engine_bank_contains_three_real_looping_pcm_effects(self):
        base=ROOT/'mod/Tractor/sound/aom_tractor_sfx'
        fev=base.with_suffix('.fev').read_bytes();fsb=base.with_suffix('.fsb').read_bytes()
        self.assertEqual(fev[:4],b'RIFF');chunks=riff_chunks(fev,12,len(fev))
        for name in ['tractor','idle','drive','work']:self.assertIn(name.encode()+b'\0',chunks[b'STRR'])
        self.assertEqual(fsb[:4],b'FSB5');self.assertEqual(struct.unpack_from('<I',fsb,8)[0],3)
        for name in ['idle','drive','work']:
            with wave.open(str(ROOT/'assets/audio'/('tractor_'+name+'.wav'))) as audio:
                self.assertEqual(audio.getnframes(),round(44100*(6.88 if name=='work' else 4)))
                self.assertEqual(audio.getnchannels(),1)
                self.assertGreater(len(set(audio.readframes(audio.getnframes()))),50)


class VehicleMotionTests(unittest.TestCase):
    def setUp(self):
        engine=riding.NativeRidingTests();engine.setUp();self.lua=engine.lua

    def test_only_tractor_mutes_mounted_steps_on_server_and_predicting_client(self):
        self.lua.execute('''
local function exercise(graph,predicted)
 local played=0
 local function sound()played=played+1 end
 local function at(frame)return {time=frame*FRAMES,fn=sound}end
 local start={at(0),at(5)}
 local loop=predicted and {at(0),at(5)} or {at(0),at(1),at(8)}
 local other=at(24)
 loop[#loop+1]=other
 local sg={states={run_start={timeline=start},run={timeline=loop}}}
 SG_POST_FNS[graph](sg);SG_POST_FNS[graph](sg)
 assert(other.fn==sound)
 local mount
 local driver={replica={},components={}}
 local rider={GetMount=function()return mount end}
 if predicted then driver.replica.rider=rider else driver.components.rider=rider end
 local function run()
  for _,event in ipairs(start)do event.fn(driver)end
  for _,event in ipairs(loop)do event.fn(driver)end
 end
 mount=t;run();assert(played==1)
 mount=make_player();run();assert(played==1+#start+#loop)
 mount=nil;run();assert(played==1+2*(#start+#loop))
end
exercise('wilson',false)
exercise('wilson_client',true)
''')

    def test_engine_changes_idle_drive_work_without_duplicates_and_stops_on_empty_or_dismount(self):
        self.lua.execute('''
local motion=require('aom_vehicle_motion')
local playing={};local calls=0;local gain
p.SoundEmitter.PlaySound=function(_,event,handle,volume,local_only)
 assert(local_only and next(playing)==nil);playing[handle]=event;calls=calls+1;gain=volume
end
p.SoundEmitter.KillSound=function(_,handle)playing[handle]=nil end
p.SoundEmitter.PlayingSound=function(_,handle)return playing[handle]~=nil end
assert(ACTIONS.MOUNT.fn({doer=p,target=t}));p.sg:GoToState('mounted_idle')
motion.Update(t)
assert(p.facing_count==8 and playing[motion.ENGINE]=='aom_tractor_sfx/tractor/idle')
for i=1,10 do motion.Update(t)end;assert(calls==1)
p.x=1;motion.Update(t)
assert(playing[motion.ENGINE]=='dontstarve/common/together/battery/on_LP' and gain==1)
t._workstatus:set(true);p.x=2;motion.Update(t)
assert(playing[motion.ENGINE]=='aom_tractor_sfx/tractor/work' and gain==1)
local n=calls;p.x=3;motion.Update(t);assert(calls==n)
t._workstatus:set(false);p.x=4;motion.Update(t)
assert(playing[motion.ENGINE]=='dontstarve/common/together/battery/on_LP' and gain==1)
playing[motion.ENGINE]=nil;p.x=5;motion.Update(t)
assert(playing[motion.ENGINE]=='dontstarve/common/together/battery/on_LP')
motion.Update(t);assert(playing[motion.ENGINE]=='aom_tractor_sfx/tractor/idle')
t:SetFuel(0);motion.Update(t);assert(next(playing)==nil)
t:SetFuel(10);motion.Update(t);assert(playing[motion.ENGINE])
p.components.rider:ActualDismount();motion.Update(t);assert(next(playing)==nil and p.facing_count==4)
''')

    def test_dedicated_server_changes_facing_without_playing_audio(self):
        self.lua.execute('''
TheNet.IsDedicated=function()return true end
p.SoundEmitter.PlaySound=function()error('dedicated server must not play effects')end
assert(ACTIONS.MOUNT.fn({doer=p,target=t}))
require('aom_vehicle_motion').Update(t)
assert(p.facing_count==8)
''')

    def test_keep_giant_clears_only_nearby_produce_collision_and_restores_it(self):
        self.lua.execute('''
local Motion=require('aom_vehicle_motion')
COLLISION={OBSTACLES=512,CHARACTERS=1024}
bit={band=function(mask,flag)return (math.floor(mask/flag)%2)*flag end}
local function obstacle(name,x,tag)
 local item=CreateEntity();item.prefab=name;item.Transform:SetPosition(x,0,0)
 if tag then item:AddTag('oversized_veggie') end
 local mask=1280
 item.Physics={GetCollisionGroup=function()return 512 end,GetCollisionMask=function()return mask end,
  ClearCollidesWith=function(_,flag)mask=mask-flag end,CollidesWith=function(_,flag)mask=mask+flag end}
 return item
end
local fruit=obstacle('pumpkin_oversized',0,true)
local far=obstacle('pumpkin_oversized',8,true)
local wall=obstacle('wall_stone',0,false)
local waxed=obstacle('pumpkin_oversized_waxed',0,true)
local base_find=TheSim.FindEntities
TheSim.FindEntities=function(self,x,y,z,r,tags,...)
 if not tags or tags[1]~='oversized_veggie' then return base_find(self,x,y,z,r,tags,...) end
 local nearby={}
 for _,item in ipairs({fruit,far,wall,waxed}) do
  if item:HasTag(tags[1]) and (item.x-x)^2+(item.z-z)^2<=r*r then nearby[#nearby+1]=item end
 end
 return nearby
end
assert(ACTIONS.MOUNT.fn({doer=p,target=t}));p.sg:GoToState('mounted_idle')
t._atttype_net:set('harvester');Motion.Update(t)
assert(fruit.Physics:GetCollisionMask()==1280)
t._keep_oversized_net:set(true);Motion.Update(t)
assert(fruit.Physics:GetCollisionMask()==256 and far.Physics:GetCollisionMask()==1280)
assert(wall.Physics:GetCollisionMask()==1280 and waxed.Physics:GetCollisionMask()==1280)
local second=make_tractor();local other=make_player()
assert(ACTIONS.MOUNT.fn({doer=other,target=second}));other.sg:GoToState('mounted_idle')
second._atttype_net:set('harvester');second._keep_oversized_net:set(true);Motion.Update(second)
p.Transform:SetPosition(4,0,0);Motion.Update(t)
assert(fruit.Physics:GetCollisionMask()==256)
other.components.rider:ActualDismount();Motion.Update(second)
assert(fruit.Physics:GetCollisionMask()==1280 and fruit.x==0 and fruit:IsValid())
''')

    def test_legacy_scale_options_migrate_to_new_default(self):
        for value,expected in [('3',2.5),('4',2.5),('1',2.5),('1.25',3.125),('0.75',1.875)]:
            self.lua.globals().option=value
            self.lua.execute("AOM_CONFIG={MODEL_SCALE=option};package.loaded.aom_model_scale=nil")
            self.assertEqual(self.lua.eval("require('aom_model_scale')"),expected)

    def test_model_setting_loads_only_its_driver_bank_and_keeps_native_skin(self):
        for option,bank,scale in [('0.75','aom_tractor_driver_075',1.875),
                                  ('1','aom_tractor_driver',2.5),
                                  ('1.25','aom_tractor_driver_125',3.125),
                                  ('1.5','aom_tractor_driver_150',3.75)]:
            with self.subTest(option=option):
                self.lua.globals().option=option
                self.lua.execute('''
AOM_CONFIG={MODEL_SCALE=option};package.loaded.aom_model_scale=nil;package.loaded.aom_driver_visual=nil
local visual=require('aom_driver_visual')
assert(visual.Configure('test/',function(path)loaded_driver_path=path;return true end))
visual.Attach(t);p.build='character_skin'
assert(ACTIONS.MOUNT.fn({doer=p,target=t}))
''')
                self.assertEqual(self.lua.globals().p.bank,bank)
                self.assertEqual(self.lua.globals().p.anim_scale[1],scale)
                self.assertEqual(self.lua.globals().loaded_driver_path,'test/anim/'+bank+'.zip')
                self.lua.execute("p.components.rider:ActualDismount();assert(p.bank=='wilson' and p.build=='character_skin' and p.anim_scale[1]==1)")


if __name__=='__main__':unittest.main()
