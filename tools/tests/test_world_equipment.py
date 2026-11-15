"""独立世界设备：真实 Mod / 容器 / 骑乘 / 耐久 / 存档与动作流程。"""
import unittest
import test_lifecycle_flow as lifecycle


class WorldEquipmentTests(unittest.TestCase):
    def setUp(self):
        engine=lifecycle.LifecycleFlowTests();engine.setUp();self.lua=engine.lua
        self.lua.execute('''
kit:Remove()
t=SpawnPrefab('aom_tractor_chassis')
Mount=require('aom_attachment_mount');Durability=require('aom_durability')
function ride()
 assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
end
function equipment(name)
 local item=SpawnPrefab(name);item.Transform:SetPosition(2,0,0);return item
end
function click(item)
 local actions={};SCENE_HOOKS.inspectable(item,player,actions,true)
 return actions[1]
end
function act(item)
 local action=click(item)
 return action and action.fn({doer=player,target=item})
end
''')

    def run_lua(self,s):self.lua.execute(s)

    def test_all_seven_recipes_build_world_prefabs_with_real_placement_previews(self):
        self.run_lua('''
for _,name in ipairs({'aom_tractor_chassis','aom_landclearer','aom_seeder','aom_irrigator','aom_fertilizer','aom_weeder','aom_harvester'})do
 local recipe=RECIPE_RECORDS[name]
 assert(recipe.product==name and recipe.placer==name..'_placer' and RECIPE_TECH[name]==TECH.SCIENCE_TWO)
 local built=SpawnPrefab(recipe.product)
 assert(not built.components.inventoryitem and not built.components.deployable)
 local preview=SpawnPrefab(recipe.placer);assert(preview.components.placer)
 assert(preview.orientation~=ANIM_ORIENTATION.OnGround and preview.facing_count==8)
end
''')

    def test_all_recipes_share_native_gardening_category_and_characteristic_materials(self):
        self.run_lua('''
local expected={
 aom_tractor_chassis={gears=4,transistor=3,boards=6,flint=8},
 aom_landclearer={boards=6,rope=4,flint=16,cutstone=4},
 aom_seeder={boards=6,rope=4,seeds=20,gears=1},
 aom_irrigator={boards=6,rope=4,waterballoon=6,ice=12},
 aom_fertilizer={boards=6,rope=4,fertilizer=1,compost=6},
 aom_weeder={boards=4,rope=4,twigs=16,flint=12},
 aom_harvester={boards=8,rope=4,flint=16,gears=2},
}
for name,ingredients in pairs(expected)do
 local filters=RECIPE_FILTERS[name]
 assert(#filters==1 and filters[1]=='GARDENING',name)
 local actual=RECIPE_INGREDIENTS[name];assert(#actual==4,name)
 for _,v in ipairs(actual)do assert(ingredients[v.type]==v.amount,name..':'..v.type)end
end
for _,v in ipairs(RECIPE_INGREDIENTS.aom_fertilizer)do
 if v.type=='fertilizer' then assert(v.deconstruct==true)end
end
''')

    def test_sixteen_cargo_slots_stay_available_with_independent_attached_equipment(self):
        self.run_lua('''
local tool=equipment('aom_seeder');ride();assert(act(tool))
for i=1,15 do assert(t.components.container:GiveItem(SpawnPrefab('gears'),i))end
assert(t:GetAttachment()==tool and t.components.container:GetNumSlots()==15)
assert(t.components.container:GetItemInSlot(1).prefab=='gears')
assert(not t.components.container:CanTakeItemInSlot(tool,1))
assert(not t.components.container:GiveItem(tool,1,nil,false))
assert(Mount.Owner(tool)==t and not tool.persists and not tool.physics_active)
''')

    def test_right_click_world_device_mounts_then_right_click_attached_device_unmounts(self):
        self.run_lua('''
local tool=equipment('aom_landclearer');local actions={}
SCENE_HOOKS.inspectable(tool,player,actions,true);assert(#actions==0)
ride();assert(click(tool)==ACTION_DEFS.AOM_ATTACH and act(tool))
assert(t:GetAttachment()==tool and t._atttype_net:value()=='plow')
assert(ACTION_DEFS.AOM_ATTACH.strfn({target=tool})=='DETACH')
assert(act(tool) and player.components.rider:GetMount()==t)
assert(t:GetAttachment()==nil and Mount.Owner(tool)==nil and tool.persists and tool.physics_active)
assert(not tool.components.inventoryitem and tool:IsValid())
''')

    def test_left_click_never_picks_equipment_into_player_or_cargo(self):
        self.run_lua('''
local tool=equipment('aom_seeder');local actions={};ride()
SCENE_HOOKS.inspectable(tool,player,actions,false);assert(#actions==0)
assert(tool.components.inventoryitem==nil and not tool:HasTag('_inventoryitem'))
assert(not t.components.container:GiveItem(tool,2,nil,false))
assert(tool:IsValid() and Mount.Owner(tool)==nil and tool.persists)
''')

    def test_only_actual_driver_can_mount_nearby_available_equipment(self):
        self.run_lua('''
local tool=equipment('aom_seeder')
assert(not ACTION_DEFS.AOM_ATTACH.fn({doer=player,target=tool}))
ride();tool.Transform:SetPosition(30,0,0);assert(not act(tool))
tool.Transform:SetPosition(2,0,0);assert(act(tool))
local second=equipment('aom_weeder');assert(not act(second) and t:GetAttachment()==tool)
local other=make_player();other.components.rider.IsRiding=function()return true end
other.components.rider.GetMount=function()return t end
assert(not ACTION_DEFS.AOM_ATTACH.fn({doer=other,target=tool}))
assert(Mount.Owner(tool)==t and Mount.Owner(second)==nil)
''')

    def test_all_six_break_to_world_reject_mount_until_repaired_then_reuse(self):
        self.run_lua('''
ride()
for _,name in ipairs({'aom_landclearer','aom_seeder','aom_weeder','aom_harvester','aom_irrigator','aom_fertilizer'})do
 local tool=equipment(name);assert(act(tool))
 if tool.attachment_type=='irrigator' or tool.attachment_type=='fertilizer' then tool._aom_machine_uses=1
 else tool.components.finiteuses:SetUses(1)end
 t:SetWorking(true);Durability.UseAttachment(t,tool)
 assert(tool:IsValid() and Durability.GetUses(tool)==0 and t:GetAttachment()==nil and not t._working)
 assert(Mount.Owner(tool)==nil and tool.persists and not act(tool))
 assert(Durability.RepairAttachment(tool) and Durability.GetUses(tool)==10)
 player.Transform:SetPosition(tool.Transform:GetWorldPosition())
 assert(act(tool) and t:GetAttachment()==tool)
 assert(act(tool) and t:GetAttachment()==nil)
 tool:Remove();player.Transform:SetPosition(0,0,0)
end
''')

    def test_ground_repair_uses_one_flint_on_foot_or_while_driving(self):
        self.run_lua('''
local tool=equipment('aom_weeder');tool.components.finiteuses:SetUses(0)
local flint=SpawnPrefab('flint');flint.components.stackable:SetStackSize(3)
local action=prompt(flint,player,tool)[1];assert(action==ACTION_DEFS.AOM_REPAIR)
ride();assert(action.fn({doer=player,target=tool,invobject=flint}))
assert(Durability.GetUses(tool)==10 and flint.components.stackable:StackSize()==2)
player.components.rider:ActualDismount()
assert(action.fn({doer=player,target=tool,invobject=flint}))
assert(Durability.GetUses(tool)==20 and flint.components.stackable:StackSize()==1)
ride();assert(act(tool))
''')

    def test_water_quantity_and_sprinkler_mechanical_durability_are_independent(self):
        self.run_lua('''
local tool=equipment('aom_irrigator');ride();assert(act(tool))
assert(t.components.aom_attachment_store:AddWater(12)==12)
tool._aom_machine_uses=1;Durability.UseAttachment(t,tool)
assert(tool.components.finiteuses:GetUses()==12 and Durability.GetUses(tool)==0)
assert(Durability.RepairAttachment(tool) and tool.components.finiteuses:GetUses()==12)
player.Transform:SetPosition(tool.Transform:GetWorldPosition());assert(act(tool))
assert(t.components.aom_attachment_store:GetWater()==12 and Durability.GetUses(tool)==10)
''')

    def test_mount_visual_moves_real_independently_clickable_entity_and_body_symbols_are_empty(self):
        self.run_lua('''
require('aom_driver_visual').Configure('test/',function()return true end)
local tool=equipment('aom_harvester');ride();assert(act(tool))
local before=tool.Transform:GetWorldPosition();player.Transform:SetPosition(12,0,0)
local after=tool.Transform:GetWorldPosition()
assert(after>before+10 and tool.parent==player and tool~=player and tool~=t)
assert(player.visual_symbols.aom_driver_attachment_front.symbol=='empty')
assert(t.visual_symbols.attachment.symbol=='empty')
''')

    def test_save_reload_retains_independent_equipment_and_slot_one_cargo(self):
        self.run_lua('''
local tool=equipment('aom_irrigator');ride();assert(act(tool))
assert(t.components.aom_attachment_store:AddWater(17)==17)
tool._aom_machine_uses=23
local cargo=SpawnPrefab('tomato_seeds');cargo.components.stackable:SetStackSize(11)
assert(t.components.container:GiveItem(cargo,1))
local record=clone(t:GetSaveRecord());assert(record.data.aom_attachment_record.prefab=='aom_irrigator')
assert(record.data.container.items[1].prefab=='tomato_seeds' and not tool.persists)
t:Remove();tool:Remove()
local restored=SpawnSaveRecord(record)
assert(restored:GetAttachment().prefab=='aom_irrigator' and Durability.GetUses(restored:GetAttachment())==23)
assert(restored.components.aom_attachment_store:GetWater()==17)
assert(restored.components.container:GetItemInSlot(1).components.stackable:StackSize()==11)
''')

    def test_legacy_slot_one_equipment_migrates_without_losing_water_or_cargo(self):
        self.run_lua('''
local tank=equipment('aom_irrigator');tank.components.finiteuses:SetUses(19)
local seeds=SpawnPrefab('tomato_seeds');seeds.components.stackable:SetStackSize(7)
local record={prefab='aom_tractor_chassis',data={fuel=123,container={items={
 [1]=clone(tank:GetSaveRecord()),[2]=clone(seeds:GetSaveRecord())}}}}
tank:Remove();seeds:Remove()
local restored=SpawnSaveRecord(record)
assert(restored:GetAttachment() and restored:GetAttachment().prefab=='aom_irrigator')
assert(restored.components.aom_attachment_store:GetWater()==19 and restored._fuel:value()==123)
assert(restored.components.container:GetItemInSlot(1)==nil)
assert(restored.components.container:GetItemInSlot(2).components.stackable:StackSize()==7)
''')

    def test_client_world_equipment_has_replica_link_but_no_inventory_component(self):
        self.run_lua('''
TheWorld.ismastersim=false
local tool=equipment('aom_seeder')
assert(tool._aom_vehicle and tool._durability_net and tool.components.inventoryitem==nil)
assert(tool.components.finiteuses==nil)
''')

    def test_broken_equipment_save_reload_stays_broken_until_repaired(self):
        self.run_lua('''
local tool=equipment('aom_irrigator');tool._aom_machine_uses=0
tool.components.finiteuses:SetUses(9)
local saved=clone(tool:GetSaveRecord());tool:Remove()
local restored=SpawnSaveRecord(saved)
assert(Durability.GetUses(restored)==0 and restored.components.finiteuses:GetUses()==9)
ride();assert(not act(restored))
assert(Durability.RepairAttachment(restored) and act(restored))
assert(t.components.aom_attachment_store:GetWater()==9)
''')

    def test_blocked_unmount_keeps_machine_and_cargo_then_can_retry_on_clear_ground(self):
        self.run_lua('''
local tool=equipment('aom_seeder');ride();assert(act(tool))
local normal=TheWorld.Map.IsPassableAtPoint
TheWorld.Map.IsPassableAtPoint=function()return false end
tool.components.finiteuses:SetUses(1);t:SetWorking(true);Durability.UseAttachment(t,tool)
assert(tool:IsValid() and t:GetAttachment()==tool and not t._working)
assert(string.find(require('aom_work_status').Describe(t),'附近无空地',1,true))
TheWorld.Map.IsPassableAtPoint=normal
assert(act(tool) and t:GetAttachment()==nil and Durability.GetUses(tool)==0)
''')

    def test_old_packed_tractor_auto_migrates_to_world_with_equipment_and_contents(self):
        self.run_lua('''
local tank=equipment('aom_irrigator');tank.components.finiteuses:SetUses(21)
local seeds=SpawnPrefab('tomato_seeds');seeds.components.stackable:SetStackSize(8)
local record={prefab='aom_tractor_item',data={aom_packed_fuel=127,aom_packed_uses=633,
 container={items={[1]=clone(tank:GetSaveRecord()),[9]=clone(seeds:GetSaveRecord())}}}}
t:Remove();tank:Remove();seeds:Remove()
local old=SpawnSaveRecord(record);assert(not old.components.inventoryitem.canbepickedup)
old.last_periodic.fn(old)
assert(not old:IsValid())
local vehicle
for _,e in ipairs(ENTITIES)do if e:IsValid() and e.prefab=='aom_tractor_chassis' then vehicle=e end end
assert(vehicle and vehicle:GetAttachment().prefab=='aom_irrigator')
assert(vehicle.components.aom_attachment_store:GetWater()==21 and vehicle._fuel:value()==127)
assert(vehicle.components.finiteuses:GetUses()==633)
assert(vehicle.components.container:GetItemInSlot(9).components.stackable:StackSize()==8)
''')

    def test_hammer_recovers_materials_and_equipment_without_creating_portable_tractor(self):
        self.run_lua('''
local tool=equipment('aom_weeder');assert(t:AttachAttachment(nil,tool))
assert(t.components.container:GiveItem(SpawnPrefab('tomato_seeds'),1))
t.components.workable:WorkedBy(player,4)
assert(not t:IsValid() and tool:IsValid() and tool.persists and Mount.Owner(tool)==nil)
for _,e in ipairs(ENTITIES)do assert(not (e:IsValid() and e.prefab=='aom_tractor_item'))end
''')

    def test_destroyed_tractor_preserves_machine_even_without_a_clear_parking_space(self):
        self.run_lua('''
local tool=equipment('aom_irrigator');assert(t:AttachAttachment(nil,tool))
assert(t.components.aom_attachment_store:AddWater(13)==13)
TheWorld.Map.IsPassableAtPoint=function()return false end
t.components.health:SetVal(0)
assert(tool:IsValid() and tool.persists and Mount.Owner(tool)==nil)
assert(tool.components.finiteuses:GetUses()==13 and t:GetAttachment()==nil)
''')

    def test_mount_range_includes_native_action_collision_radii(self):
        self.run_lua('''
local tool=equipment('aom_seeder');ride()
tool.physics_radius=.5;player.physics_radius=.5
tool.Transform:SetPosition(6.01,0,0);assert(not act(tool))
tool.Transform:SetPosition(6,0,0);assert(act(tool))
''')


if __name__=='__main__':unittest.main()
