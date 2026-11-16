-- 有界整块选配：静态候选保持全部坑位、角色与必要空坑。
local M={}
local Data=require('aom_seed_template_data')
local Layout=require('aom_seed_layout')
M.Specs=Data.Catalog.templates
local function Copy(a)local b={};for k,v in pairs(a)do b[k]=v end;return b end
local function Better(a,b)
 if not b then return true end
 if a.total~=b.total then return a.total>b.total end
 if a.holes~=b.holes then return a.holes<b.holes end
 if a.tidy~=b.tidy then return a.tidy<b.tidy end
 return a.key<b.key
end
function M.Build(crops,stock,tiles,slots,defs,yieldfn,options)
 options=options or {};local task=options.task or {};local trace=options.trace
 local clock=trace and function()return trace:Clock()end or os.clock
 local started=clock();task.started=started;task.phase='template_prepare';task._clock=clock
 if trace then trace:Stage('template_prepare')end
 local placements,validations,geometry_builds=Data.Prepare(crops,stock,tiles,slots,defs,yieldfn,options)
 local geometry=Layout.Geometry(tiles,slots,defs,yieldfn,true);geometry.balanced=true;geometry.nutrients_only=true
 local bytile={};for i=1,#tiles do bytile[i]={}end
 for _,p in ipairs(placements)do for _,ti in ipairs(p.indices)do bytile[ti][#bytile[ti]+1]=p end end
 local prepared=clock()-started;task.phase='template_select'
 if trace then trace:Stage('template_select')end
 local metric_cache,metric_order={},{};local metrics_computed=0
 -- 至少容纳一次完整候选遍历，不能因旧的固定工作量而截掉大田后半段。
 local sweep=0;for _,list in ipairs(bytile)do for _,p in ipairs(list)do sweep=sweep+#p.recipes end end
 local attempts,budget=0,math.max(options.work_budget or 120000,sweep)
 local best,bestscore,bestmodules=nil,nil,{}
 local function Run(pass,kept)
  local remaining=Copy(stock);local occupied,board,modules={}, {},{}
  for i=1,#slots do board[i]=false end
  local order={};for i=1,#tiles do order[i]=i end
  table.sort(order,function(a,b)
   local x,z,u,v=tiles[a].x,tiles[a].z,tiles[b].x,tiles[b].z
   if pass%2==1 then x,z,u,v=z,x,v,u end
   if pass%4>=2 then x,z,u,v=-x,-z,-u,-v end
   return z~=v and z<v or z==v and x<u
  end)
  local total=0
  local function Place(p,r)
   for k,n in pairs(r.needs)do remaining[k]=remaining[k]-n end
   for j,ti in ipairs(p.indices)do occupied[ti]=true;for s=1,9 do board[(ti-1)*9+s]=r.map[p.cells[(j-1)*9+s]]or false end end
   total=total+p.n;modules[#modules+1]={placement=p,recipe=r}
  end
  for _,m in ipairs(kept or {})do Place(m.placement,m.recipe)end
  for _,ti in ipairs(order)do if not occupied[ti] and attempts<budget then
   local chosen,recipe,score=nil,nil,-math.huge
   for _,p in ipairs(bytile[ti])do
    local free=true;for _,i in ipairs(p.indices)do if occupied[i]then free=false;break end end
    if free then for _,r in ipairs(p.recipes)do
     if attempts>=budget then break end;attempts=attempts+1
     local fits=Data.Fits(r,remaining);local scarcity=0
     if fits then
      for j,index in ipairs(p.indices)do for s=1,9 do
       if r.map[p.cells[(j-1)*9+s]]then for _,other in ipairs(geometry.conflicts[(index-1)*9+s])do if board[other]then fits=false end end end
      end end
     end
     if fits then
      for k,n in pairs(r.needs)do scarcity=scarcity+n/(remaining[k]+1)end
      -- 搜索顺序包含大块、密度及稀缺库存等不同方向；最终仅比较完整全田方案。
      local variation=pass<4 and 0 or ((attempts%97)*(pass+11)%101)/101
      local value=p.n/(pass%3==0 and p.area or 1)*10-scarcity*(pass%3==1 and 10 or 1)+variation*12
      if value>score then chosen,recipe,score=p,r,value end
     end
     if attempts%256==0 and yieldfn then yieldfn()end
    end end
   end
   if chosen then Place(chosen,recipe)end
  end;if ti%16==0 and yieldfn then yieldfn()end end
  local used,minx,maxx,minz,maxz={},math.huge,-math.huge,math.huge,-math.huge
  local keys={}
  for _,m in ipairs(modules)do local p=m.placement;keys[#keys+1]=p.id..':'..p.symmetry..':'..string.format('%012.3f:%012.3f',p.origin.z,p.origin.x)..':'..m.recipe.key end
  for i,k in ipairs(board)do if k then local p=slots[i];minx=math.min(minx,p.x);maxx=math.max(maxx,p.x);minz=math.min(minz,p.z);maxz=math.max(maxz,p.z);used[math.floor((i-1)/9)+1]=true end end
  local signature={};for i,k in ipairs(board)do signature[i]=k or '_' end;signature=table.concat(signature,',')
  local metrics=metric_cache[signature];if not metrics then metrics=Layout.Metrics(board,geometry,yieldfn);metric_cache[signature]=metrics;metric_order[#metric_order+1]=signature;metrics_computed=metrics_computed+1;if #metric_order>16 then metric_cache[table.remove(metric_order,1)]=nil end end
  local area=total>0 and (maxx-minx+4/3)*(maxz-minz+4/3)or 0
  table.sort(keys)
  return board,{total=total,holes=area-total*16/9,tidy=metrics.tidy,key=table.concat(keys,'|')},modules
 end
 local function Accept(board,score,modules)
  if Better(score,bestscore)then best,bestscore,bestmodules=board,score,modules end
 end
 for pass=0,47 do if attempts>=budget then break end;Accept(Run(pass));if yieldfn then yieldfn()end end
 for repair=1,64 do
  if attempts>=budget or #bestmodules==0 then break end
  local keep={};local remove=1+repair%4;local start=(repair*7)%#bestmodules
  for i,m in ipairs(bestmodules)do if (i-1-start)%#bestmodules>=remove then keep[#keep+1]=m end end
  Accept(Run(48+repair,keep));if yieldfn then yieldfn()end
 end
 -- 增加目录配比会改变有限搜索的顺序和额度，不能因此丢掉旧候选可构造的方案。
 -- 原有候选单独沿用完整额度及尝试计数；只比较完整全田方案，不逐块拼接两次结果。
 local upper=0;for _,k in ipairs(crops)do upper=upper+stock[k]end;upper=math.min(#slots,upper)
 if bestscore and bestscore.total<upper then
  local original={};local original_sweep=0;local has_extension=false
  for ti,list in ipairs(bytile)do
   original[ti]={}
   for _,p in ipairs(list)do
    local recipes={}
    for _,r in ipairs(p.recipes)do if r.extension then has_extension=true else recipes[#recipes+1]=r end end
    if #recipes>0 then local q=Copy(p);q.recipes=recipes;original[ti][#original[ti]+1]=q;original_sweep=original_sweep+#recipes end
   end
  end
  if has_extension then
   local expanded_board,expanded_score,expanded_modules=best,bestscore,bestmodules
   local expanded_attempts,expanded_budget=attempts,budget
   bytile=original;attempts=0;budget=math.max(options.work_budget or 120000,original_sweep)
   best,bestscore,bestmodules=nil,nil,{}
   for pass=0,47 do if attempts>=budget then break end;Accept(Run(pass));if yieldfn then yieldfn()end end
   for repair=1,64 do
    if attempts>=budget or #bestmodules==0 then break end
    local keep={};local remove=1+repair%4;local start=(repair*7)%#bestmodules
    for i,m in ipairs(bestmodules)do if (i-1-start)%#bestmodules>=remove then keep[#keep+1]=m end end
    Accept(Run(48+repair,keep));if yieldfn then yieldfn()end
   end
   Accept(expanded_board,expanded_score,expanded_modules)
   attempts=attempts+expanded_attempts;budget=budget+expanded_budget
  end
 end
 local exported={}
 for _,m in ipairs(bestmodules)do local p=m.placement;exported[#exported+1]={id=p.id,tiles=Copy(p.indices),symmetry=p.symmetry,origin=Copy(p.origin),crops=Copy(m.recipe.map)}end
 local quantity=clock()-started;task.quantity_seconds=quantity;task.phase='template_finalize'
 if trace then trace:Stage('template_finalize')end
 if bestscore and bestscore.total>0 then
  assert(Layout.Valid(best,geometry,yieldfn),'template legality validation failed')
 else best=nil end
 local total=bestscore and bestscore.total or 0
 local metrics=best and Layout.Metrics(best,geometry,yieldfn)or nil
 local details={total=total,upper=upper,optimal=total==upper,limited=total<upper,mode='templates',modules=exported,catalog_version=Data.Catalog.version,
  quantity_seconds=quantity,arrangement_seconds=clock()-started-quantity,template_prepare_seconds=prepared,template_select_seconds=quantity-prepared,
  attempts=attempts,work_budget=budget,validations=validations,geometry_builds=geometry_builds,metrics_computed=metrics_computed,arrangement={before=metrics,after=metrics,limited=false,moves=0,trials=0}}
 task.last_report=details;task.arrangement_seconds=details.arrangement_seconds;task.phase='done'
 return best,details
end
return M
