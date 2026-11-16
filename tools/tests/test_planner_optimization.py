"""Planning lifecycle, cache validity, spatial indexing and crash-replay telemetry."""
import unittest
import test_plan_timing

class PlannerOptimizationTests(unittest.TestCase):
 def setUp(self):
  fixture=test_plan_timing.PlanTimingTests();fixture.setUp();self.lua=fixture.lua

 def test_cached_layout_uses_exact_inventory_and_rechecks_input(self):
  self.lua.execute('''
prepare();local first=D.Build(inst,0,0);assert(first.total==8)
local second=D.Build(inst,0,0);assert(second.construction.cache_hit and D.Validate(second))
inst=make_inst({tomato=9,potato=9},'autumn')
local third=D.Build(inst,0,0);assert(third and third.total==8 and not third.construction.cache_hit)
''')

 def test_cache_survives_start_tile_change_without_moving_crops(self):
  self.lua.execute('''
prepare();for x=-1,1 do for z=-1,1 do SpawnPrefab('farm_soil').Transform:SetPosition(4+x*4/3,0,z*4/3)end end
local first=D.Build(inst,0,0);local second=D.Build(inst,4,0)
assert(second.construction.cache_hit and second.total==first.total and D.Validate(second))
local points={};for _,p in ipairs(first.slots)do points[p.x..':'..p.z]=p.crop end
for _,p in ipairs(second.slots)do assert(points[p.x..':'..p.z]==p.crop)end
''')

 def test_pause_resume_preserves_stack_and_changes_invalidate_it(self):
  self.lua.execute('''
prepare();local plan=D.Build(inst,0,0);local built=0;local cpu=0
os.clock=function()return cpu end
D.Build=function(_,x,z,trace)
 built=built+1
 for i=1,5 do cpu=cpu+.005;coroutine.yield()end
 return plan
end
D.Start(inst,0,0);table.remove(queue,1).fn();local job=inst._aom_dynamic_job
D.Cancel(inst,'WORK_STOPPED');assert(inst._aom_suspended_job==job)
D.Start(inst,0,0);assert(inst._aom_dynamic_job==job)
run_planning();assert(built==1 and inst._block.total==8 and contains('[RESUMED]'))
''')

 def test_background_job_never_plants_and_f_promotes_same_job(self):
  self.lua.execute('''
prepare();local plan=D.Build(inst,0,0);local cpu=0;os.clock=function()return cpu end
D.Build=function(_,x,z,trace)for i=1,3 do cpu=cpu+.002;coroutine.yield()end;return plan end
inst._working=false;D.Start(inst,0,0,true);table.remove(queue,1).fn()
local job=inst._aom_dynamic_job;assert(job and not inst._block and crop_count()==0)
inst._working=true;D.Start(inst,0,0);assert(inst._aom_dynamic_job==job and not inst._aom_background)
run_planning();assert(inst._block and crop_count()==0)
''')

 def test_background_completion_only_populates_cache(self):
  self.lua.execute('''
prepare();inst._working=false;D.Start(inst,0,0,true)
local n=0;while #queue>0 do n=n+1;assert(n<1000);table.remove(queue,1).fn()end
assert(not inst._block and crop_count()==0 and inst._aom_prepared_key)
local plan=D.Build(inst,0,0);assert(plan.construction.cache_hit)
''')

 def test_stable_nearby_input_prepares_without_spending_seeds(self):
  self.lua.execute('''
prepare();inst._working=false;inst._rider=inst
local now=0;GetTimeRealSeconds=function()return now end
D.PrepareNearby(inst);assert(not inst._aom_dynamic_job)
now=1;D.PrepareNearby(inst);assert(not inst._aom_dynamic_job)
now=2;D.PrepareNearby(inst);assert(inst._aom_dynamic_job and inst._aom_background)
local n=0;while #queue>0 do n=n+1;assert(n<1000);table.remove(queue,1).fn()end
assert(not inst._block and crop_count()==0 and inst.components.aom_attachment_store:GetSeedCount()==16)
''')

 def test_changed_stock_replaces_suspended_job(self):
  self.lua.execute('''
prepare();local cpu=0;os.clock=function()return cpu end
D.Build=function()while true do cpu=cpu+.005;coroutine.yield()end end
D.Start(inst,0,0);table.remove(queue,1).fn();local old=inst._aom_dynamic_job
D.Cancel(inst,'WORK_STOPPED')
local replacement=make_inst({tomato=9,potato=9},'autumn')
inst.components.aom_attachment_store=replacement.components.aom_attachment_store
D.Start(inst,0,0)
assert(inst._aom_dynamic_job~=old and not inst._aom_suspended_job and contains('reason=REPLACED'))
''')

 def test_changed_field_is_rechecked_before_background_result_is_used(self):
  self.lua.execute('''
prepare();local plan=D.Build(inst,0,0);local cpu=0;os.clock=function()return cpu end
D.Build=function()cpu=cpu+.005;coroutine.yield();return plan end
inst._working=false;D.Start(inst,0,0,true);table.remove(queue,1).fn()
for _,v in ipairs(ENTITIES)do if v.prefab=='farm_soil'then v:Remove();break end end
while #queue>0 do table.remove(queue,1).fn()end
assert(not inst._block and not inst._aom_dynamic_job and crop_count()==0 and contains('reason=INPUT_CHANGED'))
''')

 def test_first_seed_wait_starts_at_f_when_background_job_is_promoted(self):
  self.lua.execute('''
prepare();local plan=D.Build(inst,0,0);local now,cpu=100,0
GetTimeRealSeconds=function()return now end;os.clock=function()return cpu end
D.Build=function()cpu=cpu+.005;coroutine.yield();return plan end
inst._working=false;D.Start(inst,0,0,true);table.remove(queue,1).fn()
now=110;Timing.Request(inst);inst._working=true;D.Start(inst,0,0)
run_planning();now=112;inst._aom_plan_trace:FirstSeed({crop='tomato',x=0,z=0})
assert(contains('request_to_seed_wall_ms=2000.000'))
''')

 def test_two_vehicles_share_one_frame_budget(self):
  self.lua.execute('''
prepare();local plan=D.Build(inst,0,0);local first=inst
local cpu,tick,built=0,0,0;os.clock=function()return cpu end;GetTick=function()return tick end
D.Build=function()built=built+1;cpu=cpu+.004;return plan end
D.Start(first,0,0)
local second=make_inst({tomato=8,potato=8},'autumn');second._attachment_type='seeder';second._working=true
second.DoTaskInTime=first.DoTaskInTime;D.Start(second,0,0)
local a=table.remove(queue,1);local b=table.remove(queue,1);a.fn();b.fn()
assert(built==1 and first._block and not second._block)
tick=1
for _,task in ipairs(queue)do if task.delay<1 then task.fn();break end end
assert(built==2 and second._block)
''')

 def test_input_is_written_before_completion_and_clock_is_high_resolution(self):
  self.lua.execute('''
prepare();local now=123.125;GetTimeRealSeconds=function()return now end
local trace=Timing.New(inst,0,0);trace:TickBegin();now=now+.004
trace:TickEnd('cpu_budget');trace:Complete('complete',nil,{total=8,upper=8,optimal=true})
assert(contains('wall_precision_ms=1') and contains('wall_ms=4.000'))
logs={};D.Start(inst,0,0);run_planning()
local input,summary,pits
for i,line in ipairs(logs)do if line:find('[INPUT]',1,true)and not input then input=i end;if line:find('[SUMMARY]',1,true)then summary=i end;if line:find('[PITS]',1,true)then pits=i end end
assert(input and pits and summary and input<summary and pits<summary and contains('[LAYOUT]'))
''')

 def test_spatial_buckets_match_exhaustive_distances_with_offset_pits(self):
  self.lua.execute('''
local A=require('aom_seed_layout');local slots,tiles={},{}
for x=-2,2 do for z=-2,2 do if x~=0 or z~=0 then
 tiles[#tiles+1]={x=x*4,z=z*4}
 for dx=-1,1 do for dz=-1,1 do slots[#slots+1]={x=x*4+dx*4/3+.03,z=z*4+dz*4/3-.02}end end
end end end
for _,p in ipairs(slots)do SpawnPrefab('farm_soil').Transform:SetPosition(p.x,0,p.z)end
local g=A.Geometry(tiles,slots,DEFS)
for i,p in ipairs(slots)do
 local expected={};for j,q in ipairs(slots)do local d=(p.x-q.x)^2+(p.z-q.z)^2;if d<=16 then expected[#expected+1]=j end end
 assert(#expected==#g.near[i]);for n,j in ipairs(expected)do assert(g.near[i][n].j==j)end
end
''')

if __name__=='__main__':unittest.main()
