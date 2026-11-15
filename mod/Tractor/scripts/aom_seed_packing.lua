-- 先证明最大合法数量，再在固定数量上整理。启发式只提供可行下界。
local M={}
-- 回归中断时也保留当前阶段耗时；未结束的阶段不能作为完成成绩。
function M.Timings()
 local now=os.clock()
 return {
  quantity_seconds=M.quantity_seconds or (M.started and now-M.started or 0),
  arrangement_seconds=M.arrangement_seconds or (M.arrangement_started and now-M.arrangement_started or 0),
  quantity_complete=M.quantity_seconds~=nil,
  arrangement_complete=M.phase=='done',
  basis='process_cpu',
 }
end
function M.Balanced(crops,stock,tiles,slots,defs,yieldfn)
 local Balance=require('aom_seed_balance')
 local Layout=require('aom_seed_layout')
 local Exact=require('aom_seed_exact')
 local clock=os.clock
 local started=clock();M.started=started;M.quantity_seconds=nil;M.arrangement_started=nil;M.arrangement_seconds=nil;M.last_report=nil;M.phase="quantity"
 local patterns,vectors=Balance.Patterns(crops,stock,defs,yieldfn)
 if #patterns==0 then M.quantity_seconds=clock()-started;M.last_report={upper=0,total=0,optimal=true,limited=false,quantity_seconds=M.quantity_seconds,arrangement_seconds=0};M.phase="done";return nil,M.last_report end
 local geometry=Layout.Geometry(tiles,slots,defs,yieldfn);geometry.balanced=true
 local upper=Balance.Upper(crops,stock,vectors,#tiles*patterns[1].n)
 local relaxedupper=upper
 local best,bestn=nil,0
 -- 同一原始互补组合在真实连通地皮上重复，快速覆盖大田；失败不排除任何精确分支。
 for _,pattern in ipairs(patterns) do
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
  prepared=Exact.Prepare(crops,stock,defs,vectors,upper,yieldfn)
  if not prepared.limited then upper=math.min(upper,prepared.upper) end
 end
 if bestn<upper then
  local fast=require('aom_seed_feasible').Find(crops,stock,tiles,slots,defs,upper,yieldfn,1000000)
  if fast then best,bestn=fast,upper end
 end
 if bestn<upper then
  local fast=Exact.BlockWitness(crops,stock,tiles,slots,defs,upper,yieldfn,prepared)
  if fast then best,bestn=fast,upper end
 end
 if bestn<upper then
  local fast=Exact.SubsetWitness(crops,stock,tiles,slots,defs,upper,yieldfn,prepared,patterns,best)
  if fast then best,bestn=fast,upper end
 end
 local board,proof=Exact.Maximize(crops,stock,tiles,slots,defs,best,bestn,upper,yieldfn,{node_limit=128,work_limit=3000,prepared=prepared})
 if proof.pending then
  local warm,report=require('aom_seed_heuristic').Balanced(crops,stock,tiles,slots,defs,yieldfn,false,nil,nil,1000000)
  if warm and report.total>bestn and Layout.Valid(warm,geometry) then best,bestn=warm,report.total end
  board,proof=Exact.Maximize(crops,stock,tiles,slots,defs,best,bestn,upper,yieldfn,{prepared=prepared or proof.prepared})
 end
 proof.relaxed_upper=relaxedupper
 local quantity=clock()-started
 M.quantity_seconds=quantity
 proof.quantity_seconds=quantity;proof.timing_basis="process_cpu";proof.limited=false;M.last_report=proof
 if not board then proof.arrangement_seconds=0;M.phase="done";return nil,proof end
 -- 数量已经证明；排列优化只能交换坑位，不能少播或改变库存用量。
 local arranging=clock();M.arrangement_started=arranging;M.phase="arrangement"
 local arranged,details=Layout.Regularize(board,geometry,yieldfn,false,#tiles>16 and 250 or 1400)
 proof.arrangement_seconds=clock()-arranging
 proof.arrangement=details;M.phase="done"
 M.arrangement_seconds=proof.arrangement_seconds
 return arranged,proof
end
return M
