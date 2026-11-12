"""驾驶八向、音效状态与已编译资源；不替代 DST 实机视听验收。"""
import io
import json
from pathlib import Path
import struct
import sys
import unittest
import wave
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
                    variants=[a for a in anim['animations'] if a['name']==('idle' if kind=='body' else kind)]
                    self.assertEqual({a['facing'] for a in variants},{5,48,192,2,8})
                    frames={a['facing']:next(e['frame'] for e in a['frames'][0]['elements'] if e['symbol']==name_hash(kind)) for a in variants}
                    self.assertEqual(frames[8],3);self.assertEqual(frames[2],4)

    def test_real_driver_run_has_wheel_frames_and_suspension_in_every_direction(self):
        with ZipFile(ROOT/'mod/Tractor/anim/aom_tractor_driver.zip') as z:
            with ZipFile(ROOT/'mod/Tractor/anim/aom_tractor_cabin.zip') as shared:
                _,symbols=build_frames(shared.read('build.bin'))
            anim=parse_anim(z.read('anim.bin'))
            self.assertEqual(len(symbols[name_hash('aom_wheels')]),60)
            for name in ['mount','dismount','idle_loop','run_pre','run_loop','run_pst']:
                self.assertEqual({a['facing'] for a in anim['animations'] if a['name']==name},{5,48,192,2,8})
            for a in [a for a in anim['animations'] if a['name']=='run_loop']:
                wheels=[next(e['frame'] for e in f['elements'] if e['symbol']==name_hash('aom_wheels')) for f in a['frames']]
                body=[next(e['matrix'][5] for e in f['elements'] if e['symbol']==name_hash('aom_cabin_front')) for f in a['frames']]
                self.assertGreater(len(set(wheels)),3);self.assertGreater(max(body)-min(body),2)
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
        with ZipFile(ROOT/'Driver-Results.zip') as outer:
            name=next(n for n in outer.namelist() if n.replace('\\','/').endswith('anim/aom_tractor_driver.zip'))
            with ZipFile(io.BytesIO(outer.read(name))) as z:old=parse_anim(z.read('anim.bin'))
        def head(bank):
            a=next(a for a in bank['animations'] if a['name']=='idle_loop' and a['facing']==5)
            return next(e['matrix'] for e in a['frames'][0]['elements'] if bank['strings'].get(e['symbol'])=='headbase')
        before=head(old)
        keys={(a['name'],a['facing']) for a in old['animations']}
        del old
        config=json.loads((ROOT/'assets/directional-v2/seat-layout.json').read_text())
        for name,vehicle_scale in config['vehicle_scales'].items():
            with self.subTest(bank=name),ZipFile(ROOT/'mod/Tractor/anim'/(name+'.zip')) as z:
                self.assertIsNone(z.testzip());new=parse_anim(z.read('anim.bin'))
                after=head(new)
                for i in range(4):
                    self.assertAlmostEqual(after[i]*vehicle_scale,before[i]/.24,places=5)
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
                self.assertEqual(audio.getnframes(),44100*4)
                self.assertEqual(audio.getnchannels(),1)
                self.assertGreater(len(set(audio.readframes(audio.getnframes()))),50)


class VehicleMotionTests(unittest.TestCase):
    def setUp(self):
        engine=riding.NativeRidingTests();engine.setUp();self.lua=engine.lua

    def test_engine_changes_idle_drive_work_without_duplicates_and_stops_on_empty_or_dismount(self):
        self.lua.execute('''
local motion=require('aom_vehicle_motion')
local playing={};local calls=0
p.SoundEmitter.PlaySound=function(_,event,handle)playing[handle]=event;calls=calls+1 end
p.SoundEmitter.KillSound=function(_,handle)playing[handle]=nil end
assert(ACTIONS.MOUNT.fn({doer=p,target=t}));p.sg:GoToState('mounted_idle')
motion.Update(t)
assert(p.facing_count==8 and playing[motion.ENGINE]=='aom_tractor_sfx/tractor/idle')
for i=1,10 do motion.Update(t)end;assert(calls==1)
t._workstatus:set(true);p.x=1;motion.Update(t)
assert(playing[motion.ENGINE]=='aom_tractor_sfx/tractor/drive' and playing[motion.WORK])
local n=calls;p.x=2;motion.Update(t);assert(calls==n)
motion.Update(t);assert(not playing[motion.WORK] and playing[motion.ENGINE]=='aom_tractor_sfx/tractor/idle')
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
