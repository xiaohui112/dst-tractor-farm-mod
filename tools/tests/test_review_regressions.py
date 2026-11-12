"""0.5.1 二次复查：跨轮计划、提示、回调结算和状态快照。"""
import unittest
import test_work_cargo as cargo
from test_giant_farming import World, as_dict


class PlanReviewTests(unittest.TestCase):
    def test_completed_plan_cannot_relocate_change_ratio_or_rotation_implicitly(self):
        w=World();c=w.combo('autumn-01-02')
        inst=w.make({'tomato':4,'eggplant':4});w.bind(inst,c)
        inst._block.rotation=2
        inst._block.completed=w.lua.table_from({i:True for i,p in c.slots.items() if p.crop})
        inst._block.done=c.total
        before=w.block.OnSave(inst)
        inst.x=40
        self.assertEqual(w.drive.WorkHere(inst,40,0),(False,'COMPLETE',False))
        after=w.block.OnSave(inst)
        for key in ('combo_id','x','z','rotation','confirmed'):
            self.assertEqual(after[key],before[key])
        self.assertEqual(inst._block.done,c.total)
        # 保存/加载仍保留已完成计划，不能偷偷承认当前坐标的新方案。
        w.block.OnLoad(inst,after)
        self.assertEqual(w.drive.WorkHere(inst,40,0),(False,'COMPLETE',False))
        self.assertTrue(w.block.Preview(inst))
        self.assertEqual(inst._block.x,40)
        self.assertNotEqual(inst._block.combo_id,c.id)
        self.assertFalse(inst._block.confirmed)
        self.assertEqual(w.drive.WorkHere(inst,40,0),(False,'PLAN_PENDING',False))
        self.assertTrue(w.block.Confirm(inst))
        self.assertTrue(w.drive.WorkHere(inst,40,0)[0])

    def test_unconfirmed_or_missing_confirmation_never_becomes_confirmed_through_save(self):
        w=World();c=w.combo('autumn-01-02');inst=w.make(as_dict(c.ratio))
        self.assertEqual(w.drive.WorkHere(inst),(False,'PLAN_PENDING',False))
        self.assertIsNone(inst._block)
        self.assertTrue(w.block.Preview(inst))
        inst._block.confirmed=None
        saved=w.block.OnSave(inst)
        self.assertFalse(saved.confirmed)
        saved.confirmed=None
        w.block.OnLoad(inst,saved)
        self.assertFalse(inst._block.confirmed)
        self.assertEqual(w.drive.WorkHere(inst),(False,'PLAN_PENDING',False))

    def test_next_tile_is_advisory_for_plough_and_seeder_and_reentry_works(self):
        for kind in ('plow','seeder'):
            with self.subTest(kind=kind):
                w=World();c=w.combo('autumn-10-02');inst=w.make(as_dict(c.ratio));w.bind(inst,c)
                if kind=='seeder':w.prepare(inst)
                inst._attachment_type=kind;inst._working=True
                fuel=inst._fuel.value(inst._fuel)
                tool=inst.components.container.GetItemInSlot(inst.components.container,1)
                uses=tool.components.finiteuses.GetUses(tool.components.finiteuses)
                self.assertEqual(w.drive.WorkTile(inst,40,0),(False,'NEXT_TILE'))
                self.assertTrue(inst._working)
                self.assertEqual(inst._fuel.value(inst._fuel),fuel)
                self.assertEqual(tool.components.finiteuses.GetUses(tool.components.finiteuses),uses)
                x,z=w.block.NextTile(inst)
                self.assertTrue(w.drive.WorkTile(inst,x,z))
                self.assertTrue(inst._working)

    def test_preview_distinguishes_invalid_template_insufficient_seeds_and_blocked_field(self):
        w=World();inst=w.make({'tomato':4,'potato':4})
        w.lua.globals().TUNING.FARM_TILL_SPACING=1.5
        self.assertEqual(w.block.Preview(inst),(False,'MOUNDS_TOO_CLOSE'))
        self.assertIsNone(inst._block)
        w.lua.globals().TUNING.FARM_TILL_SPACING=1.25
        w.lua.execute('TheWorld.Map.IsPassableAtPoint=function()return false end')
        self.assertEqual(w.block.Preview(inst),(False,'INVALID_LAND'))
        other=w.make({'tomato':3,'potato':4})
        self.assertEqual(w.block.Preview(other),(False,'MISSING_SEEDS'))

    def test_failed_rotation_keeps_previous_preview_and_reports_template_error(self):
        w=World();inst=w.make({'tomato':4,'potato':4})
        self.assertTrue(w.block.Preview(inst));rotation=inst._block.rotation
        w.lua.globals().TUNING.FARM_TILL_SPACING=1.5
        self.assertEqual(w.block.Preview(inst,True),(False,'MOUNDS_TOO_CLOSE'))
        self.assertEqual(inst._block.rotation,rotation)
        self.assertFalse(inst._block.confirmed)
        self.assertEqual(w.block.Confirm(inst),(False,'MOUNDS_TOO_CLOSE'))


