"""Rain barrel recipe, persistence and actual mounted refill action."""
import unittest

import test_pond_refill as pond


class RainBarrelTests(unittest.TestCase):
    def setUp(self):
        pond.PondRefillTests.setUp(self)
        self.lua.execute('''
local create=CreateEntity
function CreateEntity()
 local inst=create()
 function inst:WatchWorldState(name,fn)
  assert(name=='israining');self.onrain=fn
 end
 local add=inst.AddComponent
 function inst:AddComponent(name)
  if name=='lootdropper' then self.components.lootdropper={DropLoot=function()self.dropped_loot=true end}
  else return add(self,name) end
 end
 return inst
end
for _,prefab in ipairs({dofile(SCRIPTS..'/prefabs/aom_rain_barrel.lua')})do REGISTRY[prefab.name]=prefab end
clock=0;GetTime=function()return clock end
TheWorld.state.israining=false
barrel=SpawnPrefab('aom_rain_barrel');barrel.Transform:SetPosition(2,0,0)
action=ACTION_DEFS.AOM_BARREL_REFILL
Refill=require('aom_pond_refill');Irrigator=require('aom_irrigator')
function rain(value)
 TheWorld.state.israining=value
 for _,inst in ipairs(ENTITIES)do if inst:IsValid() and inst.onrain then inst.onrain(inst,value) end end
end
function collect(seconds)
 rain(true);clock=clock+seconds;rain(false)
end
function barrel_actions(doer,right)
 local actions={};SCENE_HOOKS.inspectable(barrel,doer or player,actions,right~=false);return actions
end
function take_water(doer)
 return action.fn({doer=doer or player,target=barrel})
end
function stored(expected)
 assert(barrel:GetStoredWater()==expected)
 assert(barrel._barrel_water_net:value()==expected)
end
''')

    run_lua = pond.PondRefillTests.run_lua

    def test_gardening_recipe_and_placeable_structure(self):
        self.run_lua('''
local name='aom_rain_barrel';local recipe=RECIPE_RECORDS[name]
assert(recipe.product==name and recipe.placer==name..'_placer' and RECIPE_TECH[name]==TECH.SCIENCE_TWO)
assert(#RECIPE_FILTERS[name]==1 and RECIPE_FILTERS[name][1]=='GARDENING')
local expected={boards=2,rope=2,cutstone=2}
for _,item in ipairs(RECIPE_INGREDIENTS[name])do assert(expected[item.type]==item.amount);expected[item.type]=nil end
local placer=SpawnPrefab(recipe.placer)
assert(not next(expected) and placer.components.placer)
local tank=SpawnPrefab('aom_irrigator')
assert(barrel.anim_scale[1]*240==tank.anim_scale[1]*150 and placer.transform_scale[1]==barrel.anim_scale[1])
assert(barrel:HasTag('structure') and not barrel:HasTag('watersource') and not barrel.components.inventoryitem)
assert(barrel.components.workable:GetWorkAction()==ACTIONS.HAMMER)
assert(barrel:displaynamefn()=='田边蓄水桶'..string.char(10)..'水量 0/2000')
assert(barrel.components.inspectable.getspecialdescription(barrel)=='水量 0/2000')
barrel.components.workable:WorkedBy(player,4)
assert(barrel.dropped_loot and not barrel:IsValid())
''')

    def test_rain_accumulates_exactly_and_stops_at_capacity(self):
        self.run_lua('''
stored(0);assert(not barrel._rain_task)
rain(true);local task=barrel._rain_task;assert(task)
clock=1;task.fn(barrel);stored(10)
clock=199;task.fn(barrel);stored(1990)
clock=200;task.fn(barrel);stored(2000)
assert(task.cancelled and not barrel._rain_task)
clock=201;assert(take_water());clock=202;Refill.Update(t)
stored(1920);assert(barrel._rain_task and store:GetWater()==80)
clock=203;barrel._rain_task.fn(barrel);stored(1930)
''')

    def test_rain_fraction_persists_and_dry_seasons_keep_water(self):
        self.run_lua('''
collect(.25);stored(2)
local record=clone(barrel:GetSaveRecord());barrel:Remove()
TheWorld.state.season='winter';clock=800
barrel=SpawnSaveRecord(record);stored(2)
collect(.25);stored(5)
TheWorld.state.season='summer';clock=1600;stored(5)
assert(barrel.components.inspectable.getspecialdescription(barrel)=='水量 5/2000')
''')

    def test_mounted_action_draws_at_eighty_and_preserves_partial_transfer(self):
        self.run_lua('''
assert(#barrel_actions()==0 and not take_water())
collect(120);stored(1200)
assert(#barrel_actions(nil,false)==0 and barrel_actions()[1]==action and action.mount_valid)
local handlers=0
for _,handler in ipairs(ACTION_HANDLERS)do
 if handler.action==action then assert(handler.state=='doshortaction');handlers=handlers+1 end
end
assert(handlers==2)
local start=clock;local fuel=t._fuel:value();local wear=require('aom_durability').GetUses(tank)
function barrel:is_a(kind)return kind==EntityScript end
function barrel:CollectActions(kind,doer,actions,right)
 assert(kind=='SCENE');SCENE_HOOKS.inspectable(self,doer,actions,right)
end
local picker=make_mouse_picker(player)
local inspect=picker:GetLeftClickActions(Vector3(2,0,0),barrel)[1]
assert(inspect and inspect.action==ACTIONS.LOOKAT and inspect.target==barrel)
local click=picker:GetRightClickActions(Vector3(2,0,0),barrel)[1]
assert(click.action==action and click:Do() and not take_water())
assert(t._refilling_net:value() and not t._working)
clock=start+.1;Refill.Update(t);assert(store:GetWater()==8);stored(1192)
clock=start+1;Refill.Update(t);assert(store:GetWater()==80);stored(1120)
player.Transform:SetPosition(.2,0,0);clock=start+2;Refill.Update(t)
assert(not t._refilling_net:value() and store:GetWater()==80);stored(1120)
assert(take_water());clock=clock+4;Refill.Update(t)
assert(store:GetWater()==400 and not t._refilling_net:value());stored(800)
assert(t._fuel:value()==fuel and require('aom_durability').GetUses(tank)==wear)
assert(#barrel_actions()==0 and not take_water())
''')

    def test_two_drivers_cannot_draw_the_same_dose_and_there_is_no_deposit_action(self):
        self.run_lua('''
collect(7);stored(70)
local other=make_player();local vehicle=SpawnPrefab('aom_tractor_chassis')
local other_tank=SpawnPrefab('aom_irrigator');assert(vehicle:AttachAttachment(nil,other_tank))
other_tank.components.finiteuses:SetUses(0)
assert(ACTIONS.MOUNT.fn({doer=other,target=vehicle}));other.sg:GoToState('mounted_idle')
assert(take_water() and take_water(other));clock=clock+.5
Refill.Update(t);Refill.Update(vehicle)
assert(store:GetWater()==40 and vehicle.components.aom_attachment_store:GetWater()==30);stored(0)
clock=clock+.1;Refill.Update(t);assert(not t._refilling_net:value() and not vehicle._refilling_net:value())
local item=SpawnPrefab('waterballoon');local actions={}
SCENE_HOOKS.inventoryitem(item,player,barrel,actions,true)
assert(#actions==0 and not barrel.components.watersource);stored(0)
''')

    def test_source_removal_permissions_and_replica_prompt(self):
        self.run_lua('''
collect(10)
local pedestrian=make_player();assert(#barrel_actions(pedestrian)==0 and not take_water(pedestrian))
barrel.Transform:SetPosition(10,0,0);assert(not take_water());stored(100)
local old=barrel;TheWorld.ismastersim=false
barrel=SpawnPrefab('aom_rain_barrel');barrel._barrel_water_net:set(100)
assert(barrel:displaynamefn()=='田边蓄水桶'..string.char(10)..'水量 100/2000')
assert(barrel_actions()[1]==action and not take_water() and not barrel._rain_task and not barrel.components.inspectable)
barrel:Remove();barrel=old;TheWorld.ismastersim=true
barrel.Transform:SetPosition(2,0,0);assert(take_water())
clock=clock+.5;Refill.Update(t);assert(store:GetWater()==40);stored(60)
barrel:Remove();assert(not t._refilling_net:value() and not t._aom_pond_refill)
assert(store:GetWater()==40 and not take_water())
''')
