"""原版Rider/拖拉机接入：行驶耗油独立于农业作业与挂件。"""
import unittest
import test_native_riding as native


class DrivingFuelTests(unittest.TestCase):
    setUp = native.NativeRidingTests.setUp
    run_lua = native.NativeRidingTests.run_lua

    def test_empty_driving_counts_distance_and_stationary_costs_nothing(self):
        self.run_lua('''
assert(ACTIONS.MOUNT.fn({doer=p,target=t}))
local task=t._drivetask
assert(task and not t._working and not t._attachment_type)
for i=1,100 do task.fn(t) end
assert(t._fuel:value()==400)
-- 不要求跨地块：小步移动同样结算，停车和单纯转向没有距离成本。
for i=1,16 do p.Transform:SetPosition(i*.25,0,0);task.fn(t) end
assert(t._fuel:value()==399)
p.Transform:SetRotation(90);task.fn(t);assert(t._fuel:value()==399)
p.Transform:SetPosition(7,0,4);task.fn(t) -- 斜向5距离，扣1.25。
assert(t._fuel:value()==397.75)
''')

    def test_all_six_attachments_and_f_toggles_keep_same_travel_task(self):
        self.run_lua('''
assert(ACTIONS.MOUNT.fn({doer=p,target=t}))
local drive=require('aom_drive');local task=t._drivetask;local x=0
for _,kind in ipairs({'plow','seeder','irrigator','fertilizer','weeder','harvester'}) do
 t._attachment_type=kind
 for _,working in ipairs({false,true,false}) do
  t:SetWorking(working)
  assert(t._drivetask==task and not task.cancelled)
  local before=t._fuel:value();x=x+4;p.Transform:SetPosition(x,0,0);task.fn(t)
  assert(t._fuel:value()==before-1,kind)
 end
end
drive.StopForReason(t,'EMPTY')
local before=t._fuel:value();x=x+4;p.Transform:SetPosition(x,0,0);task.fn(t)
assert(not t._working and t._fuel:value()==before-1)
''')

    def test_movement_and_successful_work_are_both_charged(self):
        self.run_lua('''
assert(ACTIONS.MOUNT.fn({doer=p,target=t}))
local drive=require('aom_drive')
t._attachment_type='plow';t:SetWorking(true)
drive.WorkHere=function()return true end
assert(drive.WorkTile(t,0,0));assert(t._fuel:value()==399)
p.Transform:SetPosition(4,0,0);t._drivetask.fn(t)
assert(t._fuel:value()==398)
assert(drive.WorkTile(t,4,0));assert(t._fuel:value()==397)
''')

    def test_empty_tank_stops_work_server_and_client_then_refuel_restores_speed(self):
        self.run_lua('''
p.replica.rider.classified={riderrunspeed=net(0)}
local stops=0;local messages={}
p:AddComponent('locomotor');p.components.locomotor.Stop=function()stops=stops+1 end
p.components.talker={Say=function(_,text)messages[#messages+1]=text end}
assert(ACTIONS.MOUNT.fn({doer=p,target=t}));p.sg:GoToState('mounted_idle')
t._attachment_type='plow';t:SetWorking(true);t:SetFuel(.1)
local worktask=t._worktask;local task=t._drivetask
p.Transform:SetPosition(1,0,0);task.fn(t)
assert(t._fuel:value()==0 and not t.components.rideable.canride)
assert(not t._working and worktask.cancelled and t._worktask==nil)
assert(t.components.locomotor.runspeed==0 and t.components.locomotor.walkspeed==0)
assert(p.replica.rider.classified.riderrunspeed:value()==0 and t._speedfactor_net:value()==0)
assert(stops==1 and #messages==1 and string.find(messages[1],'燃料不足'))
for i=1,10 do task.fn(t) end
assert(t._fuel:value()==0 and #messages==1)
t:SetFuel(15)
assert(t.components.rideable.canride and not t._working)
assert(t.components.locomotor.runspeed==3 and p.replica.rider.classified.riderrunspeed:value()==3)
p.Transform:SetPosition(5,0,0);task.fn(t);assert(t._fuel:value()==14)
assert(ACTIONS.DISMOUNT.fn({doer=p,target=p}));p.components.rider:ActualDismount()
assert(not p.components.rider:IsRiding())
''')

    def test_work_exhausting_fuel_also_prevents_empty_driving(self):
        self.run_lua('''
assert(ACTIONS.MOUNT.fn({doer=p,target=t}))
local drive=require('aom_drive');t._attachment_type='plow'
drive.WorkHere=function()return true end
t:SetFuel(1);t:SetWorking(true);assert(drive.WorkTile(t,0,0))
assert(t._fuel:value()==0 and t.components.locomotor.runspeed==0 and not t._working)
t:SetWorking(false);assert(t.components.locomotor.runspeed==0)
assert(ACTIONS.DISMOUNT.fn({doer=p,target=p}));p.components.rider:ActualDismount()
''')

    def test_dismount_settles_last_step_cancels_task_and_remount_has_new_origin(self):
        self.run_lua('''
assert(ACTIONS.MOUNT.fn({doer=p,target=t}));p.sg:GoToState('mounted_idle')
local old=t._drivetask
p.Transform:SetPosition(1,0,0) -- 尚未到下一次采样就下车，也要收费。
assert(ACTIONS.DISMOUNT.fn({doer=p,target=p}))
assert(t._fuel:value()==399.75 and not old.cancelled and t._drivetask==old)
p.components.rider:ActualDismount()
assert(t._fuel:value()==399.75 and old.cancelled and t._drivetask==nil)
p.Transform:SetPosition(100,0,100)
assert(ACTIONS.MOUNT.fn({doer=p,target=t}))
local fresh=t._drivetask;fresh.fn(t)
assert(fresh~=old and t._fuel:value()==399.75)
local x,y,z=p.Transform:GetWorldPosition() -- 原版上车会移到车体所在位置。
assert(t._last_drive_x==x and t._last_drive_z==z)
p.Transform:SetPosition(x+4,y,z);fresh.fn(t);assert(t._fuel:value()==398.75)
''')

    def test_teleport_resets_origin_without_billing_entire_jump(self):
        self.run_lua('''
assert(ACTIONS.MOUNT.fn({doer=p,target=t}))
p.Transform:SetPosition(1000,0,1000);t._drivetask.fn(t)
assert(t._fuel:value()==400)
p.Transform:SetPosition(1000,0,1004);t._drivetask.fn(t)
assert(t._fuel:value()==399)
''')

    def test_delete_and_death_cancel_travel_without_leaking_into_next_driver(self):
        self.run_lua('''
assert(ACTIONS.MOUNT.fn({doer=p,target=t}));local task=t._drivetask
p.Transform:SetPosition(2,0,0);t:Remove()
assert(task.cancelled and t._drivetask==nil and t._fuel:value()==399.5)
assert(not p.components.rider:IsRiding())
t=make_tractor();assert(ACTIONS.MOUNT.fn({doer=p,target=t}))
task=t._drivetask;p:PushEvent('death')
p.components.rider:ActualDismount()
assert(task.cancelled and t._drivetask==nil)
local other=make_player();assert(ACTIONS.MOUNT.fn({doer=other,target=t}))
other.Transform:SetPosition(4,0,0);t._drivetask.fn(t)
assert(t._rider==other and t._fuel:value()==399)
''')

    def test_interrupted_dismount_cannot_disable_driving_cost(self):
        self.run_lua('''
assert(ACTIONS.MOUNT.fn({doer=p,target=t}));p.sg:GoToState('mounted_idle')
local task=t._drivetask
assert(ACTIONS.DISMOUNT.fn({doer=p,target=p}))
-- 未执行ActualDismount就恢复驾驶，计费任务必须仍在。
p.sg:GoToState('mounted_idle');p.Transform:SetPosition(4,0,0);task.fn(t)
assert(t._drivetask==task and not task.cancelled and t._fuel:value()==399)
p.components.rider:ActualDismount();assert(task.cancelled)
''')

    def test_save_retains_fractional_fuel_and_load_does_not_start_driving_task(self):
        self.run_lua('''
assert(ACTIONS.MOUNT.fn({doer=p,target=t}))
p.Transform:SetPosition(1,0,0);t._drivetask.fn(t)
local record=t:GetSaveRecord();assert(record.data.fuel==399.75)
local restored=make_tractor();restored:OnLoad(record.data)
assert(restored._fuel:value()==399.75 and restored._drivetask==nil and not restored._working)
restored:SetFuel(0);assert(restored.components.locomotor.runspeed==0)
''')


if __name__ == '__main__':
    unittest.main()
