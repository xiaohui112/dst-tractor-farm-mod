"""执行原版上下车组件验证驾驶显示挂接；二进制合成保留骑乘时间线与朝向。"""
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from zipfile import ZipFile
import test_native_riding as riding

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from driver_animation import parse_anim,write_anim,name_hash,merge_rider,build_symbols,build_driver,native_riding_bank


class DriverVisualRuntimeTests(unittest.TestCase):
    def setUp(self):
        engine=riding.NativeRidingTests(methodName='runTest');engine.setUp();self.lua=engine.lua
        self.lua.execute('''
Visual=require('aom_driver_visual');VisualBank=require('aom_driver_visual_bank')
VisualBank.available=true;assert(Visual.Configure('test/',function()return true end))
p.build='character_skin';p.visual_symbols.swap_hat={build='hat_skin',symbol='hat'}
''')

    def test_native_mount_uses_driver_bank_and_preserves_character_and_hat_builds(self):
        self.lua.execute('''
assert(ACTIONS.MOUNT.fn({doer=p,target=t}))
assert(p.bank=='aom_tractor_driver' and p.build=='character_skin')
assert(p.visual_builds.aom_tractor_cabin and not p.visual_builds.beefalo_build)
assert(p.visual_symbols.swap_hat.build=='hat_skin')
assert(t.hidden and p.sg.current=='mount' and p.components.rider:GetMount()==t)
''')

    def test_native_actual_dismount_restores_bank_and_only_clears_own_overrides(self):
        self.lua.execute('''
ACTIONS.MOUNT.fn({doer=p,target=t});ACTIONS.DISMOUNT.fn({doer=p,target=p})
assert(p.sg.current=='dismount' and p.bank=='aom_tractor_driver')
p.components.rider:ActualDismount()
assert(p.bank=='wilson' and p.build=='character_skin' and not p.visual_builds.aom_tractor_cabin)
assert(p.visual_symbols.swap_hat.build=='hat_skin' and not p.visual_symbols.aom_driver_attachment_front)
assert(not t.hidden and t._aom_driver_animstate==nil)
''')

    def test_attachment_changes_update_only_driver_mount_symbols(self):
        self.lua.execute('''
t._attachment_type='harvester';ACTIONS.MOUNT.fn({doer=p,target=t})
assert(p.visual_symbols.aom_driver_attachment_front.symbol=='empty')
assert(p.visual_symbols.aom_driver_attachment_rear.symbol=='empty')
t._attachment_type='irrigator';Visual.UpdateAttachment(t,p.AnimState)
assert(p.visual_symbols.aom_driver_attachment_front.symbol=='empty')
assert(p.visual_symbols.aom_driver_attachment_rear.symbol=='empty')
assert(p.visual_symbols.swap_hat.build=='hat_skin')
''')

    def test_other_mounts_and_missing_driver_asset_keep_vanilla_rendering(self):
        self.lua.execute('''
VisualBank.available=false;assert(not Visual.Configure('test/',function()return true end))
ACTIONS.MOUNT.fn({doer=p,target=t})
assert(p.bank=='wilsonbeefalo' and not p.visual_builds.aom_tractor_cabin)
p.components.rider:ActualDismount()
VisualBank.available=true;assert(not Visual.Configure('test/',function()return false end))
''')


