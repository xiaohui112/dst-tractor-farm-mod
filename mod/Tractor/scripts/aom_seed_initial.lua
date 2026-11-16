-- 最优策略独立的初始见证构造，只提供合法下界；不调用模版策略入口。
local M={}
local Layout=require('aom_seed_layout')
local Balance=require('aom_seed_balance')
local specs={
 {id='single-8',rows={'AAA','A_B','BBB'}},
 {id='pair-12-ratio',rows={'_AAAA_','_BBBB_','_BBBB_'}},
 {id='pair-18-ratio',rows={'BBAABB','BBAABB','BBAABB'}},
 {id='pair-12-equal',rows={'_AAAA_','_BBBB_','_CCCC_'}},
 {id='pair-18-equal',rows={'AAAAAA','BBBBBB','CCCCCC'}},
 {id='pair-16',rows={'_AAAA_','CCCCCC','CBBBBC'}},
 {id='square-32-a',rows={'_CCCC_','ACBBCA','ACBBCA','ACBBCA','ACBBCA','_CCCC_'},preferred={{4,-8,4},{-8,4,4},{2,2,-4}}},
 {id='square-32-b',rows={'_CCCC_','CABBAC','CABBAC','CABBAC','CABBAC','_CCCC_'},preferred={{4,4,-8},{4,-8,4},{-4,2,2}}},
 {id='square-32-four',rows={'_BBBB_','DCAACD','DCAACD','DCAACD','DCAACD','_BBBB_'},preferred={{4,-2,-2},{2,2,-4},{-8,4,4},{2,-4,2}}},
}
M.Specs=specs
local function Copy(a)local b={};for k,v in pairs(a)do b[k]=v end;return b end
local function Point(x,z)return x..':'..z end
local function Variants(spec)
 local result,seen={},{}
 for symmetry=0,7 do
  local w,h=#spec.rows[1],#spec.rows;local cells={}
  for z=0,h-1 do for x=0,w-1 do
   local xx,zz=x,z;local ww,hh=w,h
   if symmetry>=4 then xx=w-1-xx end
   for _=1,symmetry%4 do xx,zz=hh-1-zz,xx;ww,hh=hh,ww end
   cells[zz*ww+xx+1]=spec.rows[z+1]:sub(x+1,x+1)
  end end
  if symmetry%2==1 then w,h=h,w end
  local key=w..':'..table.concat(cells)
  if not seen[key]then seen[key]=true;result[#result+1]={w=w/3,h=h/3,cells=cells,pitwidth=w,symmetry=symmetry}end
 end
 return result
end
local function Recipes(spec,crops,stock,defs,yieldfn)
 local counts={};for _,row in ipairs(spec.rows)do for role in row:gmatch('[A-Z]')do counts[role]=(counts[role]or 0)+1 end end
 local roles={};for role in pairs(counts)do roles[#roles+1]=role end;table.sort(roles)
 local vectors={};for _,k in ipairs(crops)do vectors[k]=Balance.Vector(defs[k])end
 local mapped,used,recipes,keys={}, {},{},{};local work=0
 local function Search(at,x,y,z,preference)
  work=work+1;if work%128==0 and yieldfn then yieldfn()end
  if at>#roles then
   if x~=0 or y~=0 or z~=0 then return end
   local needs,parts={},{}
   for _,role in ipairs(roles)do needs[mapped[role]]=counts[role]end
   for _,k in ipairs(crops)do if needs[k]then parts[#parts+1]=k..':'..needs[k]end end
   local key=table.concat(parts,',');local old=keys[key]
   if old then if preference<old.preference then old.map=Copy(mapped);old.preference=preference end;return end
   local hash=0;for j=1,#key do hash=(hash*31+key:byte(j))%997 end
   local row={hash=hash,map=Copy(mapped),needs=needs,preference=preference,key=key};keys[key]=row;recipes[#recipes+1]=row;return
  end
  local role=roles[at];local n=counts[role]
  for _,k in ipairs(crops)do local v=vectors[k]
   if not used[k]and v and stock[k]>=n then
    local p=spec.preferred and spec.preferred[at];local penalty=p and (p[1]~=v[1]or p[2]~=v[2]or p[3]~=v[3])and 1 or 0
    used[k]=true;mapped[role]=k;Search(at+1,x+n*v[1],y+n*v[2],z+n*v[3],preference+penalty);used[k]=nil
   end
  end
 end
 Search(1,0,0,0,0)
 local total=0;for _,n in pairs(counts)do total=total+n end
 return recipes,total,roles
end
-- 取最紧的一个对偶界作为稀缺度价格，只影响候选顺序，不排除合法解。
local function Prices(crops,stock,defs,capacity)
 local vectors={};for i,k in ipairs(crops)do vectors[i]=Balance.Vector(defs[k])end
 local best,prices=math.huge,{}
 local function Try(a,b)
  local sum,p=0,{}
  for i,k in ipairs(crops)do local v=vectors[i];p[k]=math.max(0,1-a*v[1]-b*v[2]);sum=sum+stock[k]*p[k]end
  if sum<best then best,prices=sum,p end
 end
 Try(0,0)
 for i,v in ipairs(vectors)do
  if v[1]~=0 then Try(1/v[1],0)end;if v[2]~=0 then Try(0,1/v[2])end
  for j=i+1,#vectors do local u=vectors[j];local det=v[1]*u[2]-v[2]*u[1]
   if det~=0 then Try((u[2]-v[2])/det,(v[1]-u[1])/det)end
  end
 end
 return prices,math.min(capacity,math.floor(best+.000001))
end
function M.Build(crops,stock,tiles,slots,defs,yieldfn,options)
 local trace=options and options.trace
 local clock=trace and function()return trace:Clock()end or os.clock
 local started=clock()
 if trace then trace:Stage('template_prepare')end
 local lookup={};for i,t in ipairs(tiles)do lookup[Point(t.x,t.z)]=i end
 local prices,upper=Prices(crops,stock,defs,#slots)
 local banks={};local recipesCount=0
 for _,spec in ipairs(specs)do
  local recipes,n,roles=Recipes(spec,crops,stock,defs,yieldfn)
  if #recipes>0 then banks[#banks+1]={spec=spec,recipes=recipes,n=n,roles=roles,variants=Variants(spec)};recipesCount=recipesCount+#recipes end
 end
 local placements={};local validCache={}
 for anchor,t in ipairs(tiles)do
  placements[anchor]={}
  for _,bank in ipairs(banks)do for _,v in ipairs(bank.variants)do
   local indices,subtiles,subslots,roleboard={}, {},{},{};local fits=true
   for dz=0,v.h-1 do for dx=0,v.w-1 do
    local ti=lookup[Point(t.x+dx*4,t.z+dz*4)]
    if not ti then fits=false else
     indices[#indices+1]=ti;subtiles[#subtiles+1]=tiles[ti]
     for s=1,9 do
      subslots[#subslots+1]=slots[(ti-1)*9+s]
      local col=(s-1)%3;local row=math.floor((s-1)/3)
      local role=v.cells[(dz*3+row)*v.pitwidth+dx*3+col+1];roleboard[#roleboard+1]=role~='_'and role or false
     end
    end
   end end
   if fits then
    local accepted={}
    for _,r in ipairs(bank.recipes)do
     local familydefs,signature={},{}
     for _,role in ipairs(bank.roles)do local d=defs[r.map[role]];familydefs[role]=d;signature[#signature+1]=(d.family_min_count or 4)..':'..(d.family_check_dist or 4)end
     local key=anchor..':'..bank.spec.id..':'..v.symmetry..':'..table.concat(signature,',')
     local valid=validCache[key]
     if valid==nil then local g=Layout.Geometry(subtiles,subslots,familydefs,yieldfn);valid=Layout.Valid(roleboard,g);validCache[key]=valid end
     if valid then accepted[#accepted+1]=r end
    end
    if #accepted>0 then placements[anchor][#placements[anchor]+1]={indices=indices,roles=roleboard,recipes=accepted,n=bank.n,area=#indices,id=bank.spec.id,symmetry=v.symmetry}end
   end
  end end
  if yieldfn then yieldfn()end
 end
 local prepared=clock()-started
 if trace then trace:Stage('template_select')end
 local best,bestn,bestmodules=nil,0,{}
 local rounds=options and options.rounds or 96
 local attempts=0
 local function Run(pass,kept)
  local remaining=Copy(stock);local occupied,board,modules={}, {},{};for i=1,#slots do board[i]=false end
  local order={};for i=1,#tiles do order[i]=i end
  table.sort(order,function(a,b)
   local x,z=tiles[a].x,tiles[a].z;local u,v=tiles[b].x,tiles[b].z
   if pass%2==1 then x,z,u,v=z,x,v,u end
   -- 锚点采用左上角；允许选择覆盖当前地皮的模版。
   return z~=v and z<v or z==v and x<u
  end)
  local total=0
  local function Place(chosen,recipe)
   for k,n in pairs(recipe.needs)do remaining[k]=remaining[k]-n end
   for j,ti in ipairs(chosen.indices)do
    occupied[ti]=true
    for s=1,9 do local role=chosen.roles[(j-1)*9+s];board[(ti-1)*9+s]=role and recipe.map[role]or false end
   end
   total=total+chosen.n;modules[#modules+1]={placement=chosen,recipe=recipe}
  end
  for _,m in ipairs(kept or {})do Place(m.placement,m.recipe)end
  for _,anchor in ipairs(order)do if not occupied[anchor]then
   local chosen,recipe,score=nil,nil,-math.huge
   for _,p in ipairs(placements[anchor])do
    local free=true;for _,i in ipairs(p.indices)do if occupied[i]then free=false;break end end
    if free then for ri,r in ipairs(p.recipes)do
     attempts=attempts+1
     local fits=true;local scarcity,waste,tail=0,0,0
     for k,n in pairs(r.needs)do
      if remaining[k]<n then fits=false;break end
      scarcity=scarcity+n/(remaining[k]+1);waste=waste+n*(prices[k]or 1)
      local rest=remaining[k]-n;if rest>0 and rest<4 then tail=tail+rest end
     end
     if fits then
      -- 多种确定性排序，避免单一贪心提前耗尽某种库存；模板内部不重排。
      local variation=pass>=4 and ((r.hash*(pass+13))%997)/997 or 0
      local density=pass<8 and 100 or pass%3==0 and 5 or 20
      local value=p.n/p.area*density-(waste-p.n)*40-scarcity/p.area*(pass%4==0 and 14 or 3)-tail/p.area*2+p.area*(pass>=8 and pass%4==0 and 40 or .05)-r.preference*.1+variation*(pass%4==1 and 35 or 8)
      if value>score then chosen,recipe,score=p,r,value end
     end
     if attempts%256==0 and yieldfn then yieldfn()end
    end end
   end
   if chosen then Place(chosen,recipe)end
  end end
  return board,total,modules
 end
 for pass=0,rounds-1 do
  local board,total,modules=Run(pass)
  if total>bestn then best,bestn,bestmodules=board,total,modules end
  if bestn==upper then break end
  if yieldfn then yieldfn()end
 end
 -- 有界拆除/回填，释放已选模板占用的库存；始终保留最好合法方案。
 local working=bestmodules
 for attempt=1,(options and options.repairs or 128)do
  if bestn==upper or #working==0 then break end
  local keep={};local remove=2+attempt%5;local start=(attempt*7)%#working
  for i,m in ipairs(working)do if (i-1-start)%#working>=remove then keep[#keep+1]=m end end
  local board,total,modules=Run(rounds+attempt,keep)
  if total>bestn then best,bestn,bestmodules=board,total,modules;working=modules
  elseif total==bestn and attempt%3==0 then working=modules end
  if yieldfn then yieldfn()end
 end
 if options and options.intensify and upper-bestn<=9 then
  for pass=rounds,options.intensify-1 do
   if bestn==upper then break end
   local board,total,modules=Run(pass)
   if total>bestn then best,bestn,bestmodules=board,total,modules end
   if yieldfn then yieldfn()end
  end
 end
 -- 目录候选单独构造，只能提高旧构造的合法下界；不能改变其原有候选顺序。
 if bestn<upper then
  local Data=require('aom_seed_template_data')
  local candidates=Data.Prepare(crops,stock,tiles,slots,defs,yieldfn)
  for pass=0,3 do
   local order={};for i,p in ipairs(candidates)do order[i]=p end
   table.sort(order,function(a,b)
    local x=a.n/(pass%2==0 and a.area or 1);local y=b.n/(pass%2==0 and b.area or 1)
    if x~=y then return x>y end
    if a.id~=b.id then return a.id<b.id end
    if a.symmetry~=b.symmetry then return a.symmetry<b.symmetry end
    if a.origin.z~=b.origin.z then return a.origin.z<b.origin.z end
    return a.origin.x<b.origin.x
   end)
   local remaining=Copy(stock);local occupied,board,modules={}, {},{};local total=0
   for i=1,#slots do board[i]=false end
   for _,p in ipairs(order)do
    local free=true;for _,ti in ipairs(p.indices)do if occupied[ti]then free=false end end
    if free then for _,r in ipairs(p.recipes)do if Data.Fits(r,remaining)then
     local sub={};for i,role in ipairs(p.cells)do sub[i]=r.map[role]or false end
     if Balance.Board(sub,defs)then
      for k,n in pairs(r.needs)do remaining[k]=remaining[k]-n end
      for j,ti in ipairs(p.indices)do occupied[ti]=true;for s=1,9 do board[(ti-1)*9+s]=sub[(j-1)*9+s]end end
      modules[#modules+1]={placement=p,recipe=r};total=total+p.n;break
     end
    end end end
   end
   if total>bestn then local geometry=Layout.Geometry(tiles,slots,defs,yieldfn);geometry.balanced=true
    if Layout.Valid(board,geometry)then best,bestn,bestmodules=board,total,modules end
   end
   if bestn==upper then break end
   if yieldfn then yieldfn()end
  end
 end
 local exported={};for _,m in ipairs(bestmodules)do local p=m.placement;exported[#exported+1]={id=p.id,tiles=Copy(p.indices),symmetry=p.symmetry,crops=Copy(m.recipe.map)}end
 local quantity=clock()-started
 if trace then trace:Stage('template_finalize')end
 local g=Layout.Geometry(tiles,slots,defs,yieldfn);g.balanced=true
 if best then assert(Layout.Valid(best,g),'template final validation failed')end
 local metrics=best and Layout.Metrics(best,g)or nil
 local details={total=bestn,upper=upper,optimal=bestn==upper,limited=bestn<upper,mode='templates',modules=exported,
  quantity_seconds=quantity,arrangement_seconds=clock()-started-quantity,template_prepare_seconds=prepared,
  template_select_seconds=quantity-prepared,recipes=recipesCount,attempts=attempts,
  arrangement={before=metrics,after=metrics,limited=false,moves=0,trials=0}}
 return best,details
end
return M
