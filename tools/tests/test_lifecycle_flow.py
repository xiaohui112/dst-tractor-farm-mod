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
        self.lua.execute("player=make_player();kit=SpawnPrefab('aom_tractor_item')")

    def run_lua(self,s):self.lua.execute(s)

    def test_independent_boot_uses_module_containers_and_real_placer(self):
        self.run_lua('''
assert(containers==nil and require('containers').params.aom_tractor_chassis)
assert(RECIPE_RECORDS.aom_tractor_chassis.product=='aom_tractor_chassis')
local preview=SpawnPrefab('aom_tractor_item_placer')
assert(preview.components.placer.snap_to_tile==true)
assert(preview.components.placer.onfailedplacement==nil)
assert(preview.components.placer.onground==false and preview.orientation~=ANIM_ORIENTATION.OnGround)
assert(preview.facing_count==8 and preview.bank=='aom_tractor_chassis' and preview.build=='aom_tractor_chassis')
assert(preview.animation=='idle' and preview.visual_symbols.attachment.symbol=='empty')
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

    def test_seed_loading_breakage_and_replacement_resume_in_same_tile(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player);local tool=SpawnPrefab('aom_seeder')
assert(t:AttachAttachment(nil,tool))
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
assert(t._uses_net:value()==999 and t._tooluses_net:value()==0 and t._toolmax_net:value()==0)
assert(t._seedcount_net:value()==2)
ACTIONS.DISMOUNT.fn({doer=player,target=player});player.components.rider:ActualDismount()
assert(tool:IsValid() and t:GetAttachment()==nil)
local replacement=tool;assert(require('aom_durability').RepairAttachment(replacement))
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
assert(t:AttachAttachment(player,replacement))
RPCS.AOM_TOGGLE_WORK(player);require('aom_drive').TrackMovement(t)
assert(not corner:IsValid() and replacement.components.finiteuses:GetUses()==9)
assert(t._fuel:value()==398 and t.components.aom_attachment_store:GetSeedCount()==1)
assert(t._seedcount_net:value()==1)
''')

    def test_f_seeding_continues_across_tiles_until_empty_and_refill_resumes(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player)
