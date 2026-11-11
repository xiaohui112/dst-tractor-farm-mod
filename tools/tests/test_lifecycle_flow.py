"""原版放置/库存/存档组件贯通的玩家操作流程；非DST客户端或真实网络测试。"""
from pathlib import Path
import unittest
import test_native_riding as riding
from test_giant_farming import CONSUME, SEASONS

ROOT=Path(__file__).resolve().parents[2]


class LifecycleFlowTests(unittest.TestCase):
    def setUp(self):
        engine=riding.NativeRidingTests();engine.setUp();self.lua=engine.lua
        defs={}
        for crop,consume in CONSUME.items():
            defs[crop]=self.lua.table_from({
                'nutrient_consumption':self.lua.table_from(consume),
                'nutrient_restoration':self.lua.table_from({i+1:True for i,n in enumerate(consume) if n==0}),
                'good_seasons':self.lua.table_from({s:True for s in SEASONS[crop].split()}),
                'family_min_count':4,'family_check_dist':4,
            })
        self.lua.globals().DEFS=self.lua.table_from(defs)
        self.lua.execute("package.loaded['prefabs/farm_plant_defs'].PLANT_DEFS=DEFS")
        self.lua.execute((ROOT/'tools/tests/lifecycle_engine.lua').read_text())
        self.lua.execute("player=make_player();kit=SpawnPrefab(RECIPE_RECORDS.aom_tractor_chassis.product)")

    def run_lua(self,s):self.lua.execute(s)

    def test_independent_boot_uses_module_containers_and_real_placer(self):
        self.run_lua('''
assert(containers==nil and require('containers').params.aom_tractor_chassis)
assert(RECIPE_RECORDS.aom_tractor_chassis.product=='aom_tractor_item')
local preview=SpawnPrefab('aom_tractor_item_placer')
assert(preview.components.placer.snap_to_tile==true)
assert(preview.components.placer.onfailedplacement==nil)
assert(kit.components.deployable:GetDeployMode()==DEPLOYMODE.CUSTOM)
''')

    def test_real_deploy_rejects_blocked_tile_and_snaps_valid_point(self):
        self.run_lua('''
BLOCKS[key(0,0)]=true
assert(not deploy_kit(kit,1.7,1.7,player) and kit:IsValid())
BLOCKS[key(0,0)]=nil
local wall=CreateEntity();wall.prefab='wall_stone';wall.Transform:SetPosition(0,0,0)
assert(not deploy_kit(kit,1.7,1.7,player) and kit:IsValid())
wall:Remove()
local t=deploy_kit(kit,1.7,1.7,player)
assert(t and t.x==0 and t.z==0 and not kit:IsValid())
''')

    def test_client_boot_has_only_network_state_and_no_server_components(self):
        self.run_lua('''
TheWorld.ismastersim=false
dofile(MOD..'/modmain.lua')
local client=SpawnPrefab('aom_tractor_chassis')
assert(client.components.container==nil and client.components.health==nil)
assert(client._fuel and client._uses_net and client._tooluses_net)
assert(require('containers').params.aom_tractor_chassis and containers==nil)
''')

    def test_dedicated_server_boot_does_not_require_client_input(self):
        self.run_lua('''
TheNet.IsDedicated=function()return true end;TheInput=nil;TheFrontEnd=nil
dofile(MOD..'/modmain.lua')
assert(require('containers').params.aom_tractor_chassis and containers==nil)
local t=deploy_kit(kit,0,0,player)
assert(t.components.container and t.components.rideable)
''')

    def test_refuel_action_consumes_one_stack_unit_even_when_capped(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player);t:SetFuel(799)
