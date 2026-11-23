"""作业音效与洒水音乐互斥、原版等级音量及已编译PCM来源校验。"""
from pathlib import Path
import hashlib
import json
import struct
import unittest
import wave
import xml.etree.ElementTree as ET
import test_native_riding as riding

ROOT=Path(__file__).resolve().parents[2]


class AudioPolicyTests(unittest.TestCase):
    def setUp(self):
        engine=riding.NativeRidingTests();engine.setUp();self.lua=engine.lua
        self.lua.execute('''
Music=require('aom_irrigator_music');Motion=require('aom_vehicle_motion')
Music.Configure('on','test/',function()return true end,function()end)
playing={};volumes={};calls=0
p.SoundEmitter.PlaySound=function(_,event,handle,volume)
 playing[handle]=event;volumes[handle]=volume;calls=calls+1
end
p.SoundEmitter.KillSound=function(_,handle)playing[handle]=nil end
p.SoundEmitter.PlayingSound=function(_,handle)return playing[handle]~=nil end
p.SoundEmitter.SetVolume=function(_,handle,volume)volumes[handle]=volume end
AllPlayers={p}
assert(ACTIONS.MOUNT.fn({doer=p,target=t}));p.sg:GoToState('mounted_idle')
t._atttype_net:set('irrigator');t._water_net:set(20);t._workstatus:set(true)
controller=Music.New(p);Motion.Update(t)
function mode(value)t._music_mode_net:set(value);p.x=p.x+1;Motion.Update(t);controller:Update()end
''')

    def run_lua(self,s):self.lua.execute(s)

    def test_on_plays_only_music_and_off_or_mute_restores_engine_and_work_effect(self):
        self.run_lua('''
for _,setting in ipairs({'on','off','mute','on'})do
 mode(setting)
 if setting=='on' then
  assert(playing[Music.HANDLE] and not playing[Motion.ENGINE])
  assert(volumes[Music.HANDLE]==1)
 else
  assert(not playing[Music.HANDLE] and playing[Motion.ENGINE]=='aom_tractor_sfx/tractor/work')
  assert(volumes[Motion.ENGINE]==1)
 end
end
local n=calls;p.x=p.x+1;Motion.Update(t);controller:Update();assert(calls==n)
''')

    def test_stationary_work_plays_only_music_but_stopping_work_restores_idle(self):
        self.run_lua('''
mode('on');Motion.Update(t)
assert(playing[Music.HANDLE] and not playing[Motion.ENGINE])
t._workstatus:set(false);Motion.Update(t);controller:Update()
assert(not playing[Music.HANDLE] and playing[Motion.ENGINE]=='aom_tractor_sfx/tractor/idle')
''')

    def test_no_water_no_fuel_swap_and_dismount_do_not_leave_stale_music_or_effects(self):
        self.run_lua('''
mode('on');t._water_net:set(0);p.x=p.x+1;Motion.Update(t);controller:Update()
assert(not playing[Music.HANDLE] and playing[Motion.ENGINE]=='aom_tractor_sfx/tractor/work')
t._water_net:set(20);mode('on')
t._atttype_net:set('harvester');p.x=p.x+1;Motion.Update(t);controller:Update()
assert(not playing[Music.HANDLE] and playing[Motion.ENGINE]=='aom_tractor_sfx/tractor/work')
t:SetFuel(0);Motion.Update(t);controller:Update();assert(next(playing)==nil)
t:SetFuel(10);mode('on')
p.components.rider:ActualDismount();Motion.Update(t);controller:Update();assert(next(playing)==nil)
''')

    def test_missing_music_bank_keeps_tractor_effects_and_pause_resume_does_not_stack_them(self):
        self.run_lua('''
Music.ready=false;mode('on')
assert(not playing[Music.HANDLE] and playing[Motion.ENGINE]=='aom_tractor_sfx/tractor/work')
Music.ready=true;mode('on');PAUSED=true;controller:Update();assert(next(playing)==nil)
PAUSED=false;controller:Update();assert(playing[Music.HANDLE] and not playing[Motion.ENGINE])
''')


class CalibratedAudioAssetsTests(unittest.TestCase):
    def test_work_source_and_loudness_match_approved_c_and_native_reference(self):
        source=ROOT/'assets/audio/sources/sfxmint-tractor-02.mp3'
        origin=json.loads(source.with_suffix('.json').read_text())
        self.assertEqual(origin['source_page'],'https://sfxmint.com/sounds/tractor-02')
        self.assertEqual(origin['source_sha256'],hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertEqual(origin['license'],'CC0 1.0 Universal')
        calibration=json.loads((ROOT/'assets/audio/loudness-calibration.json').read_text())
        reference=json.loads((ROOT/'assets/audio/native-sfx-reference.json').read_text())
        self.assertEqual(calibration['target_lufs'],reference['target_lufs'])
        for key,name in [('work','tractor_work.wav'),('music','lanhuacao_loop.wav')]:
            item=calibration[key]
            self.assertLess(abs(float(item['measured']['input_i'])-reference['target_lufs']),.3)
            self.assertLessEqual(float(item['measured']['input_tp']),-2.8)
            wav=ROOT/'assets/audio'/name
            self.assertEqual(item['wav_sha256'],hashlib.sha256(wav.read_bytes()).hexdigest())
        with wave.open(str(ROOT/'assets/audio/tractor_work.wav')) as w:
            pcm=struct.unpack('<%dh'%w.getnframes(),w.readframes(w.getnframes()))
            self.assertEqual(w.getnframes(),303408)
            # Crossing the loop boundary must not create a larger discontinuity
            # than normal adjacent samples, nor insert a silent start/end fade.
            self.assertLess(abs(pcm[-1]-pcm[0]),max(abs(b-a) for a,b in zip(pcm,pcm[1:])))
            self.assertGreater(sum(abs(x) for x in pcm[:441]),0)

    def test_pcm_bank_contains_exact_three_source_waves_and_default_gain(self):
        from music_bank import inspect_pcm_samples
        fsb=(ROOT/'mod/Tractor/sound/aom_tractor_sfx.fsb').read_bytes()
        samples=inspect_pcm_samples(fsb)
        self.assertEqual(set(samples),{'tractor_idle','tractor_drive','tractor_work'})
        for name,entry in samples.items():
            with wave.open(str(ROOT/'assets/audio'/(name+'.wav'))) as w:
                pcm=w.readframes(w.getnframes())
                self.assertEqual(entry['frames'],w.getnframes())
                self.assertEqual(entry['pcm_sha256'],hashlib.sha256(pcm).hexdigest())
        xml=ET.parse(ROOT/'assets/audio/fmod/aom_tractor_sfx.fdp')
        for event in xml.findall('eventgroup/event'):
            self.assertEqual(event.findtext('volume_db'),'0')
            self.assertEqual(event.findtext('category'),'set_sfx')
            self.assertEqual(event.findtext('layer/sound/loopcount2'),'-1')


if __name__=='__main__':unittest.main()
