"""实机排气/间隙反馈：六设备五视图连接点、动画bank与烟筒定位。"""
import json
from pathlib import Path
from zipfile import ZipFile
import unittest
from PIL import Image
import test_world_equipment as world
from driver_animation import parse_anim,name_hash

ROOT=Path(__file__).resolve().parents[2]
ART=ROOT/'assets/directional-v2'
LAYOUT=json.loads((ART/'mount-layout.json').read_text())
MASKS=[192,5,48,8,2]


class MountGeometryFlowTests(unittest.TestCase):
    setUp=world.WorldEquipmentTests.setUp
    run_lua=world.WorldEquipmentTests.run_lua

    def test_all_six_emit_from_native_chimney_position_while_moving_and_working(self):
        self.run_lua('''
local Drive=require('aom_drive');ride()
local store=t.components.aom_attachment_store
store.GetWater=function()return 40 end;store.GetSeedCount=function()return 10 end
store.GetFertilizerCount=function()return 10 end
Drive.WorkTile=function()return false end
player.AnimState.GetSymbolPosition=function(_,name)
 assert(name=='aom_driver_attachment_front');local x,_,z=player.Transform:GetWorldPosition()
 return x+1,8,z-2,true
end
local function puffs()
 local out={};for _,e in ipairs(ENTITIES)do if e.prefab=='aom_exhaust_puff' then out[#out+1]=e end end;return out
end
for _,name in ipairs({'aom_landclearer','aom_seeder','aom_irrigator','aom_fertilizer','aom_weeder','aom_harvester'})do
 local item=equipment(name);item.Transform:SetPosition(player.Transform:GetWorldPosition());assert(act(item))
 local before=#puffs();t:SetWorking(true)
 for i=1,6 do local x,_,z=player.Transform:GetWorldPosition();player.Transform:SetPosition(x+.1,0,z);Drive.TrackMovement(t)end
 assert(#puffs()==before+2,name)
 local puff=puffs()[#puffs()];local x,_,z=player.Transform:GetWorldPosition()
 assert(math.abs(puff.x-(x+1))<.000001 and puff.y==8 and puff.z==z-2)
 for i=1,10 do Drive.TrackMovement(t)end;assert(#puffs()==before+2)
 t:SetWorking(false);player.Transform:SetPosition(x+.1,0,z);Drive.TrackMovement(t);assert(#puffs()==before+2)
 assert(t:DetachAttachment(player));item:Remove()
end
''')

    def test_missing_driver_marker_uses_vehicle_marker_and_never_spawns_at_wrong_origin(self):
        self.run_lua('''
ride();local Motion=require('aom_vehicle_motion')
player.AnimState.GetSymbolPosition=function()return 0,0,0,false end
t.AnimState.GetSymbolPosition=function(_,name)assert(name=='attachment_front');return 12,9,14,true end
local spawned={};local spawn=SpawnPrefab
SpawnPrefab=function(name)local e=spawn(name);spawned[#spawned+1]=e;return e end
Motion.EmitExhaust(t);assert(#spawned==1 and spawned[1].x==12 and spawned[1].y==9 and spawned[1].z==14)
t.AnimState.GetSymbolPosition=function()return 0,0,0,false end
Motion.EmitExhaust(t);assert(#spawned==1)
''')

    def test_all_six_switch_banks_on_mount_detach_and_remount_without_losing_durability(self):
        self.run_lua('''
ride()
for _,name in ipairs({'aom_landclearer','aom_seeder','aom_irrigator','aom_fertilizer','aom_weeder','aom_harvester'})do
 local item=equipment(name);item.Transform:SetPosition(player.Transform:GetWorldPosition());assert(item.bank=='aom_attachment_shared')
 local uses=Durability.GetUses(item);assert(act(item) and item.bank=='aom_attachment_mounted')
 assert(t:DetachAttachment(player) and item.bank=='aom_attachment_shared')
 assert(item.parent==nil and item.persists and Durability.GetUses(item)==uses)
 player.Transform:SetPosition(item.Transform:GetWorldPosition());assert(act(item))
 assert(item.bank=='aom_attachment_mounted' and Durability.GetUses(item)==uses)
 item:Remove()
end
''')


