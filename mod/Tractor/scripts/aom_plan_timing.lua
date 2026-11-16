-- 仅在游戏的异步规划入口启用。分阶段记录先缓存在内存，完成/取消时集中输出。
-- os.clock是进程CPU；只累计本任务执行区间，排除跨帧间隔，但仍可能包含并行引擎线程CPU。
local M={}
local Log=require("aom_plan_log")
local L=require("aom_locale").Text
local serial=0
local LABELS={
 template_prepare="模版准备",template_select="模版选配与局部回填",template_finalize="模版最终校验与评分",template_witness="模版合法下界",
 region_probe="大田区域构造先行探测",
 quantity_portfolio="完整证明与辅助构造交替推进",region_witness="多配比连续区域构造",cache_hit="复用已校验完整方案",
 work_dispatch="开工至规划入口等待",initial_dispatch="首次调度等待",field_scan="连通农田与真实坑位扫描",inventory="货仓种子统计",
 crop_filter="原版定义与应季种子筛选",patterns="逐地皮互补配比枚举",geometry="坑距/同族几何关系",
 upper_bound="合法数量上界",initial_layout="初始合法布局",quota_prepare="目标配额准备",
 fast_witness="快速上界见证",block_witness="互补库存分块见证",subset_witness="紧凑地皮子集见证",
 exact_probe="有界精确探测",heuristic_warm="后备可行下界搜索",exact_proof="完整最大数量证明",
 arrangement="排列初始评分",arrange_candidates="排列候选库枚举",arrange_group_bank="同组成候选合并",
 arrange_search="同族紧凑与整齐搜索",arrange_finalize="排列最终评分",plan_materialize="生成实际坑位计划",final_validation="最终原版条件复核",
 plan_commit="提交服务器计划",plan_encode="预览数据编码",net_publish="网络变量提交",completion_message="规划完成消息",
 log_output="完成日志输出（规划完成后）",preview_wait="预览定时等待",sow_dispatch="开播调度与物料初检",await_sow_tile="等待驾驶到待播地皮",pre_sow_check="开播前现场/库存复核",first_seed="首颗种子种植与进度提交",
}
-- 原版 mainfunctions.GetTimeRealSeconds 将 TheSim:GetRealTime 毫秒转换为秒。
local function Real()return GetTimeRealSeconds and GetTimeRealSeconds()or os.time()end
local function Precision()return GetTimeRealSeconds and 1 or 1000 end
local function Game()return GetTime and GetTime() or 0 end
local function Clean(v)return tostring(v):gsub('[%z\001-\031\127]',' ')end
local function Fields(values)
 local keys={};for k in pairs(values or {})do keys[#keys+1]=k end;table.sort(keys)
 local out={};for _,k in ipairs(keys)do out[#out+1]=k..'='..Clean(values[k])end
 return table.concat(out,' ')
end
local Trace={};Trace.__index=Trace
function Trace:Snapshot()
 local real,cpu=Real(),os.clock()
 return {wall=real-self.started_wall,game=Game()-self.started_game,
  cpu=self.cpu+(self.running_cpu and cpu-self.running_cpu or 0),
  active_wall=self.active_wall+(self.running_wall and real-self.running_wall or 0),process_cpu=cpu-self.started_cpu}
end
function Trace:Clock()return self.cpu+(self.running_cpu and os.clock()-self.running_cpu or 0)end
function Trace:RunBegin()
 if self.finished or self.running_cpu then return end
 self.running_cpu=os.clock();self.running_wall=Real()
end
function Trace:RunEnd()
 if not self.running_cpu then return end
 self.cpu=self.cpu+os.clock()-self.running_cpu;self.active_wall=self.active_wall+Real()-self.running_wall
 self.running_cpu=nil;self.running_wall=nil
end
function Trace:CloseStep(status,reason,snapshot)
 local row=self.current;if not row then return end
 local now=snapshot or self:Snapshot();local start=row.start
 row.wall=math.max(0,now.wall-start.wall);row.cpu=math.max(0,now.cpu-start.cpu)
 row.active_wall=math.max(0,now.active_wall-start.active_wall)
 row.wait=math.max(0,row.wall-row.active_wall);row.game=math.max(0,now.game-start.game)
 row.process_cpu=math.max(0,now.process_cpu-(start.process_cpu or 0))
 row.status=status or 'done';row.reason=reason;row.start=nil;self.current=nil
end
function Trace:Stage(id)
 if self.finished then return end
 local snapshot=self:Snapshot();self:CloseStep(nil,nil,snapshot)
 local row={id=id,start=snapshot,resumes=self.in_resume and 1 or 0,ticks=self.in_tick and 1 or 0}
 self.steps[#self.steps+1]=row;self.current=row
 self:Emit('STAGE_BEGIN',{stage=id})
end
function Trace:Skip(id,reason)
 if self.finished then return end
 self.steps[#self.steps+1]={id=id,wall=0,cpu=0,active_wall=0,wait=0,game=0,resumes=0,ticks=0,process_cpu=0,status='skipped',reason=reason}
end
function Trace:Context(values)for k,v in pairs(values)do self.context[k]=v end end
function Trace:TickBegin()
 if self.finished then return end
 self.ticks=self.ticks+1;self.in_tick=true
 if self.last_tick_end then self.max_gap=math.max(self.max_gap,Real()-self.last_tick_end)end
 self:RunBegin();self.tick_cpu=self.running_cpu
 if self.current then self.current.ticks=self.current.ticks+1 end
end
function Trace:ResumeBegin(cpu)
 self.resumes=self.resumes+1;self.in_resume=true
 if self.current then self.current.resumes=self.current.resumes+1 end
 self.resume_cpu=cpu or os.clock()
end
function Trace:ResumeEnd(cpu)
 local elapsed=(cpu or os.clock())-self.resume_cpu
 self.max_resume_cpu=math.max(self.max_resume_cpu,elapsed)
 if elapsed>.004 then self.long_resumes=self.long_resumes+1 end
 self.in_resume=false
end
function Trace:TickEnd(reason)
 if not self.in_tick then return end
 local slice=os.clock()-self.tick_cpu
 self.max_tick_cpu=math.max(self.max_tick_cpu,slice)
 local bucket=slice<=.001 and 1 or slice<=.004 and 2 or slice<=.008 and 3 or slice<=.016 and 4 or 5
 self.slice_bins[bucket]=self.slice_bins[bucket]+1
 if reason=='cpu_budget' then
  self.cpu_budget_hits=self.cpu_budget_hits+1
  if self.current then self.current.cpu_budget_hits=(self.current.cpu_budget_hits or 0)+1 end
 end
 if reason=='resume_limit' then
  self.resume_limit_hits=self.resume_limit_hits+1
  if self.current then self.current.resume_limit_hits=(self.current.resume_limit_hits or 0)+1 end
 end
 self:RunEnd();self.in_tick=false;self.last_tick_end=Real()
 if reason~='complete' and reason~='failed' then self:Progress()end
end
function Trace:Elapsed()
 return math.max(0,math.floor(Real()-self.started_wall))
end
function Trace:Text()
 return L("巨大化规划：已用时%d秒",self:Elapsed())
end
function Trace:Say(text,duration)
 if self.quiet then return end
 if self.log_error then text=text..L("（规划日志写入失败）")end
 require('aom_feedback').Say(self.vehicle and self.vehicle._rider,text,duration or 3,true)
end
function Trace:Emit(kind,values)
 local fields={};for k,v in pairs(values or {})do fields[k]=v end
 fields.logged_at=os.date('%Y-%m-%dT%H:%M:%S%z')
 fields.elapsed_s=fields.elapsed_s or fields.planning_elapsed_seconds or self:Elapsed()
 local line='[Tractor][GiantPlan]['..self.id..']['..kind..'] '..Fields(fields)
 if self.batch then self.batch[#self.batch+1]=line;return end
 local ok,err=Log.Append(line);self.log_error=not ok and (err or 'write_failed') or nil
end
function Trace:Flush()
 local lines=self.batch;self.batch=nil
 if lines and #lines>0 then
  local ok,err=Log.Append(table.concat(lines,'\n'))
  self.log_error=not ok and (err or 'write_failed') or nil
 end
end
function Trace:Progress(force)
 if self.finished or self.planning then return end
 local elapsed=self:Elapsed()
 if not force and self.last_progress and elapsed-self.last_progress<2 then return end
 self.last_progress=elapsed
 self:Emit('PROGRESS',{stage=self.current and self.current.id or 'initial_dispatch',elapsed_s=elapsed,
  active_cpu_ms=string.format('%.3f',self:Clock()*1000),ticks=self.ticks,resumes=self.resumes,
  method=self.context.active_method or '-',target=self.context.target or '-',best_legal=self.context.best_legal or 0,proof_upper=self.context.proof_upper or '-',
  nodes=self.context.proof_nodes or 0})
 local text=self:Text();self:Say(text,3)
 if not self.quiet and self.vehicle and self.vehicle._planprogress_net then self.vehicle._planprogress_net:set(text)end
end
function Trace:DumpSteps()
 for i=self.printed+1,#self.steps do
  local row=self.steps[i]
  self:Emit('STEP',{seq=i,stage=row.id,name=LABELS[row.id] or row.id,status=row.status,reason=row.reason or '-',
   wall_ms=string.format('%.3f',row.wall*1000),active_cpu_ms=string.format('%.3f',row.cpu*1000),
   active_wall_ms=string.format('%.3f',row.active_wall*1000),wait_ms=string.format('%.3f',row.wait*1000),
   game_ms=string.format('%.3f',row.game*1000),process_cpu_span_ms=string.format('%.3f',(row.process_cpu or 0)*1000),
   ticks=row.ticks,resumes=row.resumes,cpu_budget_hits=row.cpu_budget_hits or 0,resume_limit_hits=row.resume_limit_hits or 0})
 end
 self.printed=#self.steps
end
function Trace:Complete(status,reason,plan)
 if self.finished then return end
 self:RunEnd();local s=self:Snapshot();self:CloseStep(status=='complete' and 'done' or status,reason,s)
 self.planning=s;self.status=status
 self.completed_seconds=math.max(0,math.floor(s.wall))
 if status=='complete' then
  self.completed_text=L('巨大化规划完成：用时%d秒，开始播种',self.completed_seconds)
  self:Say(self.completed_text,4)
  if not self.quiet and self.vehicle and self.vehicle._planprogress_net then self.vehicle._planprogress_net:set(self.completed_text)end
 elseif status=='cancelled' then
  self:Say(L('巨大化规划已取消：用时%d秒',self.completed_seconds),3)
 else self:Say(L('巨大化规划未完成：用时%d秒',self.completed_seconds),3)end
 self.awaiting_first=status=='complete' and plan~=nil
 self.finished=not self.awaiting_first
 local log_cpu,log_wall=os.clock(),Real();self.batch={}
 if plan then
  local points={};for _,p in ipairs(plan.slots or {})do points[#points+1]=string.format('%.17g,%.17g,%s',p.x,p.z,p.crop or '_')end
  self:Emit('LAYOUT',{format='x,z,crop;...',points=table.concat(points,';')})
 end
 self:Emit('INPUT',self.context)
 self:DumpSteps()
 self:Emit('SUMMARY',{status=status,reason=reason or '-',total=plan and plan.total or 0,
  upper=plan and plan.upper or 0,optimal=plan and plan.optimal or false,
  wall_ms=string.format('%.3f',s.wall*1000),active_cpu_ms=string.format('%.3f',s.cpu*1000),
  active_wall_ms=string.format('%.3f',s.active_wall*1000),wait_ms=string.format('%.3f',math.max(0,s.wall-s.active_wall)*1000),
  game_ms=string.format('%.3f',s.game*1000),process_cpu_span_ms=string.format('%.3f',s.process_cpu*1000),
  ticks=self.ticks,resumes=self.resumes,cpu_budget_hits=self.cpu_budget_hits,resume_limit_hits=self.resume_limit_hits,
  slice_bins_ms='1,4,8,16,over16:'..table.concat(self.slice_bins,','),
  max_tick_cpu_ms=string.format('%.3f',self.max_tick_cpu*1000),max_resume_cpu_ms=string.format('%.3f',self.max_resume_cpu*1000),
  resumes_over_4ms=self.long_resumes,max_dispatch_gap_ms=string.format('%.3f',self.max_gap*1000),
  planning_elapsed_seconds=self.completed_seconds,wall_precision_ms=Precision(),log_file=Log.Path() or 'not_configured',
  wall_clock=self.wall_basis,cpu_basis='process_cpu_during_task_slices',lua=_VERSION,
  note='阶段耗时不嵌套;阶段ticks/resumes可能重叠;同步提交不等于客户端接收;CPU可能含并行引擎线程'})
 self:Emit('END',{status=status,reason=reason or '-',planning_elapsed_seconds=self.completed_seconds,wall_precision_ms=Precision(),
  completed_at=os.date('%Y-%m-%dT%H:%M:%S%z',self.started_epoch+self.completed_seconds),
  end_epoch_seconds=self.started_epoch+self.completed_seconds})
 self:Flush()
 -- 输出开销单列到规划完成后，避免把日志写入成本算作求解成本。
 self.cpu=self.cpu+os.clock()-log_cpu;self.active_wall=self.active_wall+Real()-log_wall
 local row={id='log_output',start=s,resumes=0,ticks=0}
 self.steps[#self.steps+1]=row;self.current=row
 if not self.awaiting_first then self:CloseStep();self.batch={};self:DumpSteps();self:Flush()end
end
function Trace:FirstSeed(target)
 if not self.awaiting_first or self.finished then return end
 local s=self:Snapshot();self:CloseStep(nil,nil,s)
 self.awaiting_first=false;self.finished=true;self.first_seed=s
 self.batch={};self:DumpSteps()
 self:Emit('FIRST_SEED',{crop=target.crop,x=target.x,z=target.z,
  request_to_seed_wall_ms=string.format('%.3f',math.max(0,Real()-(self.request_wall or self.started_wall))*1000),
  plan_to_seed_wall_ms=string.format('%.3f',(s.wall-self.planning.wall)*1000),
  request_to_seed_active_cpu_ms=string.format('%.3f',s.cpu*1000),preview_requested_ms=2000})
 self:Flush()
end
function Trace:Sown(target,block)
 self.seed_use=self.seed_use or {};self.seed_use[target.crop]=(self.seed_use[target.crop]or 0)+1
 if block.done>=block.total and not self.execution_finished then
  self.execution_finished=true
  self:Emit('SOW_COMPLETE',{planned=block.total,actual_done=block.done,used_in_this_session=Fields(self.seed_use),
   planning_to_completion_s=self.planning and Real()-self.started_wall-self.planning.wall or '-',total_elapsed_s=self:Elapsed()})
 end
end
function Trace:Abort(reason)
 if self.finished then
  if self.status=='complete' and self.planning and not self.execution_finished then
   self:Emit('SOW_STOPPED',{reason=reason,actual_done=self.vehicle and self.vehicle._block and self.vehicle._block.done or 0})
   self.execution_finished=true
  end
  return
 end
 if self.planning then
  self:RunEnd();self:CloseStep('cancelled',reason);self.batch={};self:DumpSteps();self:Emit('SOW_CANCELLED',{reason=reason});self:Flush()
  self.finished=true;self.awaiting_first=false
 else self:Complete('cancelled',reason)end
end
function M.Request(inst)
 inst._aom_plan_request={cpu=os.clock(),wall=Real(),game=Game()}
end
function M.New(inst,cx,cz,quiet)
 serial=serial+1
 local request=inst._aom_plan_request;inst._aom_plan_request=nil
 local start_cpu,start_wall,start_game=os.clock(),Real(),Game()
 local trace=setmetatable({quiet=quiet,id=tostring(inst.GUID or 'vehicle')..'-'..serial,vehicle=inst,steps={},printed=0,context={x=cx,z=cz,
  season=TheWorld.state.season,request_season=TheWorld.state.season,frame_seconds=FRAMES or 1/30,execution_mode="world_serial_sliced",tick_cpu_budget_ms=quiet and 1 or 4,max_resumes_per_tick=1024,strategy=inst._seed_strategy or "GIANT",mod_version="0.5.19",algorithm_build=require("aom_planner_build").fingerprint},
  slice_bins={0,0,0,0,0},cpu=0,active_wall=0,ticks=0,resumes=0,cpu_budget_hits=0,resume_limit_hits=0,
  max_resume_cpu=0,max_tick_cpu=0,long_resumes=0,max_gap=0,
  request_wall=request and request.wall or start_wall,started_epoch=os.time(),started_cpu=start_cpu,started_wall=start_wall,started_game=start_game,
  wall_basis=GetTimeRealSeconds and 'engine_realtime_seconds' or 'system_wall_seconds'},Trace)
 trace:Skip('work_dispatch','outside_planning_timer')
 if request then trace:Context({work_to_plan_before_timer_s=math.max(0,start_wall-request.wall)})end
 local row={id='initial_dispatch',start={wall=0,cpu=0,active_wall=0,game=0,process_cpu=0},resumes=0,ticks=0}
 trace.steps[#trace.steps+1]=row;trace.current=row
 trace:Emit('START',{wall_clock=trace.wall_basis,wall_precision_ms=Precision(),log_file=Log.Path() or 'not_configured',
  started_at=os.date('%Y-%m-%dT%H:%M:%S%z',trace.started_epoch),start_epoch_seconds=trace.started_epoch,
  timer_origin='planning_task_created',strategy=trace.context.strategy,mod_version=trace.context.mod_version,algorithm_build=trace.context.algorithm_build,execution_mode=trace.context.execution_mode,tick_cpu_budget_ms=quiet and 1 or 4,max_resumes_per_tick=1024})
 local store=inst.components and inst.components.aom_attachment_store
 if store then
  local stock=store:CountSeedsByCrop(require('aom_seed_strategy').GetCropOfSeedItem);local values={}
  for k,n in pairs(stock)do values[#values+1]=k..':'..n end;table.sort(values)
  trace:Context({seed_stock=table.concat(values,','),input_stage='before_field_scan'});trace:Emit('INPUT',trace.context)
 end
 local rules={}
 for k,d in pairs(require('prefabs/farm_plant_defs').PLANT_DEFS)do
  local v=require('aom_seed_balance').Vector(d)
  if v then
   local seasons={};for season,yes in pairs(d.good_seasons or {})do if yes then seasons[#seasons+1]=season end end;table.sort(seasons)
   rules[#rules+1]=k..','..(d.family_min_count or 4)..','..(d.family_check_dist or 4)..','..table.concat(v,',')..','..table.concat(seasons,'/')
  end
 end
 table.sort(rules)
 trace:Emit('RULES',{format='crop,family_min,radius,net1,net2,net3,seasons;...',definitions=table.concat(rules,';'),
  spacing=GetFarmTillSpacing and GetFarmTillSpacing()or 1.25,density=TUNING.FARM_PANT_OVERCROWDING_MAX_PLANTS or 10})
 trace:Progress(true)
 return trace
end
function M.Cancel(inst,reason)
 local trace=inst._aom_plan_trace
 if trace then trace:Abort(reason or 'WORK_STOPPED')end
 inst._aom_plan_trace=nil
end
return M
