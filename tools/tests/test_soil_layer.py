"""真实原版土坑与本地预览共用地面层，不遮挡长挂件，不改动农业行为。"""
import unittest
import test_world_equipment as world


class SoilLayerTests(unittest.TestCase):
    setUp = world.WorldEquipmentTests.setUp
    run_lua = world.WorldEquipmentTests.run_lua

    def test_real_native_soil_is_grounded_on_host_and_remote_client(self):
        self.run_lua('''
local native=dofile(REF..'/farm_soil.lua')
local create=CreateEntity
CreateEntity=function()
 local inst=create()
 inst.SetDeploySmartRadius=function()end
 inst.SetPhysicsRadiusOverride=function()end
 return inst
end
for _,master in ipairs({true,false})do
 TheWorld.ismastersim=master
 local soil=native.fn();soil.Transform:SetPosition(2,0,-3)
 local animation=soil.animation
 local save,load=soil.OnSave,soil.OnLoad
 PREFAB_POST_FNS.farm_soil(soil)
 assert(soil.layer==LAYER_BACKGROUND and soil.sort_order==2)
 assert(soil:HasTag('soil') and not soil:HasTag('NOCLICK') and not soil:HasTag('NOBLOCK'))
 assert(soil.animation==animation and soil.OnSave==save and soil.OnLoad==load)
 assert(soil.x==2 and soil.y==0 and soil.z==-3)
 assert(next(soil.components)==nil)
 if master then
  local data={};soil:OnSave(data);assert(data.broken==false)
  soil:OnLoad({broken=true})
  assert(soil.layer==LAYER_BACKGROUND and soil.sort_order==2 and soil.animation=='collapse_idle')
  assert(soil:HasTag('NOCLICK') and soil:HasTag('NOBLOCK'))
 end
 soil:Remove()
end
TheWorld.ismastersim=true
''')

    def test_normal_spawn_uses_post_init_and_does_not_raise_vehicle_or_ground_equipment(self):
        self.run_lua('''
ride();local item=equipment('aom_seeder');assert(t:AttachAttachment(nil,item))
local soil=SpawnPrefab('farm_soil')
assert(soil.layer==LAYER_BACKGROUND and soil.sort_order==2)
assert(t.layer==nil and player.layer==nil and item.layer==nil)
assert(t:DetachAttachment(player) and item.layer==nil)
''')
