"""执行原版骑牛组件和动作，验证拖拉机接入；动画、网络仍需 DST 实机验收。"""
from pathlib import Path
import unittest
from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[2]


class NativeRidingTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        for name, value in {
            'REF': ROOT / 'tools/api-ref',
            'MOD': ROOT / 'mod/Tractor',
            'SCRIPTS': ROOT / 'mod/Tractor/scripts',
        }.items():
            self.lua.globals()[name] = str(value)
        self.lua.execute((ROOT / 'tools/tests/riding_engine.lua').read_text())
        self.lua.execute('t=make_tractor();p=make_player()')

    def run_lua(self, source):
        self.lua.execute(source)

    def test_native_mount_prompt_and_no_duplicate_mod_action(self):
        self.run_lua('''
assert(not t:HasTag('NOCLICK') and t:HasTag('rideable'))
assert(not t:HasTag('saddleable'))
local actions={};SCENE.rideable(t,p,actions,true)
assert(#actions==1 and actions[1]==ACTIONS.MOUNT)
assert(SCENE_HOOKS.aom_tractor_work==nil)
assert(RPCS.AOM_TOGGLE_DRIVE==nil)
''')

    def test_native_mount_and_actual_dismount_stop_work(self):
        self.run_lua('''
assert(ACTIONS.MOUNT.fn({doer=p,target=t}))
assert(p.components.rider:GetMount()==t and t._rider==p)
assert(t.hidden and t.parent==p and p.sg.current=='mount')
p.sg:GoToState('mounted_idle')
t._attachment_type='plow';assert(t:ToggleWorking(p))
local actions={};SCENE.rider(p,p,actions)
assert(#actions==1 and actions[1]==ACTIONS.DISMOUNT)
assert(ACTIONS.DISMOUNT.fn({doer=p,target=p}))
assert(p.sg.current=='dismount' and p.components.rider:IsRiding())
p.components.rider:ActualDismount()
assert(not p.components.rider:IsRiding() and p.components.rider:GetMount()==nil)
assert(not t.hidden and t.parent==nil and t._rider==nil)
assert(not t._working and t._worktask==nil)
assert(t.sg.current=='idle' and t.animation=='idle')
''')

    def test_open_container_closes_before_dismount(self):
        self.run_lua('''
ACTIONS.MOUNT.fn({doer=p,target=t});t.opened=true
local actions={};SCENE.rider(p,p,actions)
assert(actions[1]==ACTIONS.RUMMAGE)
t.opened=false;actions={};SCENE.rider(p,p,actions)
assert(actions[1]==ACTIONS.DISMOUNT)
''')

    def test_seat_cannot_be_taken_by_another_player(self):
        self.run_lua('''
assert(ACTIONS.MOUNT.fn({doer=p,target=t}))
local other=make_player()
local ok,reason=ACTIONS.MOUNT.fn({doer=other,target=t})
assert(not ok and reason=='INUSE')
assert(t._rider==p and not other.components.rider:IsRiding())
assert(not ACTIONS.DISMOUNT.fn({doer=other,target=p}))
''')

    def test_no_fuel_disables_native_mount_and_refill_restores_it(self):
        self.run_lua('''
t:SetFuel(0)
assert(not t.components.rideable.canride and not t:HasTag('rideable'))
local actions={};SCENE.rideable(t,p,actions,true);assert(#actions==0)
assert(not ACTIONS.MOUNT.fn({doer=p,target=t}))
t:SetFuel(50)
assert(t.components.rideable.canride and t:HasTag('rideable'))
assert(ACTIONS.MOUNT.fn({doer=p,target=t}))
''')

    def test_native_dead_and_frozen_mount_rejection(self):
        self.run_lua('''
t.dead=true;assert(not ACTIONS.MOUNT.fn({doer=p,target=t}))
t.dead=false;t.components.freezable={IsFrozen=function()return true end}
assert(not ACTIONS.MOUNT.fn({doer=p,target=t}))
assert(not p.components.rider:IsRiding())
''')

    def test_running_out_of_fuel_still_allows_native_dismount(self):
        self.run_lua('''
ACTIONS.MOUNT.fn({doer=p,target=t});p.sg:GoToState('mounted_idle')
local drive=require('aom_drive');drive.WorkHere=function()return true end
t:SetFuel(1);t:SetWorking(true)
TheWorld.Map={GetTileCenterPoint=function()return 0,0,0 end}
t.last_periodic.fn(t)
assert(t._fuel:value()==0 and not t.components.rideable.canride)
assert(ACTIONS.DISMOUNT.fn({doer=p,target=p}))
p.components.rider:ActualDismount()
assert(not p.components.rider:IsRiding() and not t._working)
''')

    def test_rpc_uses_actual_driver_and_rejects_unmounted_or_busy_player(self):
        self.run_lua('''
t._attachment_type='plow';RPCS.AOM_TOGGLE_WORK(p);assert(not t._working)
ACTIONS.MOUNT.fn({doer=p,target=t})
RPCS.AOM_TOGGLE_WORK(p);assert(not t._working)
p.sg:GoToState('mounted_idle')
RPCS.AOM_TOGGLE_WORK(p);assert(t._working)
RPCS.AOM_TOGGLE_WORK(make_player());assert(t._working)
RPCS.AOM_TOGGLE_WORK(p);assert(not t._working)
''')

    def test_f_controls_work_and_hud_keeps_seed_mode_button(self):
        self.run_lua('''
ACTIONS.MOUNT.fn({doer=p,target=t});p.sg:GoToState('mounted_idle')
CLIENT_PLAYER=p;t._attachment_type='seeder';t._atttype_net:set('seeder')
t.components.aom_attachment_store.GetSeedCount=function()return 10 end
local attachment={prefab='aom_seeder',IsValid=function()return true end}
t._attachment:set(attachment)
local hud=HUD(p);hud:Refresh(t)
assert(hud.workbutton==nil and hud.seedbutton.visible)
assert(string.find(hud.worklamp:GetTooltip(),'F'))
press_f(p);release_f(p);hud:Refresh(t)
assert(t._working and not p.attacks)
hud.seedbutton.onclick();assert(t._seed_strategy=='RANDOM')
t._attachment:set(nil);t._atttype_net:set('');hud:Refresh(t);assert(not hud.seedbutton.visible)
hud:Refresh(nil);assert(not hud.visible)
''')

    def test_f_is_debounced_and_never_generates_held_attack(self):
        self.run_lua('''
ACTIONS.MOUNT.fn({doer=p,target=t});p.sg:GoToState('mounted_idle');t._attachment_type='plow'
press_f(p);assert(t._working)
press_f(p);assert(t._working and not p.attacks)
assert(not p.components.playercontroller:IsControlPressed(CONTROL_ATTACK))
release_f(p);press_f(p);assert(not t._working and not p.attacks);release_f(p)
''')

    def test_f_toggles_working_for_every_attachment_type(self):
        """六种挂件都必须 F 开=F 关，不因挂件类型被区别对待。"""
        self.run_lua('''
ACTIONS.MOUNT.fn({doer=p,target=t});p.sg:GoToState('mounted_idle')
local store=t.components.aom_attachment_store
store.GetSeedCount=function()return 100 end
store.GetWater=function()return 40 end
store.GetFertilizerCount=function()return 100 end
for _,kind in ipairs({'plow','seeder','irrigator','fertilizer','weeder','harvester'}) do
    t._attachment_type=kind;t._atttype_net:set(kind);t._working=false
    press_f(p);release_f(p);assert(t._working,kind)
    press_f(p);release_f(p);assert(not t._working,kind)
end
''')

    def test_all_six_attachments_keep_working_after_f_release_until_toggled_off(self):
        # 验证真实按键、RPC、周期任务与跨格调度；农业效果由各配件流程测试覆盖。
        self.run_lua('''
assert(ACTIONS.MOUNT.fn({doer=p,target=t}));p.sg:GoToState('mounted_idle')
local drive=require('aom_drive')
TheWorld.Map={GetTileCenterPoint=function(_,x,y,z)return math.floor((x+2)/4)*4,0,math.floor((z+2)/4)*4 end}
local store=t.components.aom_attachment_store
store.GetSeedCount=function()return 100 end
store.GetWater=function()return 40 end
store.GetFertilizerCount=function()return 100 end
for _,kind in ipairs({'plow','seeder','irrigator','fertilizer','weeder','harvester'})do
 t._attachment_type=kind
 local tool=CreateEntity();tool.attachment_type=kind;tool._aom_working=net(false)
 tool.components.finiteuses={GetUses=function()return 100 end}
 t._aom_attachment=tool;tool._aom_vehicle=tool._aom_vehicle or net(t);tool._aom_vehicle:set(t)
 local calls={}
 drive.WorkHere=function(_,x,z)
  local key=x..':'..z
  if calls[key] then return false,'NOTHING_TO_DO',true end
  calls[key]=true;return true,nil,true
 end
 p.Transform:SetPosition(0,0,0)
 press_f(p);release_f(p)
 local task=t._worktask
 assert(t._working and task)
 task.fn(t);p.Transform:SetPosition(8,0,0);task.fn(t)
 assert(calls['0:0'] and calls['4:0'] and calls['8:0'])
 for i=1,10 do task.fn(t)end
 assert(t._working and not task.cancelled and not p.attacks)
 press_f(p);release_f(p)
 assert(not t._working and task.cancelled and not t._worktask)
end
''')

    def test_f_rejects_empty_materials_immediately_and_allows_refill_retry(self):
        for kind, message, getter in (
            ('seeder', '种子不足', 'GetSeedCount'),
            ('irrigator', '水箱已空', 'GetWater'),
            ('fertilizer', '肥料不足', 'GetFertilizerCount'),
        ):
            with self.subTest(attachment=kind):
                self.setUp()
                self.lua.globals().kind = kind
                self.lua.globals().message = message
                self.lua.globals().getter = getter
                self.run_lua('''
assert(ACTIONS.MOUNT.fn({doer=p,target=t}));p.sg:GoToState('mounted_idle')
t._attachment_type=kind
local messages={}
p.components.talker={Say=function(_,text)messages[#messages+1]=text end}
for i=1,2 do
 press_f(p);release_f(p)
 assert(not t._working and not t._worktask and not t._workstatus:value())
 assert(#messages==i and string.find(messages[i],message))
 assert(messages[i]==require('aom_work_status').Describe(t) and not p.attacks)
end
t.components.aom_attachment_store[getter]=function()return 10 end
press_f(p);release_f(p)
assert(t._working and t._worktask and require('aom_work_status').Describe(t)=='' and #messages==2)
press_f(p);release_f(p);assert(not t._working and not t._worktask)
''')

    def test_f_keeps_vanilla_attack_on_foot_and_respects_input_focus(self):
        self.run_lua('''
press_f(p);release_f(p);assert(p.attacks==1)
ACTIONS.MOUNT.fn({doer=p,target=t});p.sg:GoToState('mounted_idle');t._attachment_type='plow'
p.input_blocked=true;press_f(p);release_f(p);assert(not t._working)
p.input_blocked=false;TheFrontEnd.textProcessorWidget={}
press_f(p);release_f(p);assert(not t._working)
TheFrontEnd.textProcessorWidget=nil;PAUSED=true
press_f(p);release_f(p);assert(not t._working)
''')

    def test_mount_defaults_off_and_dismount_request_stops_work_immediately(self):
        self.run_lua('''
t._working=true;ACTIONS.MOUNT.fn({doer=p,target=t});assert(not t._working)
p.sg:GoToState('mounted_idle');t._attachment_type='plow';press_f(p);release_f(p)
assert(t._working)
ACTIONS.DISMOUNT.fn({doer=p,target=p});assert(not t._working and p.sg.current=='dismount')
p.components.rider:ActualDismount()
ACTIONS.MOUNT.fn({doer=p,target=t});assert(not t._working)
''')

    def test_work_speed_updates_native_client_prediction(self):
        self.run_lua('''
p.replica.rider.classified={riderrunspeed=net(0)}
ACTIONS.MOUNT.fn({doer=p,target=t});p.sg:GoToState('mounted_idle')
t._attachment_type='plow';press_f(p);release_f(p)
assert(math.abs(t.components.locomotor.runspeed-6*3.75/7)<1e-8)
assert(p.replica.rider.classified.riderrunspeed:value()==t.components.locomotor.runspeed)
press_f(p);release_f(p)
assert(t.components.locomotor.runspeed==6 and p.replica.rider.classified.riderrunspeed:value()==6)
''')

    def test_ridden_tractor_is_in_native_player_save(self):
        self.run_lua('''
ACTIONS.MOUNT.fn({doer=p,target=t})
local data=p.components.rider:OnSave()
assert(data.mount and data.mount.prefab=='aom_tractor_chassis')
assert(data.mount.data.fuel==400)
''')

    def test_flint_repair_action_caps_uses_and_consumes_one_item(self):
        self.run_lua('''
local prefabs={dofile(SCRIPTS..'/prefabs/aom_attachments.lua')}
local tool=prefabs[1].fn()
t._aom_attachment=tool;tool._aom_vehicle=tool._aom_vehicle or net(t);tool._aom_vehicle:set(t)
t:PushEvent('itemget')
tool.components.finiteuses:SetUses(58)
local remaining=3
local flint={prefab='flint',components={},IsValid=function()return true end}
flint.components.stackable={StackSize=function()return remaining end,
 Get=function(_,n)remaining=remaining-n;return {Remove=function()end}end}
local actions={};SCENE_HOOKS.inventoryitem(flint,p,t,actions,true)
assert(#actions==1 and actions[1].id=='AOM_REPAIR')
assert(actions[1].fn({doer=p,target=t,invobject=flint}))
assert(tool.components.finiteuses:GetUses()==60 and remaining==2)
assert(not t:TryRepair(p,flint) and remaining==2)
tool.components.finiteuses:SetUses(0)
assert(tool:IsValid() and not t:TryRepair(p,flint) and remaining==2)
assert(not t._working)
''')

    def test_flint_does_not_repair_water_or_other_attachments(self):
        self.run_lua('''
local prefabs={dofile(SCRIPTS..'/prefabs/aom_attachments.lua')}
local seeder
for _,prefab in ipairs(prefabs)do if prefab.name=='aom_fertilizer' then seeder=prefab.fn()end end
t._aom_attachment=seeder;seeder._aom_vehicle=seeder._aom_vehicle or net(t);seeder._aom_vehicle:set(t);t:PushEvent('itemget')
local flint={prefab='flint',components={},IsValid=function()return true end,
 Remove=function()error('must not consume flint')end,HasTag=function()return false end}
local actions={};SCENE_HOOKS.inventoryitem(flint,p,t,actions,true)
assert(#actions==0 and not t:TryRepair(p,flint))
''')

    def test_weeder_flint_repairs_before_zero_and_cannot_restore_broken_item(self):
        self.run_lua('''
local tool
for _,prefab in ipairs({dofile(SCRIPTS..'/prefabs/aom_attachments.lua')})do
 if prefab.name=='aom_weeder' then tool=prefab.fn()end
end
t._aom_attachment=tool;tool._aom_vehicle=tool._aom_vehicle or net(t);tool._aom_vehicle:set(t);t:PushEvent('itemget')
tool.components.finiteuses:SetUses(1)
assert(tool:IsValid())
local remaining=3
local flint={prefab='flint',components={},IsValid=function()return true end}
flint.components.stackable={StackSize=function()return remaining end,
 Get=function(_,n)remaining=remaining-n;return {Remove=function()end}end}
local actions={};SCENE_HOOKS.inventoryitem(flint,p,t,actions,true)
assert(#actions==1 and actions[1].id=='AOM_REPAIR')
assert(actions[1].fn({doer=p,target=t,invobject=flint}))
assert(tool.components.finiteuses:GetUses()==11 and remaining==2)
tool.components.finiteuses:SetUses(49)
assert(t:TryRepair(p,flint) and tool.components.finiteuses:GetUses()==50 and remaining==1)
assert(not t:TryRepair(p,flint) and remaining==1)
tool.components.finiteuses:SetUses(0)
assert(tool:IsValid() and not t:TryRepair(p,flint) and remaining==1)
''')

    def test_water_load_prompt_action_sync_and_hud(self):
        self.run_lua('''
local prefabs={dofile(SCRIPTS..'/prefabs/aom_attachments.lua')}
local tank
for _,prefab in ipairs(prefabs)do if prefab.name=='aom_irrigator' then tank=prefab.fn();tank.prefab=prefab.name end end
t._aom_attachment=tank;tank._aom_vehicle=tank._aom_vehicle or net(t);tank._aom_vehicle:set(t);t:PushEvent('itemget')
local can=CreateEntity();can.prefab='wateringcan';can:AddComponent('finiteuses');can.components.finiteuses:SetUses(15)
can.components.fillable={}
local actions={};SCENE_HOOKS.inventoryitem(can,p,t,actions,true)
assert(#actions==1 and actions[1].id=='AOM_LOAD')
assert(actions[1].fn({doer=p,target=t,invobject=can}))
assert(t._water_net:value()==15 and t._watermax_net:value()==40 and can.components.finiteuses:GetUses()==0)
local hud=HUD(p);hud:Refresh(t);assert(string.find(hud.resource_num:GetString(),'15/40'))
tank.components.finiteuses:Use(1);assert(t._water_net:value()==14)
SCENE_HOOKS.inventoryitem(can,p,t,{},false)
local wrong=CreateEntity();wrong.prefab='other';wrong.components.fillable={};wrong:AddComponent('finiteuses')
actions={};SCENE_HOOKS.inventoryitem(wrong,p,t,actions,true);assert(#actions==0)
assert(not ACTION_DEFS.AOM_LOAD.fn({doer=p,target=t,invobject=wrong}))
''')

    def test_harvester_flint_repair_prompt_caps_at_forty_and_consumes_one(self):
        self.run_lua('''
local tool
for _,prefab in ipairs({dofile(SCRIPTS..'/prefabs/aom_attachments.lua')})do
 if prefab.name=='aom_harvester' then tool=prefab.fn()end
end
t._aom_attachment=tool;tool._aom_vehicle=tool._aom_vehicle or net(t);tool._aom_vehicle:set(t);t:PushEvent('itemget')
tool.components.finiteuses:SetUses(1)
assert(tool:IsValid())
local remaining=3
local flint={prefab='flint',components={},IsValid=function()return true end}
flint.components.stackable={StackSize=function()return remaining end,
 Get=function(_,n)remaining=remaining-n;return {Remove=function()end}end}
local actions={};SCENE_HOOKS.inventoryitem(flint,p,t,actions,true)
assert(#actions==1 and actions[1].id=='AOM_REPAIR')
assert(actions[1].fn({doer=p,target=t,invobject=flint}))
assert(tool.components.finiteuses:GetUses()==11 and remaining==2)
tool.components.finiteuses:SetUses(39)
assert(t:TryRepair(p,flint) and tool.components.finiteuses:GetUses()==40 and remaining==1)
assert(not t:TryRepair(p,flint) and remaining==1)
''')

    def test_swap_same_type_tank_stops_and_detaches_old_water_listener(self):
        self.run_lua('''
local prefabs={dofile(SCRIPTS..'/prefabs/aom_attachments.lua')};local create
for _,prefab in ipairs(prefabs)do if prefab.name=='aom_irrigator' then create=prefab.fn end end
local tank=create();local current=tank
t.GetAttachment=function()return current end;t:PushEvent('itemget')
tank.components.finiteuses:SetUses(10);t:SetWorking(true)
current=create();current.components.finiteuses:SetUses(3);t:PushEvent('itemget')
assert(not t._working and t._water_net:value()==3)
tank.components.finiteuses:SetUses(7);assert(t._water_net:value()==3)
current=nil;t:PushEvent('itemlose');assert(t._water_net:value()==0 and t._watermax_net:value()==0)
''')

    def test_fertilizer_hud_real_doses_prompt_and_material_listener(self):
        self.run_lua('''
local prefabs={dofile(SCRIPTS..'/prefabs/aom_attachments.lua')};local attachment
for _,prefab in ipairs(prefabs)do if prefab.name=='aom_fertilizer' then attachment=prefab.fn();attachment.prefab=prefab.name end end
assert(attachment.components.finiteuses==nil)
local item=CreateEntity();item.prefab='fertilizer';item:AddTag('fertilizer');item:AddComponent('finiteuses')
item.components.finiteuses:SetMaxUses(5);item.components.finiteuses:SetUses(5)
item.components.fertilizer={nutrients={0,0,16}}
local current=item
t.components.container.numslots=9
t._aom_attachment=attachment;t.components.container.GetItemInSlot=function(_,slot)if slot==2 then return current end end
t:PushEvent('itemget');assert(t._fertilizeruses_net:value()==5)
local actions={};SCENE_HOOKS.inventoryitem(item,p,t,actions,true)
assert(#actions==1 and actions[1].id=='AOM_LOAD')
local hud=HUD(p);hud:Refresh(t);assert(string.find(hud.resource:GetTooltip(),'肥料剩余 5 次'))
item.components.finiteuses:Use(1);assert(t._fertilizeruses_net:value()==4)
current=nil;t:PushEvent('itemlose');assert(t._fertilizeruses_net:value()==0)
item.components.finiteuses:Use(1);assert(t._fertilizeruses_net:value()==0)
''')

    def test_removing_ridden_tractor_releases_player(self):
        self.run_lua('''
ACTIONS.MOUNT.fn({doer=p,target=t});t:Remove()
assert(not p.components.rider:IsRiding())
assert(p.components.rider:GetMount()==nil and t._rider==nil)
''')

    def test_client_prefab_exposes_native_mount_tag(self):
        self.run_lua('''
TheWorld.ismastersim=false
local client=make_tractor()
assert(client:HasTag('rideable') and not client:HasTag('NOCLICK'))
local actions={};SCENE.rideable(client,p,actions,true)
assert(#actions==1 and actions[1]==ACTIONS.MOUNT)
''')


if __name__ == '__main__':
    unittest.main()
