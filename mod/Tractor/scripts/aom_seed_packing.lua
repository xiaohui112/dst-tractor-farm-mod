-- 先证明最大合法数量，再在固定数量上整理。启发式只提供可行下界。
local M={}
-- 回归中断时也保留当前阶段耗时；未结束的阶段不能作为完成成绩。
function M.Timings(task)
 local M=task or M
 local now=(M._clock or os.clock)()
 return {
  quantity_seconds=M.quantity_seconds or (M.started and now-M.started or 0),
  arrangement_seconds=M.arrangement_seconds or (M.arrangement_started and now-M.arrangement_started or 0),
  quantity_complete=M.quantity_seconds~=nil,
  arrangement_complete=M.phase=='done',
  basis=M._clock_basis or 'process_cpu',
 }
end
function M.Balanced(crops,stock,tiles,slots,defs,yieldfn,trace,task)
 local M=task or M
 local Balance=require('aom_seed_balance')
 local Layout=require('aom_seed_layout')
 local Exact=require('aom_seed_exact')
 local function Stage(id)if trace then trace:Stage(id)end end
 local function Skip(id,reason)if trace then trace:Skip(id,reason)end end
 local clock=trace and function()return trace:Clock()end or os.clock
 M._clock=clock;M._clock_basis=trace and 'process_cpu_during_task_slices' or 'process_cpu'
 local started=clock();M.started=started;M.quantity_seconds=nil;M.arrangement_started=nil;M.arrangement_seconds=nil;M.last_report=nil;M.phase="quantity"
 Stage("patterns")
 local patterns,vectors=Balance.Patterns(crops,stock,defs,yieldfn)
 if #patterns==0 then M.quantity_seconds=clock()-started;M.last_report={upper=0,total=0,optimal=true,limited=false,quantity_seconds=M.quantity_seconds,arrangement_seconds=0};M.phase="done";return nil,M.last_report end
 if trace then trace:Context({patterns=#patterns})end
 Stage("geometry")
 local geometry=Layout.Geometry(tiles,slots,defs,yieldfn);geometry.balanced=true
 if not geometry.complete then
  M.quantity_seconds=clock()-started;M.arrangement_seconds=0;M.phase='done'
  M.last_report={total=0,upper=0,optimal=false,invalid_geometry=true,quantity_seconds=M.quantity_seconds,arrangement_seconds=0}
  return nil,M.last_report
 end
 Stage("upper_bound")
 local upper=Balance.Upper(crops,stock,vectors,#tiles*patterns[1].n)
 if #tiles==1 then
  local single=0
  for _,p in ipairs(patterns)do local possible=true;for c,n in ipairs(p.counts)do if n>0 and n<(defs[crops[c]].family_min_count or 4)then possible=false;break end end;if possible then single=math.max(single,p.n)end end
  upper=math.min(upper,single)
 end
 local relaxedupper=upper
 if trace then trace:Context({relaxed_upper=relaxedupper})end
 Stage("initial_layout")
 local best,bestn=nil,0
 Stage('template_witness')
 local warm,warmreport=require('aom_seed_initial').Build(crops,stock,tiles,slots,defs,yieldfn,{rounds=#tiles>16 and 512 or 32,repairs=#tiles>16 and 1024 or 32,intensify=#tiles>16 and 4096 or nil})
 if warm and Layout.Valid(warm,geometry)then best,bestn=warm,warmreport.total end
 local function Candidate(candidate,n)
  if candidate and n>bestn and Layout.Valid(candidate,geometry)then best,bestn=candidate,n end
 end
 local regionThread
 if #tiles>=6 and bestn<upper then
  Stage('region_probe')
  regionThread=coroutine.create(function()return require('aom_seed_regions').Find(crops,stock,tiles,slots,defs,patterns,upper,coroutine.yield,Candidate)end)
  for _=1,4096 do
   local ok,candidate=coroutine.resume(regionThread);if not ok then error(candidate,0)end
   if coroutine.status(regionThread)=='dead' then
    if candidate and Layout.Valid(candidate,geometry)then best,bestn=candidate,upper end
    regionThread=nil;break
   end
   if yieldfn then yieldfn()end
  end
  Stage('initial_layout')
 end
 -- 同一原始互补组合在真实连通地皮上重复，快速覆盖大田；失败不排除任何精确分支。
 for pi,pattern in ipairs(patterns) do
  -- 这里只构造下界；完整搜索仍覆盖所有配比。
  if #tiles>16 and pi>24 then break end
  local occupied=#tiles
  for c,n in ipairs(pattern.counts) do if n>0 then occupied=math.min(occupied,math.floor(stock[crops[c]]/n)) end end
  local possible=true
  for c,n in ipairs(pattern.counts) do if n>0 and n*occupied<(defs[crops[c]].family_min_count or 4) then possible=false;break end end
  if possible and occupied*pattern.n>bestn then
   local cells={};for c,n in ipairs(pattern.counts) do for _=1,n do cells[#cells+1]=crops[c] end end
   while #cells<9 do cells[#cells+1]=false end
   local candidates=Layout.Candidates(cells,yieldfn)
   for index,candidate in ipairs(candidates) do
    if index>16 then break end
    if Balance.Shape(candidate.cells) then
     local board={}
     for t=1,#tiles do for s=1,9 do board[(t-1)*9+s]=t<=occupied and candidate.cells[s] or false end end
     if Layout.Valid(board,geometry) then best,bestn=board,occupied*pattern.n;break end
    end
   end
  end
  if bestn==upper then break end
 end
 local prepared
 if bestn<upper then
  Stage("quota_prepare")
  prepared=Exact.Prepare(crops,stock,defs,vectors,upper,yieldfn)
  if not prepared.limited then upper=math.min(upper,prepared.upper) end
 else Skip("quota_prepare","initial_layout_reached_upper")end
 -- 各方法保存自己的调用栈；完整搜索从一开始持续推进，不再丢弃有界探测栈。
 local board,proof
 if bestn==upper then
  board=best;proof={total=bestn,upper=upper,optimal=true,mode='upper-bound-witness'}
 else
  local tasks={};local exactProgress
  local function Add(name,fn,complete,thread)
   tasks[#tasks+1]={name=name,co=thread or coroutine.create(fn),complete=complete,resumes=0,cpu=0}
  end
  local function Pause()coroutine.yield()end
  Add('exact_proof',function()return Exact.Maximize(crops,stock,tiles,slots,defs,best,bestn,upper,Pause,{prepared=prepared,incumbent=function()return best,bestn end,observe=function(p)exactProgress=p end})end,true)
  Add('constructive_search',function()
   local candidate=require('aom_seed_feasible').Find(crops,stock,tiles,slots,defs,upper,Pause,1000000)
   if candidate then return candidate end
   candidate=Exact.BlockWitness(crops,stock,tiles,slots,defs,upper,Pause,prepared)
   if candidate then return candidate end
   candidate=Exact.SubsetWitness(crops,stock,tiles,slots,defs,upper,Pause,prepared,patterns,best)
   if candidate then return candidate end
   local warm,report=require('aom_seed_heuristic').Balanced(crops,stock,tiles,slots,defs,Pause,false,nil,nil,1000000)
   if warm and Layout.Valid(warm,geometry)and report.total>bestn then best,bestn=warm,report.total end
   if bestn==upper then return best end
   -- 新下界也作为另一条完整证明路径的分支提示；原证明栈继续保留。
   return Exact.Maximize(crops,stock,tiles,slots,defs,best,bestn,upper,Pause,{prepared=prepared,incumbent=function()return best,bestn end})
  end)
  if regionThread then Add('region_witness',nil,false,regionThread)end
  Stage("quantity_portfolio")
  local round=0
  while not proof do
   round=round+1
   for _,task in ipairs(tasks) do if not task.done then
    if trace then trace:Context({active_method=task.name})end
    -- 完整搜索获得稳定份额，辅助构造不会阻塞它，也不以时限截断证明。
    for _=1,(task.complete and 1 or (task.name=='constructive_search' and 8 or 2)) do
     local t=clock();local ok,candidate,report=coroutine.resume(task.co)
     task.cpu=task.cpu+clock()-t;task.resumes=task.resumes+1
     if trace then trace:Context({best_legal=bestn,target=exactProgress and exactProgress.target or upper,
      proof_upper=exactProgress and exactProgress.target or upper,proof_nodes=exactProgress and exactProgress.nodes or 0})end
     if not ok then error(candidate,0)end
     if coroutine.status(task.co)=='dead' then
      task.done=true
      if task.complete or report and report.optimal then
       assert(report and report.optimal and not report.pending,"complete search returned without proof")
       board,proof=candidate,report
      elseif candidate and Layout.Valid(candidate,geometry) then
       local n=0;for _,k in ipairs(candidate)do if k then n=n+1 end end
       task.total=n
       if n>bestn then best,bestn=candidate,n end
       if n==upper then board=candidate;proof={total=n,upper=upper,optimal=true,mode=task.name..'-upper-bound'}end
      end
      break
     end
     if yieldfn then yieldfn()end
    end
    if proof then break end
   end end
  end
  proof.methods={}
  for _,task in ipairs(tasks)do
   proof.methods[#proof.methods+1]={name=task.name,cpu=task.cpu,resumes=task.resumes,complete=task.done or false,total=task.total or 0}
   if trace then trace:Emit('METHOD',proof.methods[#proof.methods])end
  end
 end
 if trace then trace:Context({quantity_total=proof.total,quantity_upper=proof.upper,proof_mode=proof.mode or "-",proof_nodes=proof.nodes or 0,proof_propagations=proof.propagations or 0})end
 proof.relaxed_upper=relaxedupper
 local quantity=clock()-started
 M.quantity_seconds=quantity
 proof.quantity_seconds=quantity;proof.timing_basis=M._clock_basis;proof.limited=false;M.last_report=proof
 if not board then proof.arrangement_seconds=0;M.phase="done";return nil,proof end
 -- 数量已经证明；排列优化只能交换坑位，不能少播或改变库存用量。
 local arranging=clock();M.arrangement_started=arranging;M.phase="arrangement"
 Stage("arrangement")
 local arranged,details=Layout.Regularize(board,geometry,yieldfn,false,#tiles>16 and 250 or 1400,trace)
 proof.arrangement_seconds=clock()-arranging
 proof.arrangement=details;M.phase="done"
 M.arrangement_seconds=proof.arrangement_seconds
 return arranged,proof
end
return M
