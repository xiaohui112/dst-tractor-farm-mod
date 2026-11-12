"""审查发现的故障路径：执行真实设备、农业、原版地图和库存组件。"""
from pathlib import Path
import sys
import unittest
from zipfile import ZipFile
import test_world_equipment as world
import test_work_cargo as cargo
import test_plough_pickup as plough
from test_giant_farming import World,as_dict

ROOT=Path(__file__).resolve().parents[2]

class LayoutRegressionTests(unittest.TestCase):
    def test_all_layouts_prepare_and_sow_in_all_rotations_with_native_neighbor_collapse(self):
        from test_landclearer_flow import LandClearerFlowTests
        engine=LandClearerFlowTests();engine.setUp();w=engine.w
        count=0
        for season,combos in w.block.BLOCKS.items():
            for _,combo in combos.items():
                if combo.reference_only:continue
                count+=1
                for rotation in range(4):
                    with self.subTest(layout=combo.id,rotation=rotation):
                        w.lua.execute('ENTITIES={};TILES={};TRACE={};TILE_WRITES=0')
                        inst=w.lua.globals().make_flow_inst(w.lua.table_from(as_dict(combo.ratio)),season)
                        inst._seed_strategy='GIANT';w.bind(inst,combo);inst._block.rotation=rotation
                        _,tiles=w.block.WorldSlots(inst._block)
                        for _,tile in tiles.items():w.lua.globals().TheWorld.Map.SetTile(w.lua.globals().TheWorld.Map,tile.x/4,tile.z/4,0)
                        for _,tile in tiles.items():
                            changed,reason,ready=w.drive.WorkHere(inst,tile.x,tile.z)
                            self.assertTrue(changed);self.assertTrue(ready,reason)
                        w.lua.globals().set_flow_attachment(inst,'seeder')
                        for _,tile in tiles.items():w.drive.WorkTile(inst,tile.x,tile.z)
                        self.assertEqual(inst._block.done,combo.total)
        self.assertEqual(count,109)

    def test_validator_rejects_cross_tile_neighbors_and_changed_world_spacing(self):
        w=World();c=w.combo('autumn-01-02')
        w.lua.globals().TUNING.FARM_TILL_SPACING=1.5
        self.assertFalse(w.block.ValidateCombo(c,'autumn')[0])
        w.lua.globals().TUNING.FARM_TILL_SPACING=1.25
        self.assertTrue(w.block.ValidateCombo(c,'autumn'))
        w.lua.execute('''
local c=Block.BLOCKS.autumn[1]
local clone={slots={},ratio=c.ratio,not_giant=c.not_giant}
for i,p in ipairs(c.slots)do
 clone.slots[i]={x=p.x,z=p.z,tx=p.tx,tz=p.tz,crop=p.crop}
end
local a,b
for _,p in ipairs(clone.slots)do if p.crop then if not a then a=p else b=p;break end end end
a.x=1.9;a.z=0;a.tx=0;a.tz=0
b.x=-1.9;b.z=0;b.tx=1;b.tz=0
local ok,why=Block.ValidateCombo(clone,'autumn')
assert(not ok and why=='MOUNDS_TOO_CLOSE')
''')

    def test_next_tile_advances_after_actual_plough_preparation(self):
        w=World();combo=w.combo('autumn-10-02');inst=w.make(as_dict(combo.ratio));w.bind(inst,combo)
        inst._attachment_type='plow';inst._block.confirmed=True
        x,z=w.block.NextTile(inst)
        self.assertTrue(w.drive.WorkHere(inst,x,z)[0])
        self.assertNotEqual(w.block.NextTile(inst),(x,z))

    def test_plough_refuses_to_break_unplanned_neighbor_mound(self):
        w=World();inst=w.make({});inst._seed_strategy='SEQUENTIAL'
        soil=w.lua.globals().SpawnPrefab('farm_soil')
        soil.Transform.SetPosition(soil.Transform,2.1,0,0)
        changed,reason,ready=w.drive.WorkHere(inst,0,0)
        self.assertTrue(changed);self.assertFalse(ready);self.assertEqual(reason,'BLOCKED_MOUND')
        self.assertTrue(soil.IsValid(soil));self.assertFalse(soil.HasTag(soil,'NOCLICK'))

    def test_v2_plan_never_reinterprets_completed_indices_in_new_layout(self):
        w=World();inst=w.make({'tomato':4,'potato':4})
        w.block.OnLoad(inst,w.lua.table_from({'version':2,'combo_id':'autumn-01-02','season':'autumn','x':0,'z':0,'rotation':0,'completed':w.lua.table_from([1])}))
        self.assertIsNone(inst._block)
        self.assertEqual(w.block.GetTargets(inst,'autumn',w.lua.table_from({'tomato':4,'potato':4}),0,0,True),(None,'PLAN_OUTDATED'))
        saved=w.block.OnSave(inst);self.assertTrue(saved.outdated)
        w.block.ResetBlock(inst);self.assertIsNone(inst._aom_plan_outdated)