local coal=SpawnPrefab('charcoal');coal.components.stackable:SetStackSize(3)
local actions=prompt(coal,player,t)
assert(#actions==1 and actions[1].id=='AOM_REFUEL')
assert(actions[1].fn({doer=player,target=t,invobject=coal}))
assert(t._fuel:value()==800 and coal.components.stackable:StackSize()==2)
assert(not actions[1].fn({doer=player,target=t,invobject=coal}))
assert(coal.components.stackable:StackSize()==2)
coal.components.fuel.fueltype=FUELTYPE.NIGHTMARE;t:SetFuel(0)
assert(#prompt(coal,player,t)==0 and not t:TryRefuel(player,coal))
assert(t._fuel:value()==0)
''')

    def test_out_of_fuel_refill_restores_native_mount(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player);t:SetFuel(0)
assert(not ACTIONS.MOUNT.fn({doer=player,target=t}))
local coal=SpawnPrefab('charcoal');local a=prompt(coal,player,t)[1]
assert(a.fn({doer=player,target=t,invobject=coal}))
assert(not coal:IsValid() and t._fuel:value()==10)
assert(ACTIONS.MOUNT.fn({doer=player,target=t}))
''')

    def test_seed_loading_work_shortage_repair_and_corner_resume(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player);local tool=SpawnPrefab('aom_seeder')
assert(t.components.container:GiveItem(tool,1))
local seeds=SpawnPrefab('tomato_seeds');seeds.components.stackable:SetStackSize(3)
local load=prompt(seeds,player,t)[1]
assert(load.id=='AOM_LOAD' and load.fn({doer=player,target=t,invobject=seeds}))
tool.components.finiteuses:SetUses(1)
SpawnPrefab('farm_soil').Transform:SetPosition(0,0,0)
local corner=SpawnPrefab('farm_soil');corner.Transform:SetPosition(1.99,0,1.99)
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
RPCS.AOM_TOGGLE_WORK(player);require('aom_drive').TrackMovement(t)
assert(tool.components.finiteuses:GetUses()==0 and not t._working and corner:IsValid())
assert(t.components.aom_attachment_store:GetSeedCount()==2 and t._fuel:value()==399)
assert(t._uses_net:value()==999 and t._tooluses_net:value()==0 and t._toolmax_net:value()==100)
assert(t._seedcount_net:value()==2)
ACTIONS.DISMOUNT.fn({doer=player,target=player});player.components.rider:ActualDismount()
local flint=SpawnPrefab('flint');flint.components.stackable:SetStackSize(2)
local repair=prompt(flint,player,t)[1]
assert(repair.fn({doer=player,target=t,invobject=flint}))
assert(tool.components.finiteuses:GetUses()==10 and flint.components.stackable:StackSize()==1)
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
RPCS.AOM_TOGGLE_WORK(player);require('aom_drive').TrackMovement(t)
assert(not corner:IsValid() and tool.components.finiteuses:GetUses()==9)
assert(t._fuel:value()==398 and t.components.aom_attachment_store:GetSeedCount()==1)
assert(t._seedcount_net:value()==1)
''')

    def test_chassis_last_use_stops_then_gears_resume_without_free_work(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player);local tool=SpawnPrefab('aom_seeder')
t.components.container:GiveItem(tool,1)
local seeds=SpawnPrefab('tomato_seeds');seeds.components.stackable:SetStackSize(2)
t.components.container:GiveItem(seeds,2)
local a=SpawnPrefab('farm_soil');local b=SpawnPrefab('farm_soil');b.Transform:SetPosition(1,0,0)
t.components.finiteuses:SetUses(1);t._rider=player;t:SetWorking(true)
local drive=require('aom_drive');local changed,why=drive.WorkTile(t,0,0)
assert(changed and why=='BROKEN_CHASSIS' and not t._working)
assert(t.components.aom_attachment_store:GetSeedCount()==1 and t._fuel:value()==399)
assert(not drive.WorkTile(t,0,0) and t._fuel:value()==399)
local gears=SpawnPrefab('gears');gears.components.stackable:SetStackSize(2)
assert(prompt(gears,player,t)[1].fn({doer=player,target=t,invobject=gears}))
assert(t.components.finiteuses:GetUses()==100 and gears.components.stackable:StackSize()==1)
assert(drive.WorkTile(t,0,0) and t.components.finiteuses:GetUses()==99)
t.components.finiteuses:SetUses(1000)
assert(not t:TryRepair(player,gears) and gears.components.stackable:StackSize()==1)
''')

    def test_full_container_pack_save_reload_redeploy_preserves_all_state(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player);local tool=SpawnPrefab('aom_seeder')
t.components.container:GiveItem(tool,1);tool.components.finiteuses:SetUses(73)
local names={'tomato','carrot','potato','garlic','onion','pepper','corn','pumpkin'}
for i,name in ipairs(names)do
 local seed=SpawnPrefab(name..'_seeds');seed.components.stackable:SetStackSize(i+2)
 assert(t.components.container:GiveItem(seed,i+1))
end
t:SetFuel(167);t.components.finiteuses:SetUses(643);t.components.health:SetVal(321)
t._seed_strategy='GIANT'
require('aom_block_plan').OnLoad(t,{version=2,combo_id='autumn-01-01',season='autumn',x=0,z=0,rotation=1,completed={1,3}})
assert(t._block and t._block.done==2)
t.components.workable:WorkedBy(player,4)
assert(not t:IsValid())
local packed
for _,v in ipairs(ENTITIES)do if v.valid and v.prefab=='aom_tractor_item' then packed=v end end
assert(packed and packed.components.container:GetNumSlots()==9)
local saved=clone(packed:GetSaveRecord());packed:Remove()
-- 模拟重新进入：从原版容器/组件存档创建全新实体。
local restored=SpawnSaveRecord(saved,{})
local placed=deploy_kit(restored,20.7,0.5,player)
assert(placed and placed.x==20 and placed.z==0 and not restored:IsValid())
assert(placed._fuel:value()==167 and placed.components.finiteuses:GetUses()==643)
assert(placed.components.health.currenthealth==321 and placed._seed_strategy=='GIANT')
assert(placed._block.done==2 and placed._block.rotation==1 and placed._block.x==0)
assert(placed.components.container:GetItemInSlot(1).components.finiteuses:GetUses()==73)
for i,name in ipairs(names)do
 local seed=placed.components.container:GetItemInSlot(i+1)
 assert(seed.prefab==name..'_seeds' and seed.components.stackable:StackSize()==i+2)
 assert(seed.components.inventoryitem.owner==placed)
