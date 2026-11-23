"""100机械耐久、半速、车尾即时卸载及整片规划预览的行为回归。"""
import unittest
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
import test_world_equipment as world
import test_dashboard as dashboard


class EquipmentUpdateTests(unittest.TestCase):
    setUp = world.WorldEquipmentTests.setUp
    run_lua = world.WorldEquipmentTests.run_lua

    def test_every_attachment_has_two_hundred_uses_and_preserves_old_durability_percentage(self):
        self.run_lua('''
for kind,def in pairs(require('aom_equipment_defs'))do
 local item=equipment(def.prefab)
 assert(Durability.GetUses(item)==200 and def.uses==200)
 for _,remaining in ipairs({0,60,100})do
  local old=clone(item:GetSaveRecord())
  old.data.aom_machine_max=nil
  if def.separate_uses then old.data.aom_machine_uses=remaining
  else old.data.finiteuses={uses=remaining} end
  local restored=SpawnSaveRecord(old)
  assert(Durability.GetUses(restored)==remaining*2)
  assert(Durability.GetUses(SpawnSaveRecord(clone(restored:GetSaveRecord())))==remaining*2)
  if kind=='irrigator' then assert(restored.components.finiteuses:GetUses()==100)end
 end
end
local water=equipment('aom_irrigator');assert(water.components.finiteuses.total==400)
''')

    def test_all_directions_use_front_for_harvester_and_rear_for_other_tools(self):
        self.run_lua('''
for _,driving in ipairs({false,true})do
 if driving then ride()end
 local source=driving and player or t
 for _,name in ipairs({'aom_landclearer','aom_seeder','aom_irrigator','aom_fertilizer','aom_weeder','aom_harvester'})do
  for angle=0,315,45 do
   source.Transform:SetPosition(10,0,-12);source.Transform:SetRotation(angle)
   local item=equipment(name);assert(t:AttachAttachment(nil,item))
   if driving then assert(click(item)==ACTION_DEFS.AOM_DETACH and act(item))
   else assert(t:DetachAttachment(nil))end
   local x,_,z=item.Transform:GetWorldPosition();local a=angle*math.pi/180
   local sign=name=='aom_harvester' and 1 or -1
   assert(math.abs(x-(10+sign*3*math.cos(a)))<1e-6,name)
   assert(math.abs(z-(-12-sign*3*math.sin(a)))<1e-6,name)
   assert(source.Transform:GetRotation()==angle)
   item:Remove()
  end
 end
end
player.Transform:SetPosition(0,0,0);player.Transform:SetRotation(0)
for _,name in ipairs({'aom_seeder','aom_harvester'})do
 local item=equipment(name);assert(t:AttachAttachment(nil,item))
 -- 只有挂点反面可用时不能绕车卸载。
 TheWorld.Map.IsPassableAtPoint=function(_,x,y,z)return name=='aom_harvester' and x<=0 or name=='aom_seeder' and x>=0 end
 assert(not t:DetachAttachment(player) and t:GetAttachment()==item)
 assert(player.Transform:GetRotation()==0)
 TheWorld.Map.IsPassableAtPoint=function()return true end
 assert(t:DetachAttachment(player));item:Remove()
end
''')

    def test_detach_state_executes_immediately_on_server_and_client_without_facing_target(self):
        self.run_lua('''
ride();local item=equipment('aom_harvester');assert(t:AttachAttachment(nil,item))
assert(ACTION_DEFS.AOM_DETACH.do_not_locomote and not ACTION_DEFS.AOM_ATTACH.do_not_locomote)
player.Transform:SetRotation(123)
player.FacePoint=function()error('detach must not face target')end
player.PerformBufferedAction=function()assert(act(item))end
SG_STATES.wilson.aom_detach.onenter(player)
assert(t:GetAttachment()==nil and player.Transform:GetRotation()==123)
local preview=false;player.PerformPreviewBufferedAction=function()preview=true end
SG_STATES.wilson_client.aom_detach.onenter(player)
assert(preview and player.Transform:GetRotation()==123)
''')