class MachineRegressionTests(unittest.TestCase):
    setUp=world.WorldEquipmentTests.setUp
    run_lua=world.WorldEquipmentTests.run_lua
    def test_broken_water_and_fertilizer_cannot_restart_when_detach_is_blocked(self):
        self.run_lua('''
local Drive=require('aom_drive');local native=require('aom_farm_work').IsFarmTileAt
for _,name in ipairs({'aom_irrigator','aom_fertilizer'})do
 local item=equipment(name);if not player.components.rider:IsRiding()then ride()end
 assert(act(item))
 if name=='aom_irrigator' then t.components.aom_attachment_store:AddWater(20)
 else t.components.container:GiveItem(SpawnPrefab('poop'),1)end
 local free=Mount.FreePosition;Mount.FreePosition=function()return nil end
 item._aom_machine_uses=1;t:SetWorking(true);Durability.UseAttachment(t,item)
 assert(t:GetAttachment()==item and Durability.GetUses(item)==0 and not t._working)
 local called=false;require('aom_farm_work').IsFarmTileAt=function()called=true;return true end
 local fuel=t._fuel:value();local water=t.components.aom_attachment_store:GetWater()
 assert(t:ToggleWorking(player));Drive.TrackMovement(t)
 assert(not called and not t._working and Durability.GetUses(item)==0)
 assert(t._fuel:value()==fuel and t.components.aom_attachment_store:GetWater()==water)
 assert(t._workstate_net:value()==(name=='aom_irrigator' and 'BROKEN_IRRIGATOR' or 'BROKEN_FERTILIZER'))
 Mount.FreePosition=free;assert(act(item));item:Remove()
end
require('aom_farm_work').IsFarmTileAt=native
''')

    def test_blocked_legacy_migration_preserves_owner_and_retries_without_duplicate_cargo(self):
        self.run_lua('''
t:Remove()
local seed=SpawnPrefab('tomato_seeds');seed.components.stackable:SetStackSize(8)
local record={prefab='aom_tractor_item',data={aom_packed_fuel=127,
 container={items={[9]=clone(seed:GetSaveRecord())}}}}
seed:Remove();local old=SpawnSaveRecord(record)
player:AddComponent('container');player.components.inventory=player.components.container
player.components.inventory:SetNumSlots(15)
assert(old.components.inventoryitem.cangoincontainer)
assert(player.components.inventory:GiveItem(old,1))
local plant=TheWorld.Map.CanPlantAtPoint;TheWorld.Map.CanPlantAtPoint=function()return false end
old._aom_unpack_task.fn(old)
assert(old:IsValid() and old.components.inventoryitem.owner==player and old.hidden)
assert(player.components.inventory:GetItemInSlot(1)==old and old._aom_unpack_task)
assert(old.components.container:GetItemInSlot(9).components.stackable:StackSize()==8)
local pending=player.components.inventory:OnSave()
old:Remove();player.components.inventory:OnLoad(pending,{})
old=player.components.inventory:GetItemInSlot(1)
assert(old and old.components.inventoryitem.owner==player)
old._aom_unpack_task.fn(old)
assert(old:IsValid() and old.components.inventoryitem.owner==player)
local retry=old._aom_unpack_task
TheWorld.Map.CanPlantAtPoint=plant;retry.fn(old);assert(not old:IsValid())
retry.fn(old)
local count,vehicle=0
for _,e in ipairs(ENTITIES)do if e:IsValid() and e.prefab=='aom_tractor_chassis' then count=count+1;vehicle=e end end
assert(count==1 and vehicle._fuel:value()==127)
assert(vehicle.components.container:GetItemInSlot(9).components.stackable:StackSize()==8)
''')

    def test_status_code_can_be_rendered_in_another_client_language_without_components(self):
        self.run_lua('''
local Status=require('aom_work_status');local AOM=require('aom_common')
Status.Set(t,'EMPTY','irrigator');assert(Status.Read(t)=='EMPTY')
local client={_workstate_net=t._workstate_net}
AOM.SetLanguage('en');assert(string.find(Status.Describe(client),'Water tank empty',1,true))
AOM.SetLanguage('zh');assert(string.find(Status.Describe(client),'水箱已空',1,true))
Status.Set(t,'CARGO_FULL');AOM.SetLanguage('en')
assert(t._workstate_net:value()=='CARGO_FULL' and string.find(Status.Describe(client),'storage full',1,true))
''')

