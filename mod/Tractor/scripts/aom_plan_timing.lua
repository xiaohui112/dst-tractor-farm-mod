-- 游戏异步规划计时：保留内存统计、人物进度和一次控制台结果，不创建日志文件。
-- os.clock是进程CPU；只累计本任务执行区间，排除跨帧间隔，但仍可能包含并行引擎线程CPU。
local M={}
local L=require("aom_locale").Text
local Budget=require('aom_plan_budget')
local serial=0
-- 原版 mainfunctions.GetTimeRealSeconds 将 TheSim:GetRealTime 毫秒转换为秒。
local function Real()return GetTimeRealSeconds and GetTimeRealSeconds()or os.time()end
local function Game()return GetTime and GetTime() or 0 end
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
 require('aom_feedback').Say(self.vehicle and self.vehicle._rider,text,duration or 3,true)
end
function Trace:Progress(force)
 if self.finished or self.planning then return end
 local elapsed=self:Elapsed()
 if not force and self.last_progress and elapsed-self.last_progress<2 then return end
 self.last_progress=elapsed
 local text=self:Text();self:Say(text,3)
 if not self.quiet and self.vehicle and self.vehicle._planprogress_net then self.vehicle._planprogress_net:set(text)end
end
function Trace:Console(plan)
 if self.quiet or self.console_printed then return end
 self.console_printed=true
 local text='[Tractor][plan '..self.id..'] '..self.completed_text
  ..L('；实际用时%.3f秒，计算%.3f秒，每帧额度%d毫秒',self.planning.wall,self.planning.cpu,self.context.tick_cpu_budget_ms)
 local details=plan and plan.construction
 if details then
  text=text..L('；数量阶段计算%.3f秒，排列阶段计算%.3f秒',details.quantity_seconds or 0,details.arrangement_seconds or 0)
 end
 if self.reason then text=text..' ['..tostring(self.reason)..']'end
 print(text)
 -- 服务端 print 不会自动进入远端玩家的控制台；定向发给本次规划的驾驶者。
 local player=self.player
 if player and player.userid and player~=ThePlayer then
  SendModRPCToClient(GetClientModRPC('aom_rpc','AOM_PLAN_RESULT'),player.userid,text)
 end
end
function Trace:Complete(status,reason,plan)
 if self.finished then return end
 self:RunEnd();local s=self:Snapshot();self:CloseStep(status=='complete' and 'done' or status,reason,s)
 self.planning=s;self.status=status;self.reason=reason
 self.completed_seconds=math.max(0,math.floor(s.wall))
 if status=='complete' then
  self.completed_text=L('巨大化规划完成：用时%d秒，开始播种',self.completed_seconds)
  self:Say(self.completed_text,4)
  if not self.quiet and self.vehicle and self.vehicle._planprogress_net then self.vehicle._planprogress_net:set(self.completed_text)end
 elseif status=='cancelled' then
  self.completed_text=L('巨大化规划已取消：用时%d秒',self.completed_seconds)
  self:Say(self.completed_text,3)
 else
  self.completed_text=L('巨大化规划未完成：用时%d秒',self.completed_seconds)
  self:Say(self.completed_text,3)
 end
 self:Console(plan)
 self.awaiting_first=status=='complete' and plan~=nil
 self.finished=not self.awaiting_first
end
function Trace:FirstSeed(target)
 if not self.awaiting_first or self.finished then return end
 local s=self:Snapshot();self:CloseStep(nil,nil,s)
 self.awaiting_first=false;self.finished=true;self.first_seed=s
end
function Trace:Sown(target,block)
 if block.done>=block.total then self.execution_finished=true end
end
function Trace:Abort(reason)
 if self.finished then
  if self.status=='complete' and self.planning then self.execution_finished=true end
  return
 end
 if self.planning then
  self:RunEnd();self:CloseStep('cancelled',reason)
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
 local trace=setmetatable({quiet=quiet,id=tostring(inst.GUID or 'vehicle')..'-'..serial,vehicle=inst,player=inst._rider,steps={},context={x=cx,z=cz,
  season=TheWorld.state.season,request_season=TheWorld.state.season,frame_seconds=FRAMES or 1/30,execution_mode="world_serial_sliced",tick_cpu_budget_ms=Budget.Milliseconds(quiet),max_resumes_per_tick=1024,strategy=inst._seed_strategy or "GIANT"},
  slice_bins={0,0,0,0,0},cpu=0,active_wall=0,ticks=0,resumes=0,cpu_budget_hits=0,resume_limit_hits=0,
  max_resume_cpu=0,max_tick_cpu=0,long_resumes=0,max_gap=0,
  request_wall=request and request.wall or start_wall,started_cpu=start_cpu,started_wall=start_wall,started_game=start_game,
  wall_basis=GetTimeRealSeconds and 'engine_realtime_seconds' or 'system_wall_seconds'},Trace)
 trace:Skip('work_dispatch','outside_planning_timer')
 if request then trace:Context({work_to_plan_before_timer_s=math.max(0,start_wall-request.wall)})end
 local row={id='initial_dispatch',start={wall=0,cpu=0,active_wall=0,game=0,process_cpu=0},resumes=0,ticks=0}
 trace.steps[#trace.steps+1]=row;trace.current=row
 trace:Progress(true)
 return trace
end
function M.Cancel(inst,reason)
 local trace=inst._aom_plan_trace
 if trace then trace:Abort(reason or 'WORK_STOPPED')end
 inst._aom_plan_trace=nil
end
return M