class MountGeometryAssetTests(unittest.TestCase):
    def test_all_thirty_compiled_idle_hitch_centres_match_vehicle_connection_points(self):
        with ZipFile(ROOT/'mod/Tractor/anim/aom_attachment_shared.zip') as z:d=parse_anim(z.read('anim.bin'))
        for kind,hitches in LAYOUT['hitches'].items():
            for i,view in enumerate(LAYOUT['views']):
                with self.subTest(kind=kind,view=view):
                    a=next(a for a in d['animations'] if a['bank']==name_hash('aom_attachment_mounted') and a['name']==kind and a['facing']==MASKS[i])
                    with Image.open(ART/'sprites'/kind/(view+'.png')) as im:w,h=im.size
                    x=(hitches[i][0]-.5)*w;y=(hitches[i][1]-1)*h
                    # Rear implements are deliberately fully occluded in the
                    # frontal mounted view. Ground art and all other views must
                    # still contain their geometry; the front harvester stays visible.
                    hidden=kind in {'plow','seeder','irrigator','fertilizer','weeder'} and MASKS[i]==8
                    ground=next(v for v in d['animations'] if v['bank']==name_hash('aom_attachment_shared') and v['name']==kind and v['facing']==MASKS[i])
                    self.assertTrue(ground['frames'][0]['elements'])
                    if hidden:
                        self.assertEqual(a['frames'][0]['elements'],[])
                        continue
                    self.assertTrue(a['frames'][0]['elements'])
                    e=a['frames'][0]['elements'][0];m=e['matrix']
                    actual=(m[0]*x+m[2]*y+m[4],m[1]*x+m[3]*y+m[5])
                    uv=LAYOUT['tractor']['front' if kind=='harvester' else 'rear'][i]
                    with Image.open(ART/'sprites/tractor'/(view+'.png')) as im:tw,th=im.size
                    self.assertAlmostEqual(actual[0],(uv[0]-.5)*tw,places=4)
                    self.assertAlmostEqual(actual[1],(uv[1]-1)*th,places=4)

    def test_mounted_work_frames_and_streams_share_identical_translation(self):
        packages=[('aom_attachment_shared','aom_attachment_mounted',lambda n:n.split('_work_')[0]),
                  ('aom_attachment_water','aom_attachment_water_mounted',lambda n:'irrigator'),
                  ('aom_attachment_fx','aom_attachment_fx_mounted',lambda n:'fertilizer')]
        offsets={}
        for base,mounted,kindfn in packages:
            with ZipFile(ROOT/'mod/Tractor/anim'/(base+'.zip')) as z:d=parse_anim(z.read('anim.bin'))
            originals={(a['name'],a['facing']):a for a in d['animations'] if a['bank']==name_hash(base)}
            for a in d['animations']:
                if a['bank']!=name_hash(mounted):continue
                original=originals[a['name'],a['facing']];self.assertEqual(len(a['frames']),len(original['frames']))
                for f,o in zip(a['frames'],original['frames']):
                    kind=kindfn(a['name'])
                    hidden=kind in {'plow','seeder','irrigator','fertilizer','weeder'} and a['facing']==8
                    self.assertTrue(o['elements'],(base,a['name'],a['facing']))
                    if hidden:
                        self.assertEqual(f['elements'],[],(base,a['name'],a['facing']))
                        continue
                    self.assertEqual(len(f['elements']),len(o['elements']))
                    for e,oe in zip(f['elements'],o['elements']):
                        self.assertEqual(e['matrix'][:4],oe['matrix'][:4])
                        delta=tuple(e['matrix'][i]-oe['matrix'][i] for i in (4,5))
                        key=(kindfn(a['name']),a['facing']);previous=offsets.setdefault(key,delta)
                        for x,y in zip(delta,previous):self.assertAlmostEqual(x,y,places=4)

    def test_all_driver_sizes_have_chimney_markers_in_every_direction_and_motion_frame(self):
        names=['aom_tractor_driver','aom_tractor_driver_075','aom_tractor_driver_125','aom_tractor_driver_150','aom_tractor_chassis']
        points=[]
        for i,view in enumerate(LAYOUT['views']):
            with Image.open(ART/'sprites/tractor'/(view+'.png')) as im:w,h=im.size
            uv=LAYOUT['tractor']['exhaust'][i];points.append(((uv[0]-.5)*w,(uv[1]-1)*h))
        for name in names:
            with ZipFile(ROOT/'mod/Tractor/anim'/(name+'.zip')) as z:d=parse_anim(z.read('anim.bin'))
            marker=name_hash('attachment_front' if name=='aom_tractor_chassis' else 'aom_driver_attachment_front')
            seen=set()
            for a in d['animations']:
                for frame in a['frames']:
                    e=next((e for e in frame['elements'] if e['symbol']==marker),None)
                    if not e:continue
                    body=next(e for e in frame['elements'] if e['symbol'] in (name_hash('body'),name_hash('aom_cabin_front')))
                    x,y=points[MASKS.index(a['facing'])]
                    self.assertAlmostEqual(e['matrix'][4]-body['matrix'][4],x,places=4)
                    self.assertAlmostEqual(e['matrix'][5]-body['matrix'][5],y,places=4)
                    seen.add(a['facing'])
            self.assertEqual(seen,set(MASKS))


if __name__=='__main__':unittest.main()
