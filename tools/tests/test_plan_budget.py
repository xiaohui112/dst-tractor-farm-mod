"""设置到实际分帧调度贯通：额度、后台接管、世界共享及恢复上限。"""
from pathlib import Path
import unittest
from lupa.lua51 import LuaRuntime
import test_plan_timing as timing

MOD = Path(__file__).resolve().parents[2] / 'mod/Tractor'


class PlanBudgetTests(unittest.TestCase):
    def setUp(self):
        fixture = timing.PlanTimingTests()
        fixture.setUp()
        self.lua = fixture.lua

    def test_menu_values_and_localization(self):
        for locale in ('zh', 'en'):
            lua = LuaRuntime()
            lua.globals().locale = locale
            lua.execute((MOD / 'modinfo.lua').read_text())
            option = next(o for o in lua.globals().configuration_options.values()
                          if o.name == 'PLAN_CPU_BUDGET_MS')
            self.assertEqual(option.default, 16)
            self.assertEqual([o.data for o in option.options.values()],
                             [2, 4, 8, 12, 16, 24, 32])
            self.assertIn('规划' if locale == 'zh' else 'planning', option.label)
            self.assertIn('卡顿' if locale == 'zh' else 'stutter', option.hover)

    def test_missing_or_invalid_configuration_falls_back_to_sixteen_ms(self):
        self.lua.execute('''
local budget=require('aom_plan_budget')
for _,config in ipairs({false,'bad',{},
 {PLAN_CPU_BUDGET_MS=false},{PLAN_CPU_BUDGET_MS={}},
 {PLAN_CPU_BUDGET_MS='invalid'},{PLAN_CPU_BUDGET_MS=0},
 {PLAN_CPU_BUDGET_MS=-8},{PLAN_CPU_BUDGET_MS=1000},
 {PLAN_CPU_BUDGET_MS=8.5},{PLAN_CPU_BUDGET_MS=math.huge},
 {PLAN_CPU_BUDGET_MS=0/0}})do
 AOM_CONFIG=config;assert(budget.Milliseconds(false)==16)
 assert(budget.Milliseconds(true)==1)
end
AOM_CONFIG=nil;assert(budget.Milliseconds(false)==16)
AOM_CONFIG={PLAN_CPU_BUDGET_MS='12'};assert(budget.Milliseconds(false)==12)
''')

    def test_each_budget_advances_more_work_and_preserves_the_final_plan(self):
        ticks = []
        for budget in (2, 4, 8, 12, 16, 24, 32):
            with self.subTest(budget=budget):
                self.setUp()
                self.lua.globals().SELECTED_BUDGET = budget
                self.lua.execute('''
prepare();local baseline=D.Build(inst,0,0)
AOM_CONFIG={PLAN_CPU_BUDGET_MS=SELECTED_BUDGET}
local cpu,real=0,0
os.clock=function()return cpu end;os.time=function()return real end
before_task=function(delay)real=real+delay end
D.Build=function()
 for i=1,200 do cpu=cpu+.0005;real=real+.0005;coroutine.yield()end
 return baseline
end
D.Start(inst,0,0);run_planning()
local trace=inst._aom_plan_trace
assert(trace.context.tick_cpu_budget_ms==SELECTED_BUDGET)
assert(trace.max_tick_cpu>=SELECTED_BUDGET/1000-1e-9)
assert(trace.max_tick_cpu<=SELECTED_BUDGET/1000+.0005+1e-9)
assert(trace.cpu_budget_hits>0 and trace.resume_limit_hits==0)
assert(math.abs(trace.planning.cpu-.1)<1e-9)
assert(inst._block==baseline and inst._block.optimal and D.Validate(inst._block))
assert(crop_count()==0 and inst.components.aom_attachment_store:GetSeedCount()==16)
''')
                ticks.append(self.lua.globals().inst._aom_plan_trace.ticks)
        self.assertTrue(all(a > b for a, b in zip(ticks, ticks[1:])), ticks)

    def test_background_stays_at_one_ms_and_promotes_the_same_job(self):
        self.lua.execute('''
prepare();local baseline=D.Build(inst,0,0)
AOM_CONFIG={PLAN_CPU_BUDGET_MS=32}
local cpu=0;os.clock=function()return cpu end
D.Build=function()
 for i=1,100 do cpu=cpu+.0005;coroutine.yield()end
 return baseline
end
inst._working=false;D.Start(inst,0,0,true);table.remove(queue,1).fn()
local trace=inst._aom_plan_trace;local job=inst._aom_dynamic_job
assert(job and not inst._block and trace.context.tick_cpu_budget_ms==1)
assert(math.abs(trace.max_tick_cpu-.001)<1e-9)
inst._working=true;D.Start(inst,0,0)
assert(inst._aom_dynamic_job==job and trace.context.tick_cpu_budget_ms==32)
run_planning()
assert(inst._block==baseline and trace.max_tick_cpu>=.032-1e-9)
assert(crop_count()==0)
''')

    def test_two_vehicles_share_the_configured_world_budget(self):
        self.lua.execute('''
prepare();local baseline=D.Build(inst,0,0);local first=inst
AOM_CONFIG={PLAN_CPU_BUDGET_MS=12}
local cpu,tick,built=0,0,0
os.clock=function()return cpu end;GetTick=function()return tick end
D.Build=function()built=built+1;cpu=cpu+.0122;return baseline end
D.Start(first,0,0)
local second=make_inst({tomato=8,potato=8},'autumn')
second._attachment_type='seeder';second._working=true
second.DoTaskInTime=first.DoTaskInTime;D.Start(second,0,0)
local a=table.remove(queue,1);local b=table.remove(queue,1);a.fn();b.fn()
assert(built==1 and first._block and not second._block)
tick=1
for _,task in ipairs(queue)do if task.delay<1 then task.fn();break end end
assert(built==2 and second._block)
''')

    def test_high_budget_retains_the_resume_limit(self):
        self.lua.execute('''
prepare();local baseline=D.Build(inst,0,0)
AOM_CONFIG={PLAN_CPU_BUDGET_MS=32}
local cpu=0;os.clock=function()return cpu end
D.Build=function()
 for i=1,1100 do cpu=cpu+.000001;coroutine.yield()end
 return baseline
end
D.Start(inst,0,0);table.remove(queue,1).fn()
local trace=inst._aom_plan_trace
assert(trace.resumes==1024 and trace.resume_limit_hits==1)
assert(trace.cpu_budget_hits==0 and not inst._block)
run_planning();assert(inst._block==baseline and trace.ticks==2)
''')