class CallbackRegressionTests(unittest.TestCase):
    def setUp(self):
        engine=cargo.WorkCargoTests();engine.setUp();self.lua=engine.lua
        self.lua.execute("work_errors={};print=function(message)work_errors[#work_errors+1]=message end")

    def test_callback_after_pick_stops_bills_actual_progress_once_and_restores_methods(self):
        self.lua.execute('''
local a=crop('tomato',0,0,false);local inv=player.components.inventory
local give,spawn=inv.GiveItem,a.components.lootdropper.SpawnLootPrefab
a.components.pickable.onpickedfn=function()error('injected callback failure')end
t:SetWorking(true);local changed,why=Drive.WorkTile(t,0,0)
assert(changed and why=='WORK_ERROR' and not t._working)
assert(t._fuel:value()==399 and t:GetAttachment().components.finiteuses:GetUses()==39)
assert(inv.GiveItem==give and a.components.lootdropper.SpawnLootPrefab==spawn)
assert(quantity(nil,'tomato')==1 and t._workstate_net:value()=='WORK_ERROR')
assert(not t._aom_work_result and not t:HasTag('NOBLOCK'))
assert(not a.components.pickable:CanBePicked())
t:SetWorking(true);Drive.WorkTile(t,0,0)
assert(t._fuel:value()==399 and quantity(t,'tomato')==1)
local saved=a.components.pickable:OnSave();assert(saved.picked==true)
''')

    def test_error_before_any_change_stops_without_consuming_resources(self):
        self.lua.execute('''
Farm.Harvest=function()error('before work')end
t:SetWorking(true);local changed,why=Drive.WorkTile(t,0,0)
assert(not changed and why=='WORK_ERROR' and not t._working)
assert(t._fuel:value()==400 and t:GetAttachment().components.finiteuses:GetUses()==40)
''')

    def test_workable_error_after_dig_is_billed_and_does_not_escape_sampling(self):
        self.lua.execute('''
tool('aom_weeder');local e=weed(0,0)
e.components.workable:SetOnFinishCallback(function()e:Remove();error('after dig')end)
t:SetWorking(true);Drive.TrackMovement(t)
assert(not t._working and not e:IsValid() and t._fuel:value()==399)
assert(t:GetAttachment().components.finiteuses:GetUses()==49)
''')

class PloughRegressionTests(unittest.TestCase):
    def setUp(self):
        engine=plough.PloughPickupTests();engine.setUp();self.lua=engine.lua
        self.lua.execute("work_errors={};print=function(message)work_errors[#work_errors+1]=message end")

    def test_scattered_new_drop_is_collected_without_picking_neighbor_items(self):
        self.lua.execute('''
local debris=CreateEntity();debris.prefab='farm_soil_debris';debris.Transform:SetPosition(1.99,0,0)
debris:AddComponent('workable');local w=debris.components.workable
w:SetWorkAction(ACTIONS.DIG);w:SetWorkLeft(1)
local loot;debris.components.lootdropper={SpawnLootPrefab=function()loot=ground('flint',2.1,0,1);return loot end}
w:SetOnFinishCallback(function()debris.components.lootdropper:SpawnLootPrefab();debris:Remove()end)
local neighbor=ground('rocks',2.1,0,1);neighbor:AddTag('NOBLOCK')
t:SetWorking(true);local changed,why=Drive.WorkTile(t,0,0)
assert(changed and not why and Farm.IsFieldReady(0,0,0))
assert(loot.components.inventoryitem.owner==t and neighbor.components.inventoryitem.owner==nil)
''')

    def test_tilling_error_cleans_noblock_and_charges_only_actual_progress(self):
        self.lua.execute('''
local native=TheWorld.Map.CanTillSoilAtPoint;local calls=0
TheWorld.Map.CanTillSoilAtPoint=function(self,...)
 calls=calls+1;if calls==2 then error('till hook')end;return native(self,...)
end
t:SetWorking(true);local changed,why=Drive.WorkTile(t,0,0)
assert(changed and why=='WORK_ERROR' and not t._working and not t:HasTag('NOBLOCK'))
assert(t._fuel:value()==399 and tool.components.finiteuses:GetUses()==59)
''')

if __name__=='__main__':unittest.main()