class SettlementReviewTests(unittest.TestCase):
    def setUp(self):
        engine=cargo.WorkCargoTests();engine.setUp();self.lua=engine.lua
        self.lua.execute("print=function()end")

    def check_failure(self,inject):
        self.lua.execute('''
local plant=crop('tomato',0,0,false)
t:SetWorking(true)
''' + inject + '''
local fuel=t._fuel:value();local chassis=t.components.finiteuses:GetUses()
local item=t:GetAttachment();local tool=item.components.finiteuses:GetUses()
local ok,changed,reason=pcall(Drive.WorkTile,t,0,0)
assert(ok and changed and reason=='WORK_ERROR' and not t._working)
assert(not t._worktask and not t._aom_work_result and not t:HasTag('NOBLOCK'))
assert(item._aom_work_vehicle==nil)
assert(t._fuel:value()==fuel-1 and t.components.finiteuses:GetUses()==chassis-1)
assert(item.components.finiteuses:GetUses()==tool-1)
assert(quantity(t,'tomato')==1 and t._workstate_net:value()=='WORK_ERROR')
local used_fuel=t._fuel:value();t:SetWorking(true);Drive.WorkTile(t,0,0)
assert(t._fuel:value()==used_fuel and quantity(t,'tomato')==1)
''')

    def test_success_fx_error_cannot_skip_settlement_or_escape_sampling(self):
        self.check_failure("require('aom_attachment_animation').Success=function()error('injected FX failure')end")

    def test_chassis_callback_error_does_not_skip_attachment_or_fuel_debit(self):
        self.check_failure('''
local uses=t.components.finiteuses;local use=uses.Use
uses.Use=function(self,n)use(self,n);error('chassis callback')end
''')

    def test_attachment_callback_error_restores_owner_and_debits_fuel_once(self):
        self.check_failure('''
local uses=t:GetAttachment().components.finiteuses;local use=uses.Use
uses.Use=function(self,n)use(self,n);error('attachment callback')end
''')

    def test_stop_animation_error_cannot_keep_work_task_running(self):
        self.check_failure('''
local anim=require('aom_attachment_animation')
anim.Success=function()error('success FX')end
local set=anim.SetWorking
anim.SetWorking=function(inst,on)if not on then error('stop animation')end;return set(inst,on)end
''')

    def test_chassis_and_attachment_callbacks_can_both_fail_without_skipping_debits(self):
        self.check_failure('''
for _,uses in ipairs({t.components.finiteuses,t:GetAttachment().components.finiteuses})do
 local native=uses.Use;uses.Use=function(self,n)native(self,n);error('after debit')end
end
''')


class StatusSnapshotTests(unittest.TestCase):
    def test_each_network_update_is_one_complete_code_and_detail_snapshot(self):
        engine=cargo.WorkCargoTests();engine.setUp()
        engine.lua.execute('''
local Status=require('aom_work_status');local AOM=require('aom_common')
local messages={};local native=t._workstate_net.set
local client={_workstate_net=t._workstate_net}
t._workstate_net.set=function(self,value)
 native(self,value)
 local code,detail=Status.Read(client)
 messages[#messages+1]={code,detail,Status.Describe(client)}
end
Status.Set(t,'EMPTY','irrigator');Status.Set(t,'FERTILIZER_MISSING','13')
Status.Set(t,'CARGO_FULL');Status.Set(t,nil)
assert(#messages==4)
assert(messages[1][1]=='EMPTY' and messages[1][2]=='irrigator')
assert(messages[2][1]=='FERTILIZER_MISSING' and messages[2][2]=='13')
assert(messages[3][1]=='CARGO_FULL' and messages[3][2]=='')
assert(messages[4][1]=='' and messages[4][2]=='' and messages[4][3]=='')
Status.Set(t,'EMPTY','irrigator');AOM.SetLanguage('en')
assert(string.find(Status.Describe(client),'Tank empty',1,true))
AOM.SetLanguage('zh');assert(string.find(Status.Describe(client),'水箱已空',1,true))
for _,payload in ipairs({'|irrigator','invalid|13'})do
 t._workstate_net:set(payload);assert(Status.Describe(client)=='')
end
''')


if __name__=='__main__':unittest.main()
