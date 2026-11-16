"""规划计时：CPU口径、连续计算、阶段不重叠、独立日志、取消与首种。"""
import unittest
from test_giant_farming import World


class PlanTimingTests(unittest.TestCase):
    def setUp(self):
        self.w=World();self.lua=self.w.lua
        self.lua.execute('''
logs={};print=function()error('planning records must not go to the master log')end
package.preload['aom_plan_log']=function()return {
 Append=function(line)logs[#logs+1]=line;return true end,
 Path=function()return 'test-planning.log'end,
}end
Timing=require('aom_plan_timing');D=require('aom_dynamic_farm')
function field()
 for x=-1,1 do for z=-1,1 do SpawnPrefab('farm_soil').Transform:SetPosition(x*4/3,0,z*4/3)end end
end
function prepare()
 field();inst=make_inst({tomato=8,potato=8},'autumn')
 inst._attachment_type='seeder';inst._working=true
 queue={};inst.DoTaskInTime=function(_,delay,fn)queue[#queue+1]={delay=delay,fn=fn}end
end
function run_planning()
 local n=0
 while not inst._block and #queue>0 do
  n=n+1;assert(n<20000)
  local task=table.remove(queue,1)
  if before_task then before_task(task.delay)end
  assert(not contains('[STEP]') and not contains('[SUMMARY]')) -- 搜索中只有START/每秒PROGRESS。
  task.fn()
 end
 return n
end
function step(trace,id)
 for _,row in ipairs(trace.steps)do if row.id==id then return row end end
end
function contains(text)
 for _,line in ipairs(logs)do if string.find(line,text,1,true)then return true end end
 return false
end
''')

    def test_cpu_excludes_other_frame_work_and_step_wall_times_add_up(self):
        self.lua.execute('''
local cpu,real,game=0,0,0
os.clock=function()return cpu end;os.time=function()return real end;GetTime=function()return game end
local function advance(w,c,g)real=real+w;cpu=cpu+c;game=game+(g or 0)end
local vehicle={GUID=42};Timing.Request(vehicle);advance(.1,.05,.1)
local trace=Timing.New(vehicle,0,0);advance(.033,.03,.033)
trace:TickBegin();trace:Stage('field_scan');trace:ResumeBegin()
advance(.004,.002);trace:Stage('patterns');advance(.002,.001)
trace:ResumeEnd();trace:TickEnd('cpu_budget')
advance(1,.6,1)
trace:TickBegin();trace:ResumeBegin();advance(.006,.003)
trace:Stage('arrangement');advance(.004,.002);trace:ResumeEnd()
trace:Stage('final_validation');advance(.002,.001)
trace:Stage('plan_commit');advance(.002,.001);trace:TickEnd('complete')
assert(not contains('[STEP]') and not contains('[SUMMARY]'))
trace:Complete('complete',nil,{total=8,upper=8,optimal=true})
assert(math.abs(trace.planning.cpu-.01)<1e-9)
assert(math.abs(trace.planning.process_cpu-.64)<1e-9)
assert(math.abs(trace.planning.wall-1.053)<1e-9)
local patterns=step(trace,'patterns')
assert(math.abs(patterns.wall-1.008)<1e-9 and math.abs(patterns.cpu-.004)<1e-9)
assert(math.abs(patterns.wait-1)<1e-9)
local wall,active,waiting=0,0,0
for _,row in ipairs(trace.steps)do if row.id=="log_output" then break end;wall=wall+row.wall;active=active+row.cpu;waiting=waiting+row.wait end
assert(math.abs(wall-trace.planning.wall)<1e-9 and math.abs(active-trace.planning.cpu)<1e-9)
assert(math.abs(waiting-1.033)<1e-9)
assert(contains('name=最终原版条件复核') and contains('active_cpu_ms=10.000'))
assert(contains('process_cpu_span_ms=640.000') and contains('wall_clock=system_wall_seconds'))
trace:Stage('preview_wait');advance(2,.3,2)
trace:RunBegin();trace:Stage('sow_dispatch');advance(.001,.0005)
trace:Stage('pre_sow_check');advance(.002,.001)
trace:Stage('first_seed');advance(.003,.002);trace:FirstSeed({crop='potato',x=0,z=0});trace:RunEnd()
assert(contains('request_to_seed_wall_ms=3159.000') and contains('preview_requested_ms=2000'))
assert(math.abs(step(trace,'preview_wait').wall-2)<1e-9 and step(trace,'preview_wait').cpu==0)
assert(contains('name=首颗种子种植与进度提交'))
''')

    def test_real_async_planner_retains_same_layout_and_excludes_simulated_engine_cpu(self):
        self.lua.execute('''
prepare()
local baseline=D.Build(inst,0,0);assert(baseline)
package.loaded.aom_dynamic_farm=nil;D=require("aom_dynamic_farm")
local nativeclock=os.clock;local origin=nativeclock();local extra,real,game,dispatches=0,0,0,0
os.clock=function()return nativeclock()+extra end
os.time=function()return nativeclock()-origin+real end;GetTime=function()return game end
before_task=function(delay)extra=extra+.25;real=real+delay;game=game+delay;dispatches=dispatches+1 end
Timing.Request(inst);D.Start(inst,0,0);run_planning()
local trace=inst._aom_plan_trace;local plan=inst._block;assert(plan and plan.total==baseline.total)
for i,p in ipairs(plan.slots)do assert(p.crop==baseline.slots[i].crop and p.x==baseline.slots[i].x and p.z==baseline.slots[i].z)end
assert(trace.planning.process_cpu-trace.planning.cpu>=dispatches*.25-.002)
assert(plan.construction.timing_basis=='process_cpu_during_task_slices')
assert(plan.construction.quantity_seconds+plan.construction.arrangement_seconds<=trace.planning.cpu+.002)
for _,name in ipairs({'field_scan','inventory','crop_filter','patterns','geometry','upper_bound','initial_layout','arrangement','arrange_candidates','arrange_group_bank','arrange_search','arrange_finalize','plan_materialize','final_validation','plan_commit','plan_encode','net_publish','completion_message'})do assert(step(trace,name),name)end
assert(inst._block.optimal)
assert(contains('seed_stock=potato:8,tomato:8') and contains('stage=plan_commit'))
assert(crop_count()==0 and inst.components.aom_attachment_store:GetSeedCount()==16)
local preview=table.remove(queue,1);assert(preview.delay==2);before_task(preview.delay);preview.fn()
assert(trace.finished and trace.first_seed and contains('[FIRST_SEED]'))
assert(step(trace,'preview_wait').wall>=2 and inst._block.done>0)
''')

    def test_failure_logs_reason_without_success_or_first_seed(self):
        self.lua.execute('''
prepare();for _,v in ipairs(ENTITIES)do if v.prefab=='farm_soil'then v:Remove()end end
D.Start(inst,0,0)
while #queue>0 do table.remove(queue,1).fn()end
assert(contains('status=failed') and contains('reason=NEED_PLOW') and not contains('status=complete'))
assert(not contains('[FIRST_SEED]') and crop_count()==0)
''')

    def test_cancelled_pending_job_logs_once_and_old_callbacks_cannot_submit(self):
        self.lua.execute('''
prepare();D.Start(inst,0,0);local trace=inst._aom_plan_trace
D.Cancel(inst,'TEST_CANCEL');local count=#logs;D.Cancel(inst,'TEST_CANCEL')
while #queue>0 do table.remove(queue,1).fn()end
assert(#logs==count and trace.finished and not inst._block and crop_count()==0)
assert(contains('status=cancelled') and contains('reason=TEST_CANCEL'))
''')

    def test_cancel_during_preview_logs_separately_and_cannot_plant(self):
        self.lua.execute('''
prepare();D.Start(inst,0,0);run_planning()
local trace=inst._aom_plan_trace;D.Cancel(inst,'PREVIEW_CANCEL')
while #queue>0 do table.remove(queue,1).fn()end
assert(trace.finished and contains('[SOW_CANCELLED]') and not contains('[FIRST_SEED]'))
assert(step(trace,'preview_wait').status=='cancelled' and crop_count()==0)
''')

    def test_fallback_phases_are_measured_without_nested_double_counting(self):
        self.lua.execute('''
prepare()
for x=-1,1 do for z=-1,1 do SpawnPrefab('farm_soil').Transform:SetPosition(4+x*4/3,0,z*4/3)end end
inst=make_inst({carrot=5,corn=5,potato=5},'autumn');inst._attachment_type='seeder';inst._working=true
inst.DoTaskInTime=function(_,delay,fn)queue[#queue+1]={delay=delay,fn=fn}end
D.Start(inst,0,0);run_planning()
local trace=inst._aom_plan_trace
assert(inst._block and inst._block.total==15 and inst._block.optimal)
assert(step(trace,'quantity_portfolio').status=='done' and contains('[METHOD]'))
local cpu=0;for _,row in ipairs(trace.steps)do if row.id=="log_output" then break end;cpu=cpu+(row.cpu or 0)end
assert(math.abs(cpu-trace.planning.cpu)<.001)
''')

    def test_live_process_clock_timings_remain_unchanged_for_web_and_sync_builds(self):
        self.lua.execute('''
prepare();local plan=D.Build(inst,0,0)
assert(plan and plan.total==8 and plan.construction.timing_basis=='process_cpu')
assert(require('aom_seed_packing').Timings().basis=='process_cpu' and not contains('[STEP]'))
''')

    def test_slice_budget_yields_without_losing_search_progress(self):
        for long_resume in (False, True):
            with self.subTest(long_resume=long_resume):
                self.setUp()
                self.lua.globals().LONG_RESUME=long_resume
                self.lua.execute('''
prepare();local plan=D.Build(inst,0,0)
local cpu,real=0,0
os.clock=function()return cpu end;os.time=function()return real end
before_task=function(delay)real=real+delay end
D.Build=function(_,x,z,trace)
 trace:Stage('field_scan')
 for i=1,(LONG_RESUME and 1 or 260)do
  local dt=LONG_RESUME and .01 or .000001;cpu=cpu+dt;real=real+dt
  coroutine.yield()
 end
 return plan
end
D.Start(inst,0,0);run_planning();local trace=inst._aom_plan_trace
if LONG_RESUME then
 assert(trace.cpu_budget_hits==1 and trace.resume_limit_hits==0 and trace.long_resumes==1)
 assert(math.abs(trace.max_resume_cpu-.01)<1e-9 and trace.ticks==2)
else
 assert(trace.resume_limit_hits==0 and trace.cpu_budget_hits==0 and trace.resumes==261)
 assert(trace.ticks==1 and #queue==1 and queue[1].delay==2)
end
''')

    def test_moving_away_during_preview_records_travel_wait_before_first_seed(self):
        self.lua.execute('''
prepare();local real=0;os.time=function()return real end
D.Start(inst,0,0);run_planning();local trace=inst._aom_plan_trace
inst.x=4;real=2;table.remove(queue,1).fn()
assert(not trace.finished and trace.current.id=='await_sow_tile' and not contains('[FIRST_SEED]'))
real=7;inst.x=0;Drive.WorkTile(inst,0,0)
assert(trace.finished and contains('[FIRST_SEED]'))
local waiting=step(trace,'await_sow_tile');assert(math.abs(waiting.wall-5)<1e-9 and waiting.cpu<.005)
''')

    def test_log_output_cost_is_post_planning_and_not_counted_as_solver_cpu(self):
        self.lua.execute('''
local cpu,real=0,0;os.clock=function()return cpu end;os.time=function()return real end
local trace=Timing.New({GUID=42},0,0)
require('aom_plan_log').Append=function(line)logs[#logs+1]=line;cpu=cpu+.0005;real=real+.001;return true end
trace:TickBegin();trace:Stage('field_scan');trace:ResumeBegin()
cpu=.01;real=.01;trace:ResumeEnd();trace:TickEnd('complete')
trace:Complete('complete',nil,{total=8,upper=8,optimal=true})
local count=1;assert(math.abs(trace.planning.cpu-.01)<1e-9)
trace:Stage('preview_wait');local output=step(trace,'log_output')
assert(math.abs(output.cpu-count*.0005)<1e-9 and math.abs(output.wall-count*.001)<1e-9)
''')
