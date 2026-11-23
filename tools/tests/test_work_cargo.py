"""除草与收割进入真实 Container；覆盖原版 Pickable、归属、堆叠、满仓及存档。"""
from pathlib import Path
import unittest
import test_lifecycle_flow as lifecycle

ROOT=Path(__file__).resolve().parents[2]


class WorkCargoTests(unittest.TestCase):
    def setUp(self):
        engine=lifecycle.LifecycleFlowTests();engine.setUp();self.lua=engine.lua
        self.lua.execute((ROOT/'tools/tests/harvester_engine.lua').read_text())
        self.lua.execute('''
package.loaded['aom_farm_work']=nil;package.loaded['aom_drive']=nil
kit:Remove();t=SpawnPrefab('aom_tractor_chassis');Farm=require('aom_farm_work');Drive=require('aom_drive')
local make_giant=giant
function giant(...)local e=make_giant(...);e:AddComponent('inventoryitem');return e end
local spawn=SpawnPrefab
function SpawnPrefab(name)
 local e=spawn(name)
 if DEFS[name] and not e.components.stackable then e:AddComponent('stackable')end
 return e
end
player:AddComponent('container');player.components.inventory=player.components.container
player.components.inventory:SetNumSlots(15)
local inventory=player.components.inventory
inventory.GetEquippedItem=function()return nil end
function tool(name)
 if t:GetAttachment() then assert(t:DetachAttachment(nil))end
 local e=SpawnPrefab(name);assert(t:AttachAttachment(nil,e));return e
end
tool('aom_harvester')
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
function quantity(owner,name)
 local n=0
 for _,e in ipairs(ENTITIES)do
  local ii=e.components.inventoryitem
  if e.valid and e.prefab==name and ii and ii.owner==owner then
   n=n+(e.components.stackable and e.components.stackable:StackSize() or 1)
  end
 end
 return n
end
function fill_storage(storage)
 for i=1,storage:GetNumSlots() do local e=SpawnPrefab('gears');e.components.stackable:SetStackSize(40)
  assert(storage:GiveItem(e,i))end
end
function fill(include_pockets)
 fill_storage(t.components.container)
 if include_pockets~=false then fill_storage(player.components.inventory)end
end
function weed(x,z)
 local e=CreateEntity();e.prefab='weed_tillweed';e:AddTag('weed')
 e.Transform:SetPosition(x or 0,0,z or 0);e:AddComponent('workable')
 e.components.workable:SetWorkAction(ACTIONS.DIG);e.components.workable:SetWorkLeft(1)
 attach_loot(e,{'twigs','rocks'})
 e.components.workable:SetOnFinishCallback(function()e.components.lootdropper:DropLoot();e:Remove()end)
 return e
end
''')

    def run_lua(self,s):self.lua.execute(s)

    def test_normal_harvest_goes_to_cargo_and_leaves_players_existing_stack_untouched(self):
        self.run_lua('''
local old=SpawnPrefab('tomato');old.components.stackable:SetStackSize(10)
assert(player.components.inventory:GiveItem(old,1))
local plant=crop('tomato',0,0,false);local nextplant=crop('tomato',4,0,false)
local give=player.components.inventory.GiveItem
local actual_picker
plant.components.pickable.onpickedfn=function(_,picker)actual_picker=picker end
t:SetWorking(true);assert(Drive.WorkTile(t,0,0))
assert(quantity(t,'tomato')==1 and quantity(t,'tomato_seeds')==1)
assert(quantity(player,'tomato')==10 and old.components.stackable:StackSize()==10)
assert(actual_picker==player and give==player.components.inventory.GiveItem)
assert(not plant.valid and nextplant.valid and t._working)
assert(Drive.WorkTile(t,4,0) and quantity(t,'tomato')==2 and not nextplant.valid)
assert(t._fuel:value()==598 and t:GetAttachment().components.finiteuses:GetUses()==198)
''')

    def test_auto_pickup_stacks_across_cargo_pockets_and_equipped_backpack_then_leaves_remainder(self):
        self.run_lua('''
fill()
local pockets=player.components.inventory
local pack=SpawnPrefab('backpack');pack:AddComponent('container')
pack.components.inventoryitem:OnPutInInventory(player)
local backpack=pack.components.container;backpack:SetNumSlots(1)
function pockets:GetOverflowContainer()return backpack end
for i,storage in ipairs({t.components.container,pockets,backpack})do
 local old=storage:RemoveItemBySlot(1);if old then old:Remove()end
 local stack=SpawnPrefab('rocks');stack.components.stackable:SetStackSize(40-i)
 assert(storage:GiveItem(stack,1))
end
local loot=SpawnPrefab('rocks');loot.components.stackable:SetStackSize(8)
local fuel=t._fuel:value()
assert(not Drive.WorkTile(t,0,0))
assert(quantity(t,'rocks')==40 and quantity(player,'rocks')==40 and quantity(pack,'rocks')==40)
assert(quantity(nil,'rocks')==2 and loot:IsValid() and t._fuel:value()==fuel)
''')

    def test_harvest_uses_backpack_when_cargo_and_pockets_are_full(self):
        self.run_lua('''
fill()
local pack=SpawnPrefab('backpack');pack:AddComponent('container')
pack.components.inventoryitem:OnPutInInventory(player)
pack.components.container:SetNumSlots(2)
function player.components.inventory:GetOverflowContainer()return pack.components.container end
local crop_to_harvest=crop('tomato',0,0,false)
assert(Drive.WorkTile(t,0,0) and not crop_to_harvest:IsValid())
assert(quantity(t,'tomato')==0 and quantity(player,'tomato')==0)
assert(quantity(pack,'tomato')==1 and quantity(pack,'tomato_seeds')==1)
''')

    def test_giant_and_rotten_giant_drops_are_collected_with_native_yields(self):
        self.run_lua('''
local first=crop('tomato',0,0,true);local rotten=giant('carrot',1,0,'_rotten')
assert(Drive.WorkTile(t,0,0) and not first.valid and not rotten.valid)
assert(quantity(t,'tomato')+quantity(t,'tomato_seeds')==5)
assert(quantity(t,'spoiled_food')==1 and quantity(player,'tomato')==0)
assert(t._fuel:value()==599 and t:GetAttachment().components.finiteuses:GetUses()==199)
''')

    def test_keep_giants_harvests_whole_even_after_crossing_a_full_tile(self):
        self.run_lua('''
fill()
local normal=crop('corn',0,0,false)
local existing=giant('carrot',1,0)
local giant_plant=crop('tomato',4,0,true)
local other_normal=crop('corn',5,0,false)
assert(t:CycleHarvestMode(player))
t:SetWorking(true)
assert(not Drive.WorkTile(t,0,0))
assert(t._working and normal:IsValid() and existing:IsValid() and t._fuel:value()==600)
assert(Drive.WorkTile(t,4,0))
assert(not giant_plant:IsValid() and other_normal:IsValid() and t._working)
local intact
for _,item in ipairs(ENTITIES)do
 if item:IsValid() and item.prefab=='tomato_oversized' then
  assert(not intact);intact=item
 end
end
assert(intact and intact.x==4 and intact.z==0 and not intact.components.inventoryitem.owner)
assert(intact.components.workable:GetWorkLeft()==1 and existing.components.workable:GetWorkLeft()==1)
assert(t._fuel:value()==599 and t.components.finiteuses:GetUses()==999)
assert(t:GetAttachment().components.finiteuses:GetUses()==199)
assert(not Drive.WorkTile(t,4,0) and intact:IsValid() and t._fuel:value()==599)
''')

    def test_keep_giants_stores_ordinary_harvest_and_respects_protection_when_full(self):
        self.run_lua('''
local normal=crop('corn',0,0,false)
local giant_plant=crop('tomato',1,0,true)
assert(t:CycleHarvestMode(player))
assert(Drive.WorkTile(t,0,0) and not normal:IsValid() and not giant_plant:IsValid())
assert(quantity(t,'corn')==1 and quantity(t,'corn_seeds')==1)
assert(quantity(nil,'tomato_oversized')==1 and quantity(t,'tomato')==0)
for slot=1,15 do
 local item=t.components.container:RemoveItemBySlot(slot)
 if item then item:Remove() end
end
fill()
local protected=crop('tomato',4,0,true)
require('aom_weed_defense').FindIvy=function(plant)return plant==protected end
t:SetWorking(true)
local changed,reason=Drive.WorkTile(t,4,0)
assert(not changed and reason=='IVY_THREAT' and not t._working)
assert(protected:IsValid() and t._fuel:value()==599)
''')

    def test_weeding_collects_old_ground_items_and_new_drops_then_continues(self):
        self.run_lua('''
local e=tool('aom_weeder');local a=weed(0,0);local b=weed(4,0)
local old=SpawnPrefab('flint');old.components.stackable:SetStackSize(3)
t:SetWorking(true);assert(Drive.WorkTile(t,0,0) and not a.valid and b.valid)
assert(quantity(t,'twigs')==1 and quantity(t,'rocks')==1 and quantity(t,'flint')==3)
assert(Drive.WorkTile(t,4,0) and not b.valid and t._working)
assert(quantity(t,'twigs')==2 and quantity(t,'rocks')==2 and t._fuel:value()==598)
assert(e.components.finiteuses:GetUses()==198)
''')

    def test_fully_stacked_cargo_stops_before_harvest_and_resumes_after_freeing_space(self):
        self.run_lua('''
fill();local a=crop('tomato',0,0,false);local b=crop('tomato',1,0,false)
t:SetWorking(true);local changed,why=Drive.WorkTile(t,0,0)
assert(not changed and why=='CARGO_FULL' and not t._working and a.valid and b.valid)
assert(quantity(nil,'tomato')==0 and quantity(nil,'tomato_seeds')==0)
assert(quantity(player,'tomato')==0 and t._fuel:value()==600)
assert(string.find(require('aom_work_status').Describe(t),'空间不足',1,true))
t.components.container:RemoveItemBySlot(1):Remove();t.components.container:RemoveItemBySlot(2):Remove()
t:SetWorking(true);assert(Drive.WorkTile(t,0,0) and not a.valid and not b.valid and t._working)
assert(quantity(t,'tomato')==2 and quantity(t,'tomato_seeds')==2)
assert(quantity(nil,'tomato')==0 and t._fuel:value()==599)
''')

    def test_full_cargo_before_weeding_does_not_destroy_weeds_or_charge(self):
        self.run_lua('''
tool('aom_weeder');fill();local a=weed(0,0);local loot=SpawnPrefab('flint')
t:SetWorking(true);local changed,why=Drive.WorkTile(t,0,0)
assert(not changed and why=='CARGO_FULL' and a.valid and loot.valid and not t._working)
assert(t._fuel:value()==600 and t:GetAttachment().components.finiteuses:GetUses()==200)
''')

    def test_new_loot_scattered_across_tile_border_is_collected_without_sweeping_neighbor(self):
        self.run_lua('''
local a=giant('tomato',1.99,0);local spawn=a.components.lootdropper.SpawnLootPrefab
a.components.lootdropper.SpawnLootPrefab=function(self,...)
 local e=spawn(self,...);e.Transform:SetPosition(2.1,0,0);return e
end
local neighbor=SpawnPrefab('rocks');neighbor.Transform:SetPosition(2.1,0,0)
assert(Drive.WorkTile(t,0,0))
assert(quantity(t,'tomato')+quantity(t,'tomato_seeds')==5)
assert(neighbor.components.inventoryitem.owner==nil and quantity(t,'rocks')==0)
''')

    def test_full_cargo_after_weeding_keeps_native_drops_and_bills_changed_tile_once(self):
        self.run_lua('''
tool('aom_weeder');fill();local a=weed(0,0);local b=weed(1,0)
t:SetWorking(true);local changed,why=Drive.WorkTile(t,0,0)
assert(changed and why=='CARGO_FULL' and not t._working and not a.valid and b.valid)
assert(quantity(nil,'twigs')==1 and quantity(nil,'rocks')==1)
assert(t._fuel:value()==599 and t:GetAttachment().components.finiteuses:GetUses()==199)
''')

    def test_full_slots_accept_matching_produce_and_partial_stack_keeps_remainder(self):
        self.run_lua('''
fill();t.components.container:RemoveItemBySlot(1):Remove()
local stored=SpawnPrefab('tomato');stored.components.stackable:SetStackSize(38)
assert(t.components.container:GiveItem(stored,1))
local a=crop('tomato',0,0,false);a.components.lootdropper.loot={'tomato','tomato','tomato'}
t:SetWorking(true);local changed,why=Drive.WorkTile(t,0,0)
assert(changed and why=='CARGO_FULL' and not t._working and not a.valid)
assert(quantity(t,'tomato')==40 and quantity(nil,'tomato')==1)
assert(t._fuel:value()==599)
t.components.container:RemoveItemBySlot(2):Remove()
t:SetWorking(true);local again=Drive.WorkTile(t,0,0)
assert(not again and t._working and quantity(t,'tomato')==41 and quantity(nil,'tomato')==0)
assert(t._fuel:value()==599 and t:GetAttachment().components.finiteuses:GetUses()==199)
''')

    def test_harvest_callback_error_restores_inventory_and_loot_functions(self):
        self.run_lua('''
local a=crop('tomato',0,0,false);local inv=player.components.inventory
local give,spawn=inv.GiveItem,a.components.lootdropper.SpawnLootPrefab
a.components.pickable.onpickedfn=function()error('callback failed')end
local ok=pcall(Farm.Harvest,0,0,0,player,t)
assert(not ok and inv.GiveItem==give and a.components.lootdropper.SpawnLootPrefab==spawn)
assert(quantity(nil,'tomato')==1 and quantity(player,'tomato')==0)
''')

    def test_collected_produce_and_equipment_survive_save_reload(self):
        self.run_lua('''
crop('tomato',0,0,true);assert(Drive.WorkTile(t,0,0))
local count=quantity(t,'tomato')+quantity(t,'tomato_seeds')
local record=clone(t:GetSaveRecord());t:Remove()
local restored=SpawnSaveRecord(record)
assert(quantity(restored,'tomato')+quantity(restored,'tomato_seeds')==count and count==5)
assert(restored:GetAttachment().prefab=='aom_harvester')
''')


if __name__=='__main__':unittest.main()