class FullPlanPreviewTests(unittest.TestCase):
    setUp = dashboard.DashboardTests.setUp
    run_lua = dashboard.DashboardTests.run_lua

    def test_entire_plan_renders_on_client_and_reuses_remaining_markers_then_cleans_on_dismount(self):
        self.run_lua('''
attach('aom_seeder');t:CycleSeedStrategy(player)
local slots={}
for tile=0,63 do for s=0,8 do
 local x,z=tile*4+(s%3-1)*4/3,(math.floor(s/3)-1)*4/3
 slots[#slots+1]={x=x,z=z,cx=tile*4,cz=0,crop='potato',index=#slots+1}
end end
local tiles={};for tile=0,63 do tiles[#tiles+1]={x=tile*4,z=0}end
t._block={dynamic=true,tiles=tiles,slots=slots,total=576,done=0,season='autumn',completed={}}
local Block=require('aom_block_plan');Block.Sync(t)
local decoded=Block.Decode(t._plan_net:value());assert(decoded and #decoded.slots==576 and #decoded.tiles==64)
local old=t.components;t.components={};hud:Refresh(t);t.components=old
assert(#hud._plan_markers==576)
local first,second=hud._plan_markers[1],hud._plan_markers[2]
assert(first.layer==LAYER_BACKGROUND and first.sort_order==3 and first.y==0)
assert(not first.persists and first:HasTag('FX') and not first:HasTag('soil') and not first.components.farmplantable)
hud:Refresh(t);assert(hud._plan_markers[1]==first)
t._block.completed[1]=true;t._block.done=1;Block.Sync(t);hud:Refresh(t)
assert(#hud._plan_markers==575 and not first:IsValid() and hud._plan_markers[1]==second)
hud:Refresh(nil);assert(not second:IsValid() and hud._plan_markers==nil)
assert(Block.Decode('D5;577;0;autumn;0;0;')==nil)
assert(Block.Decode('D5;2;0;autumn;0;0;0,0,potato,0,0|0,0,potato,0,0')==nil)
''')

    def test_ready_message_and_preview_precede_first_seed_and_cancel_is_safe(self):
        self.run_lua('''
attach('aom_seeder');t:CycleSeedStrategy(player)
TheWorld.Map.GetTileCoordsAtPoint=function(_,x,y,z)return center(x)/4,center(z)/4 end
for _,kind in ipairs({'tomato','potato'})do
 local seed=SpawnPrefab(kind..'_seeds');seed.components.stackable:SetStackSize(8)
 assert(t.components.container:GiveItem(seed))
end
for x=-1,1 do for z=-1,1 do SpawnPrefab('farm_soil').Transform:SetPosition(x*4/3,0,z*4/3)end end
local queue={};t.DoTaskInTime=function(_,delay,fn)queue[#queue+1]={delay=delay,fn=fn}end
t:SetWorking(true);require('aom_drive').TrackMovement(t)
while not t._block do assert(#queue>0);table.remove(queue,1).fn()end
assert(t._block.done==0 and t.components.aom_attachment_store:GetSeedCount()==16)
assert(require('aom_work_status').Read(t)=='PLAN_READY')
assert(queue[1].delay==2);hud:Refresh(t);assert(#hud._plan_markers==8)
require('aom_drive').WorkTile(t,0,0);assert(t._block.done==0)
t:SetWorking(false);table.remove(queue,1).fn()
assert(t._block.done==0 and not t._working)
t:SetWorking(true);require('aom_drive').TrackMovement(t)
assert(t._block.done==8)
''')


class CraftIconTests(unittest.TestCase):
    def test_craft_atlas_uses_seven_separate_128_pixel_cells(self):
        root=Path(__file__).resolve().parents[2]
        tex=(root/'mod/Tractor/images/aom_tractor_icons.tex').read_bytes()
        self.assertEqual(tex[:4],b'KTEX')
        width,height=struct.unpack_from('<HH',tex,8)
        self.assertEqual((width,height),(1024,128))
        atlas=ET.parse(root/'mod/Tractor/images/aom_tractor_icons.xml')
        elements=atlas.findall('.//Element')
        self.assertEqual(len(elements),7)
        for i,e in enumerate(elements):
            self.assertAlmostEqual(float(e.attrib['u1'])*width,i*128)
            self.assertAlmostEqual(float(e.attrib['u2'])*width,(i+1)*128)
            self.assertEqual((e.attrib['v1'],e.attrib['v2']),('0','1'))