class DriverAnimationBuildTests(unittest.TestCase):
    def setUp(self):
        with ZipFile(ROOT/'mod/Tractor/anim/aom_tractor_chassis.zip') as archive:
            self.raw=archive.read('anim.bin');self.build=archive.read('build.bin');self.texture=archive.read('atlas-0.tex')
        self.config=json.loads((ROOT/'assets/driver/seat-layout.json').read_text())
        self.native={'strings':{},'animations':[]}
        for name in ['headbase','torso','body','footstep','wilsonbeefalo']:
            self.native['strings'][name_hash(name)]=name
        for name in ['idle_loop','mount','dismount','run_pre','run_loop','run_pst']:
            frames=[]
            for i in range(2):
                frames.append({'bbox':(0.,-100.,200.,250.),'events':[name_hash('footstep')],
                               'elements':[self.element('headbase',i,-170-i,-1),self.element('torso',0,-120,0),self.element('body',0,0,1)]})
            self.native['animations'].append({'name':name,'bank':name_hash('wilsonbeefalo'),'facing':255,'rate':30.,'frames':frames})
        self.cabin={'strings':{},'animations':[]}
        for name in ['aom_cabin_back','aom_cabin_front','aom_driver_attachment_rear','aom_driver_attachment_front','aom_tractor_cabin']:
            self.cabin['strings'][name_hash(name)]=name
        for index,mask in enumerate([5,48,192]):
            elements=[self.element(n,0,0,z) for z,n in enumerate(['aom_cabin_back','aom_cabin_front','aom_driver_attachment_rear','aom_driver_attachment_front'])]
            for e in elements:e['frame']=index if e['symbol'] in (name_hash('aom_cabin_back'),name_hash('aom_cabin_front')) else 0
            self.cabin['animations'].append({'name':'idle','bank':name_hash('aom_tractor_cabin'),'facing':mask,'rate':40.,
                                            'frames':[{'bbox':(0.,-150.,400.,400.),'events':[],'elements':elements}]})

    @staticmethod
    def element(name,x,y,z):
        return {'symbol':name_hash(name),'frame':0,'layer':name_hash(name),'matrix':[1.,0.,0.,1.,float(x),float(y)],'z':float(z)}

    def test_native_anim_v4_roundtrip_preserves_real_animation_data(self):
        parsed=parse_anim(self.raw)
        self.assertEqual(parse_anim(write_anim(parsed)),parsed)
        with self.assertRaises(ValueError):parse_anim(self.raw[:-1])
        self.assertIn(name_hash('body'),build_symbols(self.build)[1])

    def test_composition_preserves_native_names_frames_events_and_six_facing(self):
        before=copy.deepcopy(self.native)
        result=merge_rider(self.native,self.cabin,{name_hash('body')},self.config)
        self.assertEqual(self.native,before)
        def f32(value):
            if isinstance(value,float):return struct.unpack('<f',struct.pack('<f',value))[0]
            if isinstance(value,dict):return {k:f32(v) for k,v in value.items()}
            if isinstance(value,list):return [f32(v) for v in value]
            if isinstance(value,tuple):return tuple(f32(v) for v in value)
            return value
        self.assertEqual(parse_anim(write_anim(result)),
                         {'animations':f32(result['animations']),'strings':f32(result['strings'])})
        self.assertEqual({a['name'] for a in result['animations']},{a['name'] for a in self.native['animations']})
        for name in ['idle_loop','mount','dismount','run_loop']:
            variants=[a for a in result['animations'] if a['name']==name]
            self.assertEqual(set(a['facing'] for a in variants),{5,48,192,2,8})
            for a in variants:
                self.assertEqual(a['rate'],30.)
                self.assertEqual(len(a['frames']),2)
                self.assertEqual(a['frames'][0]['events'],[name_hash('footstep')])
                self.assertNotIn(name_hash('body'),[e['symbol'] for e in a['frames'][0]['elements']])
                for f in a['frames']:
                    z={e['symbol']:e['z'] for e in f['elements']}
                    self.assertLess(z[name_hash('aom_cabin_front')],z[name_hash('headbase')])
                    self.assertLess(z[name_hash('headbase')],z[name_hash('aom_cabin_back')])

    def test_direction_specific_seat_anchor_and_original_bobbing_are_preserved(self):
        result=merge_rider(self.native,self.cabin,{name_hash('body')},self.config)
        for a in [a for a in result['animations'] if a['name']=='idle_loop']:
            view='side' if a['facing']==5 else 'upside' if a['facing'] in (48,2) else 'downside'
            head=[next(e for e in f['elements'] if e['symbol']==name_hash('headbase')) for f in a['frames']]
            self.assertEqual(head[0]['matrix'][4:6],self.config['views'][view]['neck'])
            self.assertAlmostEqual(head[1]['matrix'][4]-head[0]['matrix'][4],self.config['driver_scale'])
            self.assertAlmostEqual(head[1]['matrix'][5]-head[0]['matrix'][5],-self.config['driver_scale'])

    def test_missing_native_idle_or_cabin_direction_is_rejected(self):
        bad=copy.deepcopy(self.native);bad['animations']=[a for a in bad['animations'] if a['name']!='idle_loop']
        with self.assertRaises(ValueError):merge_rider(bad,self.cabin,set(),self.config)
        bad=copy.deepcopy(self.cabin);bad['animations'].pop()
        with self.assertRaises(ValueError):merge_rider(self.native,bad,set(),self.config)

    def test_full_windows_builder_reads_native_sources_and_enables_only_completed_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);game=root/'game';mod=root/'mod';(game/'data/anim').mkdir(parents=True)
            (mod/'anim').mkdir(parents=True);(mod/'scripts').mkdir()
            with ZipFile(game/'data/anim/player_mount_basic.zip','w') as archive:archive.writestr('anim.bin',write_anim(self.native))
            with ZipFile(game/'data/anim/beefalo_build.zip','w') as archive:archive.writestr('build.bin',self.build)
            size=struct.unpack_from('<I',self.build,16)[0];name=b'aom_tractor_cabin'
            # 复用实际 BILD 的帧数据，换成四个 cabin 符号，保证构建端也校验完整符号集。
            from driver_animation import Reader
            reader=Reader(self.build);reader.read(16);reader.string()
            atlas_count=reader.unpack('I')[0]
            for _ in range(atlas_count):reader.string()
            begin=reader.pos
            count=reader.unpack('2I')[1];frame_data=reader.read(count*32)
            # 测试仅用 build_symbols 所需的结构；texture 仍为真实 KTEX。
            cabin_build=b'BILD'+struct.pack('<3I',6,4,count*4)+struct.pack('<I',len(name))+name+struct.pack('<I',1)+struct.pack('<I',11)+b'atlas-0.tex'
            for symbol in ['aom_cabin_back','aom_cabin_front','aom_driver_attachment_rear','aom_driver_attachment_front']:
                cabin_build+=struct.pack('<2I',name_hash(symbol),count)+frame_data
            with ZipFile(mod/'anim/aom_tractor_cabin.zip','w') as archive:
                archive.writestr('anim.bin',write_anim(self.cabin));archive.writestr('build.bin',cabin_build);archive.writestr('atlas-0.tex',self.texture)
            target=build_driver(str(game),str(mod),str(ROOT/'assets/driver/seat-layout.json'))
            with ZipFile(target) as archive:
                self.assertEqual(build_symbols(archive.read('build.bin'))[0],'aom_tractor_cabin')
                self.assertTrue(all(a['bank']==name_hash('aom_tractor_driver') for a in parse_anim(archive.read('anim.bin'))['animations']))
            self.assertIn('available=true',(mod/'scripts/aom_driver_visual_bank.lua').read_text())
            report=json.loads((mod/'Driver-Build-Report.json').read_text())
            self.assertEqual(report['native_sources'],['player_mount_basic.zip'])

    def test_databundle_native_asset_discovery(self):
        import io
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data/databundles').mkdir(parents=True)
            buf=io.BytesIO()
            with ZipFile(buf,'w') as archive:archive.writestr('anim.bin',write_anim(self.native))
            with ZipFile(root/'data/databundles/anim.zip','w') as archive:archive.writestr('anim/player_mount_basic.zip',buf.getvalue())
            native,sources,conflicts=native_riding_bank(str(root))
            self.assertEqual(len(native['animations']),6)
            self.assertEqual(sources,['anim/player_mount_basic.zip'])
            self.assertEqual(conflicts,[])

    def test_riderless_native_frames_are_reported_instead_of_aborting(self):
        native=copy.deepcopy(self.native)
        frames=[{'bbox':(0.,-100.,200.,250.),'events':[],
                 'elements':[self.element('body',0,0,1)]} for _ in range(2)]
        native['animations'].append({'name':'sink','bank':name_hash('wilsonbeefalo'),'facing':255,'rate':30.,'frames':frames})
        result=merge_rider(native,self.cabin,{name_hash('body')},self.config)
        self.assertEqual(result['frames_without_driver'],
                         ['sink/192','sink/2','sink/48','sink/5','sink/8'])
        sink=[a for a in result['animations'] if a['name']=='sink']
        self.assertEqual({a['facing'] for a in sink},{5,48,192,2,8})
        for a in sink:
            for f in a['frames']:
                # 没有人物层时仍保留驾驶室四层，避免整条时间线崩掉。
                self.assertEqual({e['symbol'] for e in f['elements']},
                                 {name_hash('aom_cabin_back'),name_hash('aom_cabin_front'),
                                  name_hash('aom_driver_attachment_rear'),name_hash('aom_driver_attachment_front')})

    def test_duplicate_native_sentinel_animations_keep_first_copy_and_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data/anim').mkdir(parents=True)
            with ZipFile(root/'data/anim/player_mount.zip','w') as archive:archive.writestr('anim.bin',write_anim(self.native))
            other={'strings':{},'animations':[copy.deepcopy(self.native['animations'][1])]}
            other['animations'][0]['frames'][0]['events']=[]
            with ZipFile(root/'data/anim/player_mount_extra.zip','w') as archive:archive.writestr('anim.bin',write_anim(other))
            native,sources,conflicts=native_riding_bank(str(root))
            self.assertEqual(sorted(sources),['player_mount.zip','player_mount_extra.zip'])
            self.assertEqual(len(native['animations']),6)
            self.assertEqual(conflicts,['mount/255'])
            self.assertEqual(native['animations'][1]['frames'][0]['events'],[name_hash('footstep')])

if __name__=='__main__':unittest.main()