end
assert(placed._uses_net:value()==643 and placed._tooluses_net:value()==73)
''')

    def test_sparse_container_and_empty_water_survive_packing(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player);local tank=SpawnPrefab('aom_irrigator')
assert(tank.components.finiteuses:GetUses()==0)
t.components.container:GiveItem(tank,1)
local seed=SpawnPrefab('carrot_seeds');seed.components.stackable:SetStackSize(9)
t.components.container:GiveItem(seed,9)
t.components.workable:WorkedBy(player,4)
local packed
for _,v in ipairs(ENTITIES)do if v.valid and v.prefab=='aom_tractor_item' then packed=v end end
local record=clone(packed:GetSaveRecord());packed:Remove()
local restored=SpawnSaveRecord(record,{})
local next=deploy_kit(restored,8,0,player)
assert(next.components.container:GetItemInSlot(2)==nil)
assert(next.components.container:GetItemInSlot(9).components.stackable:StackSize()==9)
assert(next._water_net:value()==0 and next._toolmax_net:value()==0)
''')

    def test_death_drops_everything_once_and_cannot_be_packed_into_new_vehicle(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player);local tool=SpawnPrefab('aom_harvester')
t.components.container:GiveItem(tool,1)
local seed=SpawnPrefab('tomato_seeds');seed.components.stackable:SetStackSize(7)
t.components.container:GiveItem(seed,9)
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
t:SetWorking(true);t.components.health:SetVal(0)
assert(not t._working and not t.components.rideable.canride and not t.persists)
assert(not t.components.workable:CanBeWorked())
assert(tool:IsValid() and seed:IsValid() and seed.components.stackable:StackSize()==7)
assert(tool.components.inventoryitem.owner==nil and seed.components.inventoryitem.owner==nil)
t:PushEvent('death')
assert(t.components.container:GetItemInSlot(1)==nil and t.components.container:GetItemInSlot(9)==nil)
t.last_periodic.fn(t)
assert(not t:IsValid() and not player.components.rider:IsRiding())
for _,v in ipairs(ENTITIES)do assert(not (v.valid and v.prefab=='aom_tractor_item'))end
''')

    def test_english_ui_actions_status_and_network_only_durability(self):
        self.run_lua('''
require('aom_common').SetLanguage('en')
GetModConfigData=nil
local env=setmetatable({GLOBAL=_G,GetModConfigData=function(key)if key=='LANGUAGE' then return 'en' end end},{__index=_G})
setfenv(assert(loadfile(MOD..'/modmain.lua')),env)()
local t=deploy_kit(kit,0,0,player);local tool=SpawnPrefab('aom_seeder')
t.components.container:GiveItem(tool,1);tool.components.finiteuses:SetUses(0)
t._rider=player;require('aom_drive').WorkTile(t,0,0)
assert(string.find(t._workreason_net:value(),'Seeder worn out'))
local hud=HUD(player);hud:Refresh(t)
assert(string.find(hud.lines[5].text,'Chassis 1000/1000'))
assert(string.find(hud.lines[5].text,'Tool 0/100'))
assert(hud.seedbutton.text=='Change seed mode')
assert(ACTION_DEFS.AOM_REFUEL.label=='Refuel' and ACTION_DEFS.AOM_REPAIR.label=='Repair')
local proxy={IsValid=function()return true end,_attachment=t._attachment,_fuel=t._fuel,
 _workstatus=t._workstatus,_seedmode_net=t._seedmode_net,_workreason_net=t._workreason_net,
 _uses_net=t._uses_net,_tooluses_net=t._tooluses_net,_toolmax_net=t._toolmax_net}
hud:Refresh(proxy)
assert(string.find(hud.lines[5].text,'Tool 0/100'))
''')

    def test_legacy_dead_save_recovers_contents_after_all_components_load(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player)
t.components.container:GiveItem(SpawnPrefab('aom_seeder'),1)
local seed=SpawnPrefab('tomato_seeds');seed.components.stackable:SetStackSize(6)
t.components.container:GiveItem(seed,9)
local record=clone(t:GetSaveRecord());record.data.health.health=0;t:Remove()
local loaded=SpawnSaveRecord(record,{})
assert(loaded._destroyed and not loaded.components.rideable.canride)
assert(loaded.components.container:GetItemInSlot(1)==nil and loaded.components.container:GetItemInSlot(9)==nil)
local recovered=0
for _,v in ipairs(ENTITIES)do if v.valid and v.prefab=='tomato_seeds' then
 assert(v.components.inventoryitem.owner==nil);recovered=recovered+v.components.stackable:StackSize()
end end
assert(recovered==6)
''')


if __name__=='__main__':unittest.main()
