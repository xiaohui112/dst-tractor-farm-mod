"""开垦拾取回归：真实 Container / InventoryItem / Stackable / Workable 和 Mod 链路。"""
from pathlib import Path
import unittest
import test_lifecycle_flow as lifecycle

ROOT = Path(__file__).resolve().parents[2]


class PloughPickupTests(unittest.TestCase):
    def setUp(self):
        engine = lifecycle.LifecycleFlowTests()
        engine.setUp()
        self.lua = engine.lua
        self.lua.execute('''
WORLD_TILES={FARMING_SOIL=1}
player:AddTag('player')
Farm=require('aom_farm_work');Drive=require('aom_drive')
t=deploy_kit(kit,0,0,player)
tool=SpawnPrefab('aom_landclearer');assert(t:AttachAttachment(nil,tool))
t._aom_terraformer={components={terraformer={}}}
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
-- 引擎地图表面：普通地面物品确实挡坑；入库后的 INLIMBO 物品不再占地。
function TheWorld.Map:CanTillSoilAtPoint(x,y,z)
 for _,e in ipairs(ENTITIES)do
  if e.valid and not e.hidden and not (e:HasTag('NOBLOCK') or e:HasTag('FX') or e:HasTag('player') or e:HasTag('soil'))
   and (e.x-x)^2+(e.z-z)^2<1.25^2 then return false end
 end
 return true
end
function TheWorld.Map:CollapseSoilAtPoint()end
function ground(name,x,z,count)
 local e=SpawnPrefab(name);e.Transform:SetPosition(x,0,z)
 if count then e.components.stackable:SetStackSize(count)end
 return e
end
function fill_cargo()
 for i=1,t.components.container:GetNumSlots() do
  local item=SpawnPrefab('gears');item.components.stackable:SetStackSize(40)
  assert(t.components.container:GiveItem(item,i))
 end
end
''')

    def run_lua(self, source):
        self.lua.execute(source)

    def test_loot_is_picked_up_before_nine_pits_and_work_continues_to_next_tile(self):
        self.run_lua('''
local rocks=ground('rocks',0,0,4);local twigs=ground('twigs',1,1,3)
local nextloot=ground('flint',4,0,2);local untouched=ground('rocks',8,0,1)
assert(not TheWorld.Map:CanTillSoilAtPoint(0,0,0))
local pickups=0;rocks:ListenForEvent('onpickup',function(_,data)assert(data.owner==t);pickups=pickups+1 end)
Drive.SetWorking(t,true);Drive.TrackMovement(t)
assert(t._working and Farm.IsFieldReady(0,0,0) and pickups==1)
assert(rocks.hidden and twigs.hidden and rocks.components.inventoryitem.owner==t)
assert(rocks.components.stackable:StackSize()==4 and twigs.components.stackable:StackSize()==3)
assert(not nextloot.hidden and not untouched.hidden and t:GetAttachment()==tool)
player.Transform:SetPosition(4,0,0);Drive.TrackMovement(t)
assert(t._working and Farm.IsFieldReady(4,0,0) and nextloot.components.inventoryitem.owner==t)
assert(not untouched.hidden and t._fuel:value()==398 and tool.components.finiteuses:GetUses()==98)
''')

    def test_full_slots_still_accept_matching_stack_without_stopping(self):
        self.run_lua('''
fill_cargo();local stored=t.components.container:GetItemInSlot(2)
stored.components.stackable:SetStackSize(36)
local loot=ground('gears',0,0,4)
t._working=true;assert(Drive.WorkTile(t,0,0))
assert(t._working and not loot:IsValid() and stored.components.stackable:StackSize()==40)
assert(Farm.IsFieldReady(0,0,0))
''')

    def test_full_cargo_preserves_item_position_and_stops_with_specific_message(self):
        self.run_lua('''
fill_cargo();local loot=ground('rocks',1,1,5)
t._working=true;local worked,reason=Drive.WorkTile(t,0,0)
assert(not worked and reason=='CARGO_FULL' and not t._working)
assert(loot:IsValid() and not loot.hidden and loot.x==1 and loot.z==1)
assert(loot.components.inventoryitem.owner==nil and loot.components.stackable:StackSize()==5)
assert(t._fuel:value()==400 and tool.components.finiteuses:GetUses()==100)
assert(string.find(require('aom_work_status').Describe(t),'仓库已满',1,true))
-- 腾出空间后同格重试，拾取并继续开垦，不重复消耗。
t.components.container:RemoveItemBySlot(2):Remove()
t._working=true;assert(Drive.WorkTile(t,0,0) and t._working)
assert(loot.components.inventoryitem.owner==t and Farm.IsFieldReady(0,0,0))
assert(t._fuel:value()==399 and tool.components.finiteuses:GetUses()==99)
''')

    def test_partial_stack_transfer_preserves_remainder_and_retry_does_not_duplicate(self):
        self.run_lua('''
fill_cargo();local stored=t.components.container:GetItemInSlot(2)
stored.components.stackable:SetStackSize(38)
local loot=ground('gears',1,1,5)
t._working=true;local worked,reason=Drive.WorkTile(t,0,0)
assert(not worked and reason=='CARGO_FULL' and stored.components.stackable:StackSize()==40)
assert(loot:IsValid() and not loot.hidden and loot.components.inventoryitem.owner==nil)
assert(loot.x==1 and loot.z==1 and loot.components.stackable:StackSize()==3)
t.components.container:RemoveItemBySlot(3):Remove()
t._working=true;assert(Drive.WorkTile(t,0,0))
assert(loot.components.inventoryitem.owner==t and loot.components.stackable:StackSize()==3)
assert(stored.components.stackable:StackSize()==40 and Farm.IsFieldReady(0,0,0))
''')

    def test_native_workable_drops_are_collected_before_tilling(self):
        self.run_lua('''
local debris=CreateEntity();debris.prefab='farm_soil_debris';debris.Transform:SetPosition(0,0,0)
debris:AddComponent('workable');local w=debris.components.workable
w:SetWorkAction(ACTIONS.DIG);w:SetWorkLeft(1)
local loot
w:SetOnFinishCallback(function()loot=ground('flint',0,0,1);debris:Remove()end)
t._working=true;assert(Drive.WorkTile(t,0,0))
assert(not debris:IsValid() and loot and loot.components.inventoryitem.owner==t)
assert(t._working and Farm.IsFieldReady(0,0,0))
''')

    def test_full_cargo_after_digging_preserves_progress_and_loot(self):
        self.run_lua('''
fill_cargo()
local debris=CreateEntity();debris.prefab='farm_soil_debris';debris.Transform:SetPosition(0,0,0)
debris:AddComponent('workable');local w=debris.components.workable
w:SetWorkAction(ACTIONS.DIG);w:SetWorkLeft(1)
local loot
w:SetOnFinishCallback(function()loot=ground('flint',0,0,1);debris:Remove()end)
t._working=true;local worked,reason=Drive.WorkTile(t,0,0)
assert(worked and reason=='CARGO_FULL' and not t._working)
assert(loot:IsValid() and not loot.hidden and loot.components.inventoryitem.owner==nil)
assert(not debris:IsValid() and t._fuel:value()==399 and tool.components.finiteuses:GetUses()==99)
''')

    def test_owned_unpickable_burning_thrown_and_neighbor_items_are_untouched(self):
        self.run_lua('''
local owned=ground('rocks',0,0,1);owned.components.inventoryitem.owner=player
local fixed=ground('twigs',0,0,1);fixed.components.inventoryitem.canbepickedup=false
local burning=ground('charcoal',0,0,1);burning.components.burnable={IsBurning=function()return true end}
local thrown=ground('flint',0,0,1);thrown.components.projectile={IsThrown=function()return true end}
local neighbor=ground('gears',4,0,1)
assert(Farm.CollectPloughItems(0,0,0,t))
assert(owned.components.inventoryitem.owner==player)
for _,e in ipairs({fixed,burning,thrown,neighbor})do
 assert(e:IsValid() and not e.hidden and e.components.inventoryitem.owner==nil)
end
''')

    def test_buildings_and_crops_remain_protected(self):
        self.run_lua('''
local wall=CreateEntity();wall.prefab='wall_stone';wall.Transform:SetPosition(0,0,0)
local loot=ground('rocks',0,0,1)
local worked,reason=Drive.WorkTile(t,0,0)
assert(not worked and reason=='BLOCKED_MOUND' and not loot.hidden)
wall:Remove();ground('farm_plant_tomato',0,0)
worked,reason=Drive.WorkTile(t,0,0)
assert(worked and reason=='BLOCKED_MOUND' and loot.hidden)
assert(not Farm.IsFieldReady(0,0,0))
''')

    def test_cargo_survives_container_save_and_load_with_attachment(self):
        self.run_lua('''
local loot=ground('rocks',0,0,12)
assert(Drive.WorkTile(t,0,0))
local record=clone(t:GetSaveRecord());t:Remove()
local restored=SpawnSaveRecord(record)
assert(restored:GetAttachment().prefab=='aom_landclearer')
local cargo=restored.components.container:GetItemInSlot(1)
assert(cargo.prefab=='rocks' and cargo.components.stackable:StackSize()==12)
assert(cargo.components.inventoryitem.owner==restored)
''')

    def test_giant_layout_keeps_plan_and_reports_full_cargo(self):
        self.run_lua('''
local block=require('aom_block_plan');local combo
for _,c in ipairs(block.BLOCKS.autumn)do
 if not c.reference_only and block.ValidateCombo(c,'autumn')then combo=c;break end
end
assert(combo)
fill_cargo();local slot=2
for crop,count in pairs(combo.ratio)do
 t.components.container:RemoveItemBySlot(slot):Remove()
 local seeds=SpawnPrefab(crop..'_seeds');seeds.components.stackable:SetStackSize(count)
 assert(t.components.container:GiveItem(seeds,slot));slot=slot+1
end
function TheWorld.Map:IsPassableAtPoint()return true end
local loot=ground('rocks',0,0,3)
t._seed_strategy='GIANT';t._working=true
assert(block.Preview(t) and block.Confirm(t))
local worked,reason=Drive.WorkTile(t,0,0)
assert(not worked and reason=='CARGO_FULL' and not t._working and t._block and t._block.done==0)
assert(string.find(require('aom_work_status').Describe(t),'仓库已满',1,true))
assert(not loot.hidden and loot.components.stackable:StackSize()==3)
''')


if __name__ == '__main__':
    unittest.main()