t:AttachAttachment(nil,SpawnPrefab('aom_seeder'))
local seeds=SpawnPrefab('tomato_seeds');seeds.components.stackable:SetStackSize(3)
t.components.container:GiveItem(seeds,2)
for x=0,12,4 do SpawnPrefab('farm_soil').Transform:SetPosition(x,0,0)end
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
local messages={}
player.components.talker={Say=function(_,text)messages[#messages+1]=text end}
press_f(player);release_f(player)
local task=t._worktask
for x=0,4,4 do
 player.Transform:SetPosition(x,0,0);task.fn(t)
 assert(t._working and t._worktask==task and not task.cancelled)
 for i=1,5 do task.fn(t)end
end
assert(t.components.aom_attachment_store:GetSeedCount()==1 and #messages==0)
player.Transform:SetPosition(8,0,0);task.fn(t)
assert(not t._working and not t._worktask and task.cancelled)
assert(t.components.aom_attachment_store:GetSeedCount()==0 and t._fuel:value()==397)
assert(#messages==1 and string.find(messages[1],'种子不足'))
local extra=SpawnPrefab('tomato_seeds');extra.components.stackable:SetStackSize(2)
local load=prompt(extra,player,t)[1]
assert(load.id=='AOM_LOAD' and load.fn({doer=player,target=t,invobject=extra}))
player.Transform:SetPosition(12,0,0);press_f(player);release_f(player);t._worktask.fn(t)
assert(t._working and t.components.aom_attachment_store:GetSeedCount()==1)
assert(t._fuel:value()==396 and not player.attacks)
press_f(player);release_f(player);assert(not t._working and not t._worktask)
''')

    def test_driver_left_click_opens_real_nine_slots_and_stays_open_while_driving(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player)
t:AttachAttachment(nil,SpawnPrefab('aom_seeder'))
local seeds=SpawnPrefab('tomato_seeds');seeds.components.stackable:SetStackSize(17)
t.components.container:GiveItem(seeds,2)
player.components.inventory={opencontainers={}}
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
local picker=make_mouse_picker(player)
local click=picker:GetLeftClickActions(nil,player)[1]
assert(click.action==ACTION_DEFS.AOM_STORAGE and click.action.instant and click.action.mount_valid)
assert(click.action.strfn(click)=='GENERIC' and click:Do())
local c=t.components.container
assert(click.action.strfn(click)=='CLOSE')
assert(c:IsOpenedBy(player) and c:GetNumSlots()==9)
assert(not c.issidewidget and require('containers').MAXITEMSLOTS>=9)
local window={Open=function()end,AddChild=function(_,child)return child end}
POST_FNS['widgets/containerwidget'](window);window:Open(t,player)
assert(window.aom_storage_title.text=='货物与物料' and string.find(window.aom_storage_hint.text,'9格'))
assert(c:GetItemInSlot(2).components.stackable:StackSize()==17)
player.Transform:SetPosition(12,0,0);c:OnUpdate(.1)
assert(c:IsOpenedBy(player))
assert(picker:GetLeftClickActions(nil,player)[1]:Do() and not c:IsOpenedBy(player))
assert(picker:GetLeftClickActions(nil,t)[1]:Do() and c:IsOpenedBy(player))
player.components.rider:ActualDismount();assert(not c:IsOpenedBy(player))
''')

    def test_mouse_closes_and_dismounts_during_rummage_without_window_buttons(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player)
player.components.inventory={opencontainers={}}
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
local picker=make_mouse_picker(player);assert(picker:GetLeftClickActions(nil,player)[1]:Do())
local window={Open=function()end,AddChild=function(_,child)return child end}
POST_FNS['widgets/containerwidget'](window);window:Open(t,player)
assert(window.aom_storage_close==nil and window.aom_storage_dismount==nil)
-- 原版翻找动作可能带 busy，关闭不能被一般作业 RPC 的 busy 检查拦截。
local state_tag=player.sg.HasStateTag
player.sg.HasStateTag=function(_,tag)return tag=='busy' or tag=='keep_pocket_rummage' end
assert(picker:GetLeftClickActions(nil,player)[1]:Do());assert(not t.components.container:IsOpenedBy(player))
player.sg.HasStateTag=state_tag
assert(picker:GetLeftClickActions(nil,player)[1]:Do());assert(t.components.container:IsOpenedBy(player))
player.sg.HasStateTag=function(_,tag)return tag=='busy' or tag=='keep_pocket_rummage' end
local down=picker:GetRightClickActions(nil,player)[1]
assert(down.action==ACTIONS.DISMOUNT and down.target==player and down:Do())
assert(not t.components.container:IsOpenedBy(player) and player.sg.current=='dismount')
player.components.rider:ActualDismount()
assert(not player.components.rider:IsRiding() and t._rider==nil)
''')

    def test_mouse_can_close_storage_and_dismount_without_attachment_or_fuel(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player)
player.components.inventory={opencontainers={}}
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
local picker=make_mouse_picker(player)
local hud=HUD(player);hud:Refresh(t)
assert(hud.storagebutton==nil and hud.dismountbutton==nil and hud.detachbutton==nil)
assert(picker:GetLeftClickActions(nil,player)[1]:Do())
local state_tag=player.sg.HasStateTag
player.sg.HasStateTag=function()return true end
assert(picker:GetLeftClickActions(nil,player)[1]:Do());assert(not t.components.container:IsOpenedBy(player))
player.sg.HasStateTag=state_tag;assert(picker:GetLeftClickActions(nil,player)[1]:Do());t:SetFuel(0)
local other=make_player();RPCS.AOM_DISMOUNT(other);RPCS.AOM_CLOSE_STORAGE(other,t)
assert(t.components.container:IsOpenedBy(player) and player.components.rider:IsRiding())
assert(not ACTION_DEFS.AOM_STORAGE.fn({doer=other,target=player}))
assert(not ACTION_DEFS.AOM_STORAGE.fn({doer=other,target=other}))
assert(picker:GetRightClickActions(nil,t)[1]:Do())
assert(not t.components.container:IsOpenedBy(player) and not t._working and player.sg.current=='dismount')
player.components.rider:ActualDismount();assert(not player.components.rider:IsRiding())
''')

    def test_hud_uses_inventory_scaling_root_and_buttons_stay_above_inventory(self):
        self.run_lua('''
local native_root={AddChild=function(self,child)self.child=child;return child end}
local hud={SetMainCharacter=function(self,owner)self.owner=owner end,
 controls={bottom_root=native_root},inst=CreateEntity()}
POST_FNS['screens/playerhud'](hud);hud:SetMainCharacter(player)
assert(native_root.child==hud.aom_hud)
local panel=hud.aom_hud
assert(panel.storagebutton==nil and panel.dismountbutton==nil)
assert(panel.detachbutton==nil)
for _,button in ipairs({panel.seedbutton,panel.musicbutton})do
 local position=button:GetLocalPosition()
 assert(panel.root.position[2]+panel.seedcontrols.position[2]+position.y>=90)
end
for _,key in ipairs(panel.order)do assert(panel.badges[key].scale[1]==1.4)end
''')

    def test_ground_preview_mount_and_attachments_share_beefalo_scale(self):
        self.run_lua('''
local preview=SpawnPrefab('aom_tractor_item_placer')
local t=deploy_kit(kit,0,0,player)
assert(t.anim_scale[1]==2.5 and preview.transform_scale[1]==t.anim_scale[1])
for _,name in ipairs({'aom_landclearer','aom_seeder','aom_irrigator','aom_fertilizer','aom_weeder','aom_harvester'})do
 local tool=SpawnPrefab(name);assert(tool.anim_scale[1]==2.5)
end
local visual=require('aom_driver_visual')
assert(visual.Configure('test/',function()return true end))
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));assert(player.anim_scale[1]==t.anim_scale[1])
player.components.rider:ActualDismount();assert(player.anim_scale[1]==1)
''')

    def test_right_click_unmount_keeps_cargo_and_driver(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player);local tool=SpawnPrefab('aom_seeder')
assert(t:AttachAttachment(nil,tool))
local seeds=SpawnPrefab('tomato_seeds');seeds.components.stackable:SetStackSize(12)
assert(t.components.container:GiveItem(seeds,1))
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
local action=ACTION_DEFS.AOM_ATTACH;assert(action.fn({doer=player,target=tool}))
assert(t:GetAttachment()==nil and tool:IsValid() and tool.persists and not tool.components.inventoryitem)
assert(t.components.container:GetItemInSlot(1)==seeds and player.components.rider:GetMount()==t)
local hud=HUD(player);hud:Refresh(t);assert(hud.detachbutton==nil)
assert(require('containers').params.aom_tractor_chassis.widget.buttoninfo==nil)
''')

    def test_all_six_unmount_to_world_without_losing_materials(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player)
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
local seeds=SpawnPrefab('tomato_seeds');seeds.components.stackable:SetStackSize(7)
assert(t.components.container:GiveItem(seeds,1))
for _,name in ipairs({'aom_landclearer','aom_seeder','aom_irrigator','aom_fertilizer','aom_weeder','aom_harvester'})do
 local tool=SpawnPrefab(name);assert(t:AttachAttachment(player,tool))
 assert(t:DetachAttachment(player) and tool.persists and not tool.components.inventoryitem)
 assert(t:GetAttachment()==nil and t.components.container:GetItemInSlot(1)==seeds)
 tool:Remove()
end
''')

    def test_four_durable_attachments_break_clear_slot_play_fx_and_preserve_materials(self):
        for name in ('aom_landclearer','aom_seeder','aom_weeder','aom_harvester'):
            with self.subTest(attachment=name):
                self.setUp()
                self.lua.globals().tool_name=name
                self.run_lua('''
local t=deploy_kit(kit,0,0,player)
local tool=SpawnPrefab(tool_name);t:AttachAttachment(nil,tool)
local seeds=SpawnPrefab('tomato_seeds');seeds.components.stackable:SetStackSize(7)
t.components.container:GiveItem(seeds,2)
tool.components.finiteuses:SetUses(1)
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
player.Transform:SetPosition(12,0,4)
local messages={};player.components.talker={Say=function(_,s)messages[#messages+1]=s end}
press_f(player);release_f(player);local task=t._worktask
local broke=0;t:ListenForEvent('toolbroke',function()broke=broke+1 end)
require('aom_durability').UseAttachment(t,tool)
assert(tool:IsValid() and t:GetAttachment()==nil)
assert(not t._working and not t._worktask and task.cancelled and t._atttype_net:value()=='')
assert(t._attachment:value()==nil and t._tooluses_net:value()==0 and t._toolmax_net:value()==0)
assert(t.components.container:GetItemInSlot(2)==seeds and seeds.components.stackable:StackSize()==7)
assert(#messages==1 and string.find(messages[1],'已损坏') and broke==1)
local effects=0
for _,e in ipairs(ENTITIES)do
 if e.prefab=='dirt_puff' then effects=effects+1;assert(e.x==12 and e.z==4)end
end
assert(effects==1)
local flint=SpawnPrefab('flint');assert(not t:TryRepair(player,flint) and flint:IsValid())
tool.components.finiteuses:SetUses(0);assert(broke==1)
local fresh=SpawnPrefab(tool_name);fresh.Transform:SetPosition(player.Transform:GetWorldPosition());assert(t:AttachAttachment(player,fresh))
press_f(player);release_f(player);assert(t._working and t:GetAttachment()==fresh)
''')

    def test_empty_water_and_fertilizer_materials_do_not_destroy_reusable_attachments(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player);local tank=SpawnPrefab('aom_irrigator')
t:AttachAttachment(nil,tank)
local store=t.components.aom_attachment_store;assert(store:AddWater(1)==1 and store:TakeWater())
assert(tank:IsValid() and t:GetAttachment()==tank and store:GetWater()==0)
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
press_f(player);release_f(player);assert(not t._working and tank:IsValid())
assert(t:DetachAttachment(player))
local spreader=SpawnPrefab('aom_fertilizer');t:AttachAttachment(nil,spreader)
assert(spreader.components.finiteuses==nil)
press_f(player);release_f(player);assert(not t._working and spreader:IsValid())
assert(t:GetAttachment()==spreader)
for _,e in ipairs(ENTITIES)do assert(e.prefab~='dirt_puff')end
''')

    def test_water_refill_prompt_consumption_and_visible_instructions(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player);local tank=SpawnPrefab('aom_irrigator')
assert(t:AttachAttachment(nil,tank))
local can=SpawnPrefab('wateringcan');can:AddComponent('finiteuses')
can.components.fillable={};can.components.finiteuses:SetMaxUses(40);can.components.finiteuses:SetUses(7)
local refill=prompt(can,player,t)[1]
assert(refill.id=='AOM_LOAD' and refill.strfn({target=t})=='REFILL')
assert(STRINGS.ACTIONS.AOM_LOAD.REFILL=='补水' and STRINGS.ACTIONS.AOM_LOAD.GENERIC=='装料')
assert(refill.fn({doer=player,target=t,invobject=can}))
assert(t.components.aom_attachment_store:GetWater()==7 and can.components.finiteuses:GetUses()==0 and can:IsValid())
local ice=SpawnPrefab('ice');refill=prompt(ice,player,t)[1]
assert(refill and refill.strfn({target=t})=='REFILL' and refill.fn({doer=player,target=t,invobject=ice}))
assert(not ice:IsValid() and t.components.aom_attachment_store:GetWater()==8)
local HUD=require('widgets/aom_hud');local hud=HUD(player);hud:Refresh(t)
assert(string.find(hud.badges.water:GetTooltip(),'车尾',1,true) and string.find(hud.badges.water:GetTooltip(),'5秒',1,true))
local store=t.components.aom_attachment_store
for i=1,8 do assert(store:TakeWater())end
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
press_f(player);release_f(player)
assert(not t._working and string.find(require('aom_work_status').Describe(t),'右键池塘',1,true))
''')

    def test_refill_instruction_and_action_label_are_localized(self):
        self.run_lua('''
GetModConfigData=function(name)if name=='LANGUAGE' then return 'en' end end
dofile(MOD..'/modmain.lua')
local t=deploy_kit(kit,0,0,player)
assert(t:AttachAttachment(nil,SpawnPrefab('aom_irrigator')))
local ice=SpawnPrefab('ice');local refill=prompt(ice,player,t)[1]
assert(refill.strfn({target=t})=='REFILL' and STRINGS.ACTIONS.AOM_LOAD.REFILL=='Refill water')
local HUD=require('widgets/aom_hud');local hud=HUD(player);hud:Refresh(t)
assert(string.find(hud.badges.water:GetTooltip(),'refill over 5 seconds',1,true))
''')

    def test_all_seven_recipes_require_alchemy_engine_for_first_unlock(self):
        self.run_lua('''
local n=0
for name,tech in pairs(RECIPE_TECH)do assert(tech==TECH.SCIENCE_TWO,name);n=n+1 end
assert(n==7 and RECIPE_RECORDS.aom_tractor_chassis.product=='aom_tractor_chassis')
for _,name in ipairs({'aom_tractor_chassis','aom_landclearer','aom_seeder','aom_irrigator',
 'aom_fertilizer','aom_weeder','aom_harvester'})do assert(RECIPE_TECH[name]==TECH.SCIENCE_TWO)end
''')

    def test_chassis_last_use_stops_then_gears_resume_without_free_work(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player);local tool=SpawnPrefab('aom_seeder')
