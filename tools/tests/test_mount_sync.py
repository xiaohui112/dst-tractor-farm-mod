"""实机挂载反馈：父子变换连续跟随、角色切换、卸载保护与收割机侧向。"""
from pathlib import Path
from zipfile import ZipFile
import unittest
import test_world_equipment as world
from driver_animation import parse_anim

ROOT=Path(__file__).resolve().parents[2]


class MountSyncTests(unittest.TestCase):
    setUp=world.WorldEquipmentTests.setUp
    run_lua=world.WorldEquipmentTests.run_lua

    def test_all_six_move_turn_and_teleport_with_parent_without_sampling(self):
        self.run_lua('''
ride()
for _,name in ipairs({'aom_landclearer','aom_seeder','aom_irrigator','aom_fertilizer','aom_weeder','aom_harvester'})do
 local item=equipment(name);item.Transform:SetPosition(player.Transform:GetWorldPosition());assert(act(item))
 assert(item.parent==player and not item.persists and not item.physics_active)
 local d=item.attachment_type=='harvester' and .025 or -.025
 assert(item.bank=='aom_attachment_mounted')
 assert(item.x==d and item.y==0 and item.z==0 and item.rotation==0)
 for _,angle in ipairs({0,45,90,135,180,225,270,315})do
  player.Transform:SetPosition(80+angle,0,-30);player.Transform:SetRotation(angle)
  local x,y,z=item.Transform:GetWorldPosition() -- 不调用UpdateVisual，跟随应立即生效。
  assert(math.abs(x-(80+angle+d*math.cos(angle*math.pi/180)))<.000001)
  assert(math.abs(z-(-30-d*math.sin(angle*math.pi/180)))<.000001 and y==0)
  assert(Mount.Rotation(item)==angle and item.x==d and item.rotation==0)
 end
 assert(t:DetachAttachment(player));item:Remove()
end
''')

    def test_handoff_between_ground_vehicle_and_two_riders_is_immediate(self):
        self.run_lua('''
local item=equipment('aom_harvester');assert(t:AttachAttachment(nil,item))
assert(item.parent==t)
ride();assert(item.parent==player)
player.components.rider:ActualDismount();assert(item.parent==t and item:IsValid())
local other=make_player();assert(ACTIONS.MOUNT.fn({doer=other,target=t}))
assert(item.parent==other)
other.Transform:SetPosition(40,0,40)
local x,_,z=item.Transform:GetWorldPosition();assert(x==40.025 and z==40)
assert(t:DetachAttachment(other));assert(item.parent==nil and item.persists)
local before={item.Transform:GetWorldPosition()}
other.Transform:SetPosition(100,0,100);local after={item.Transform:GetWorldPosition()}
assert(before[1]==after[1] and before[3]==after[3])
''')

    def test_parent_removal_does_not_delete_the_attachment(self):
        self.run_lua('''
local item=equipment('aom_irrigator');ride();assert(act(item))
item.components.finiteuses:SetUses(17);item._aom_machine_uses=23
player:Remove()
assert(item:IsValid() and item.parent==nil and item.persists)
assert(item.components.finiteuses:GetUses()==17 and item._aom_machine_uses==23)
''')

    def test_blocked_detach_retains_parent_then_retry_restores_world_rotation(self):
        self.run_lua('''
local item=equipment('aom_harvester');ride();assert(act(item))
player.Transform:SetRotation(90)
local free=Mount.FreePosition;Mount.FreePosition=function()return nil end
assert(not t:DetachAttachment(player) and item.parent==player and not item.persists)
Mount.FreePosition=free;assert(t:DetachAttachment(player))
assert(item.parent==nil and item.rotation==90 and item.persists and item.physics_active)
assert(not item._aom_parent_removed and not item._aom_visual_parent)
''')

    def test_clients_do_not_write_replicated_parent_or_transform(self):
        self.run_lua('''
ride();TheWorld.ismastersim=false
local item=equipment('aom_harvester');item._aom_vehicle:set(t)
item.entity.SetParent=function()error('client parent mutation')end
item.Transform.SetPosition=function()error('client position mutation')end
item.Transform.SetRotation=function()error('client rotation mutation')end
Mount.UpdateVisual(item)
assert(not item._aom_visual_parent and not item.physics_active)
''')

    def test_front_offset_scales_consistently_for_all_four_model_options(self):
        self.run_lua('''
for _,scale in ipairs({1.875,2.5,3.125,3.75})do
 local old=package.loaded.aom_model_scale;package.loaded.aom_model_scale=scale
 local item=equipment('aom_harvester');assert(t:AttachAttachment(nil,item))
 assert(item.x==scale*.01 and item.bank=='aom_attachment_mounted')
 local x,_,_,_,origin=Mount.WorkPosition(t)
 assert(math.abs((x-origin)/scale-1.95/2.5)<1e-9)
 assert(t:DetachAttachment(nil));item:Remove();package.loaded.aom_model_scale=old
end
''')


class MountAssetAndHudTests(unittest.TestCase):
    def test_harvester_side_and_front_diagonal_face_forward_in_every_frame(self):
        with ZipFile(ROOT/'mod/Tractor/anim/aom_attachment_shared.zip') as z:
            animations=parse_anim(z.read('anim.bin'))['animations']
        names=set()
        for a in animations:
            if not a['name'].startswith('harvester'):continue
            names.add(a['name'])
            for frame in a['frames']:
                for element in frame['elements']:
                    if a['facing']in (5,192):self.assertLess(element['matrix'][0],0,a['name'])
                    else:self.assertGreater(element['matrix'][0],0,a['name'])
        self.assertEqual(names,{'harvester','harvester_work_pre','harvester_work_loop','harvester_work_pst'})

    def test_no_attachment_has_a_permanent_status_strip(self):
        import test_dashboard as dashboard
        engine=dashboard.DashboardTests();engine.setUp()
        engine.run_lua('''
for _,kind in ipairs({'harvester','weeder','plow','irrigator','fertilizer','seeder'})do
 t._atttype_net:set(kind);hud:Refresh(t)
 assert(hud.strip==nil)
 for _,key in ipairs(hud.order)do assert(hud.badges[key]:IsVisible())end
end
''')


if __name__=='__main__':unittest.main()
