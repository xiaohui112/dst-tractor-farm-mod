"""音乐独立生命周期，音效仅使用可观察桩；不代表真实 FMOD 试听。"""
from pathlib import Path
import hashlib
import json
import sys
import wave
import xml.etree.ElementTree as ET
import unittest
from lupa.lua51 import LuaRuntime

ROOT=Path(__file__).resolve().parents[2]

class IrrigatorMusicTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.globals().SCRIPTS=str(ROOT/'mod/Tractor/scripts')
        self.lua.execute('''
package.path=SCRIPTS..'/?.lua;'..package.path
function net(v)return {value=function()return v end,set=function(self,n)v=n end}end
Music=require('aom_irrigator_music');Bank=require('aom_irrigator_music_bank')
function player(x)
 local p={x=x or 0,replica={},valid=true,tags={}}
 function p:IsValid()return self.valid end
 function p:HasTag(tag)return self.tags[tag]end
 p.Transform={GetWorldPosition=function()return p.x,0,0 end}
 return p
end
function tractor()
 local t={prefab='aom_tractor_chassis',valid=true}
 function t:IsValid()return self.valid end
 t._workstatus=net(true);t._water_net=net(10)
 t._atttype_net=net('irrigator');t._fuel=net(800)
 t._attachment=net({attachment_type='irrigator',IsValid=function()return true end})
 return t
end
owner=player();driver=player();t=tractor()
driver.replica.rider={GetMount=function()return t end}
AllPlayers={owner,driver};plays=0;kills=0;volumes={};active=false
owner.SoundEmitter={PlaySound=function(_,event,handle,volume)
 assert(event=='aom_irrigator_music/irrigator/lanhuacao' and handle==Music.HANDLE)
 plays=plays+1;active=true;volumes[#volumes+1]=volume
end,KillSound=function(_,handle)kills=kills+1;active=false end,
PlayingSound=function()return active end,
SetVolume=function(_,handle,v)volumes[#volumes+1]=v end}
controller=Music.New(owner)
function ready()
 Bank.available=true
 local assets=Music.Configure(true,'mod/',function()return true end,function(kind,path)return {kind,path}end)
 assert(#assets==2)
end
''')

    def run_lua(self,s): self.lua.execute(s)

    def test_packaged_bank_registers_real_resources_and_starts_player(self):
        self.lua.globals().bank_file_exists=lambda name: Path(name).is_file()
        self.lua.globals().MOD_ROOT=str(ROOT/'mod/Tractor')+'/'
        self.run_lua('''
assert(Bank.available)
local assets=Music.Configure(true,MOD_ROOT,function(path)return bank_file_exists(path)end,
 function(kind,path)return {kind=kind,path=path}end)
assert(#assets==2 and Music.ready and assets[1].kind=='SOUNDPACKAGE' and assets[2].kind=='SOUND')
controller:Update();assert(plays==1 and active)
''')

    def test_missing_bank_and_disabled_config_stay_silent(self):
        self.run_lua('''
Bank.available=false
assert(#Music.Configure(true,'mod/',function()error('must not read missing bank')end,function()end)==0)
controller:Update();assert(plays==0)
ready();assert(#Music.Configure(false,'mod/',function()return true end,function()end)==0)
controller:Update();assert(plays==0)
''')

    def test_partial_missing_assets_do_not_register_bank(self):
        self.run_lua('''
Bank.available=true
local assets=Music.Configure(true,'mod/',function(path)return string.find(path,'.fev',1,true)end,function()error('must not register incomplete bank')end)
assert(#assets==0 and not Music.ready);controller:Update();assert(plays==0)
''')

    def test_single_handle_near_multiple_tractors_and_distance_volume(self):
        self.run_lua('''
ready();controller:Update();controller:Update();assert(plays==1 and active)
local other=player(5);other.replica.rider={GetMount=function()return tractor()end}
AllPlayers[#AllPlayers+1]=other;controller:Update();assert(plays==1)
AllPlayers={owner,driver};driver.x=10;controller:Update();assert(volumes[#volumes]==.175)
driver.x=21;controller:Update();assert(not active and kills==1)
''')

    def test_client_plays_from_synced_attachment_type_without_inventory_entity(self):
        self.run_lua('''
t._attachment:set(nil);ready();controller:Update();assert(plays==1 and active)
t._fuel:set(0);controller:Update();assert(not active)
''')

    def test_work_off_empty_dismount_swap_remove_and_death_stop_music(self):
        self.run_lua('''
ready();controller:Update();t._workstatus:set(false);controller:Update();assert(not active)
t._workstatus:set(true);controller:Update();t._water_net:set(0);controller:Update();assert(not active)
t._water_net:set(10);controller:Update();driver.replica.rider.GetMount=function()return nil end
controller:Update();assert(not active)
driver.replica.rider.GetMount=function()return t end;controller:Update()
t._atttype_net:set('plow');controller:Update();assert(not active)
t._atttype_net:set('irrigator');controller:Update()
t.valid=false;controller:Update();assert(not active)
t.valid=true;controller:Update();owner.tags.playerghost=true;controller:Update();assert(not active)
owner.tags.playerghost=nil;controller:Update();controller:Stop();assert(not active)
''')

    def test_playback_and_volume_errors_are_contained_and_not_retried(self):
        self.run_lua('''
ready();owner.SoundEmitter.PlaySound=function()error('missing event')end
assert(pcall(controller.Update,controller));assert(controller.failed and not active)
controller:Update();assert(not active)
controller=Music.New(owner);owner.SoundEmitter.PlaySound=function()active=true;plays=plays+1 end
controller:Update();owner.SoundEmitter.SetVolume=function()error('audio device failed')end
assert(pcall(controller.Update,controller));assert(controller.failed and not active)
''')

    def test_missing_event_without_lua_error_disables_music(self):
        self.run_lua('''
ready();owner.SoundEmitter.PlaySound=function()plays=plays+1 end
controller:Update();controller:Update();assert(controller.failed and plays==1 and not active)
''')

    def test_music_failure_does_not_change_irrigation_result(self):
        from test_irrigator_flow import IrrigatorFlowTests
        flow=IrrigatorFlowTests();flow.setUp()
        flow.run_lua('''
local Music=require('aom_irrigator_music');Music.ready=true
local old=AllPlayers;AllPlayers={}
local controller=Music.New({IsValid=function()error('bad audio state')end})
controller:Update();assert(controller.failed)
fill(40);assert(Drive.WorkTile(inst,0,0))
assert(moisture(0,0)==100 and water_count()==36 and inst._fuel:value()==799 and inst.components.finiteuses.used==1)
AllPlayers=old
''')

class MusicBankArtifactTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0,str(ROOT/'tools'))
        from music_bank import inspect_pair
        self.inspect=inspect_pair
        self.fev=(ROOT/'mod/Tractor/sound/aom_irrigator_music.fev').read_bytes()
        self.fsb=(ROOT/'mod/Tractor/sound/aom_irrigator_music.fsb').read_bytes()

    def test_real_native_banks_and_source_pcm_match_exactly(self):
        info=self.inspect(self.fev,self.fsb)
        self.assertEqual(self.fev[0:4]+self.fev[8:12],b'RIFFFEV ')
        self.assertEqual(self.fsb[:4],b'FSB5')
        self.assertEqual((info['frames'],info['rate'],info['channels']),(800680,44100,2))
        with wave.open(str(ROOT/'assets/audio/lanhuacao_loop.wav')) as source:
            pcm=source.readframes(source.getnframes())
        self.assertEqual(info['pcm_sha256'],hashlib.sha256(pcm).hexdigest())

    def test_compiled_output_matches_looping_project_and_build_record(self):
        record=json.loads((ROOT/'assets/audio/fmod/build.json').read_text())
        project=ROOT/record['project']
        xml=ET.parse(project)
        event=xml.find('eventgroup/event')
        self.assertEqual(xml.findtext('name')+'/irrigator/'+event.findtext('name'),record['event'])
        self.assertEqual(event.findtext('oneshot'),'No')
        self.assertEqual(event.findtext('layer/sound/loopmode'),'0')
        self.assertEqual(event.findtext('layer/sound/loopcount2'),'-1')
        self.assertEqual(event.findtext('category'),'set_music')
        self.assertEqual(event.findtext('mode'),'x_2d')
        self.assertEqual(record['project_sha256'],hashlib.sha256(project.read_bytes()).hexdigest())
        for kind in ('fev','fsb'):
            self.assertEqual(record[kind+'_sha256'],hashlib.sha256(getattr(self,kind)).hexdigest())

    def test_corrupt_incomplete_and_mismatched_banks_are_rejected(self):
        for fev,fsb in ((self.fev[:-1],self.fsb),(self.fev,self.fsb[:-1]),
                        (b'RIFF'+self.fev[4:8]+b'WAVE'+self.fev[12:],self.fsb),
                        (self.fev,self.fsb[:36]+b'bad-hash'+self.fsb[44:])):
            with self.subTest(size=(len(fev),len(fsb))):
                with self.assertRaises(ValueError):self.inspect(fev,fsb)

if __name__=='__main__': unittest.main()