t:AttachAttachment(nil,tool)
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
t:AttachAttachment(nil,tool);tool.components.finiteuses:SetUses(73)
local names={'tomato','carrot','potato','garlic','onion','pepper','corn','pumpkin'}
for i,name in ipairs(names)do
 local seed=SpawnPrefab(name..'_seeds');seed.components.stackable:SetStackSize(i+2)
 assert(t.components.container:GiveItem(seed,i+1))
end
t:SetFuel(167);t.components.finiteuses:SetUses(643);t.components.health:SetVal(321)
t._seed_strategy='GIANT'
require('aom_block_plan').OnLoad(t,{version=3,combo_id='autumn-01-01',season='autumn',x=0,z=0,rotation=1,confirmed=true,completed={1,3}})
assert(t._block and t._block.done==2)
local saved=clone(t:GetSaveRecord());t:Remove();tool:Remove()
local placed=SpawnSaveRecord(saved,{})
placed.Transform:SetPosition(20,0,0)
assert(placed._fuel:value()==167 and placed.components.finiteuses:GetUses()==643)
assert(placed.components.health.currenthealth==321 and placed._seed_strategy=='GIANT')
assert(placed._block.done==2 and placed._block.rotation==1 and placed._block.x==0)
assert(placed:GetAttachment().components.finiteuses:GetUses()==73)
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
t:AttachAttachment(nil,tank)
local seed=SpawnPrefab('carrot_seeds');seed.components.stackable:SetStackSize(9)
t.components.container:GiveItem(seed,9)
local record=clone(t:GetSaveRecord());t:Remove();tank:Remove()
local next=SpawnSaveRecord(record,{})
assert(next.components.container:GetItemInSlot(2)==nil)
assert(next.components.container:GetItemInSlot(9).components.stackable:StackSize()==9)
assert(next._water_net:value()==0 and next._toolmax_net:value()==60)
''')

    def test_death_drops_everything_once_and_preserves_repairable_wreck(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player);local tool=SpawnPrefab('aom_harvester')
t:AttachAttachment(nil,tool)
local seed=SpawnPrefab('tomato_seeds');seed.components.stackable:SetStackSize(7)
t.components.container:GiveItem(seed,9)
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
t:SetWorking(true);t.components.health:SetVal(0)
assert(not t._working and not t.components.rideable.canride and t.persists)
assert(t.components.workable:CanBeWorked() and t._wreck_net:value())
assert(tool:IsValid() and seed:IsValid() and seed.components.stackable:StackSize()==7)
assert(tool.components.inventoryitem==nil and seed.components.inventoryitem.owner==nil)
t:PushEvent('death')
assert(t:GetAttachment()==nil and t.components.container:GetItemInSlot(9)==nil)
assert(t:IsValid() and not player.components.rider:IsRiding())
assert(t.components.health.nofadeout and t.animation=='death')
for _,v in ipairs(ENTITIES)do assert(not (v.valid and v.prefab=='aom_tractor_item'))end
''')

    def test_english_ui_actions_status_and_network_only_durability(self):
        self.run_lua('''
require('aom_common').SetLanguage('en')
GetModConfigData=nil
local env=setmetatable({GLOBAL=_G,GetModConfigData=function(key)if key=='LANGUAGE' then return 'en' end end},{__index=_G})
setfenv(assert(loadfile(MOD..'/modmain.lua')),env)()
local t=deploy_kit(kit,0,0,player);local tool=SpawnPrefab('aom_seeder')
t:AttachAttachment(nil,tool);tool.components.finiteuses:SetUses(0)
-- 保持种子充足，单独验证挂件耐久耗尽时的英文反馈。
t.components.container:GiveItem(SpawnPrefab('tomato_seeds'),2)
assert(tool:IsValid() and t._atttype_net:value()=='')
assert(string.find(require('aom_work_status').Describe(t),'Seeder broke'))
local hud=HUD(player);hud:Refresh(t)
assert(string.find(hud.badges.chassis:GetTooltip(),'Chassis 1000/1000'))
assert(not string.find(hud.badges.chassis:GetTooltip(),'Tool'))
assert(hud.lines==nil and not hud.seedbutton.text.visible)
assert(ACTION_DEFS.AOM_REFUEL.label=='Refuel' and ACTION_DEFS.AOM_REPAIR.label=='Repair')
local proxy={IsValid=function()return true end,_attachment=t._attachment,_fuel=t._fuel,
 _workstatus=t._workstatus,_seedmode_net=t._seedmode_net,_workstate_net=t._workstate_net,
 _uses_net=t._uses_net,_tooluses_net=t._tooluses_net,_toolmax_net=t._toolmax_net}
hud:Refresh(proxy)
assert(not string.find(hud.badges.chassis:GetTooltip(),'Tool'))
''')

    def test_legacy_dead_save_recovers_contents_after_all_components_load(self):
        self.run_lua('''
local t=deploy_kit(kit,0,0,player)
t:AttachAttachment(nil,SpawnPrefab('aom_seeder'))
local seed=SpawnPrefab('tomato_seeds');seed.components.stackable:SetStackSize(6)
t.components.container:GiveItem(seed,9)
local record=clone(t:GetSaveRecord());record.data.health.health=0;t:Remove()
local loaded=SpawnSaveRecord(record,{})
assert(loaded._destroyed and not loaded.components.rideable.canride)
assert(loaded:GetAttachment()==nil and loaded.components.container:GetItemInSlot(9)==nil)
local recovered=0
for _,v in ipairs(ENTITIES)do if v.valid and v.prefab=='tomato_seeds' then
 assert(v.components.inventoryitem.owner==nil);recovered=recovered+v.components.stackable:StackSize()
end end
assert(recovered==6)
''')


if __name__=='__main__':unittest.main()
