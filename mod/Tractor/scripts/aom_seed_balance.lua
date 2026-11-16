-- 巨大化配比只依赖原版作物定义；从不读取地皮现有肥力。
local M={}
function M.Vector(def)
 if not def or not def.nutrient_consumption or not def.nutrient_restoration then return nil end
 local consume,restore=def.nutrient_consumption,def.nutrient_restoration
 local total,types=0,0
 for i=1,3 do total=total+(consume[i] or 0);if restore[i] then types=types+1 end end
 if types==0 then return nil end
 local per=total/types
 -- 不可整除时原版随机回补余数，不能当作确定互补配比。
 if per%1~=0 then return nil end
 local out={};for i=1,3 do out[i]=(restore[i] and per or 0)-(consume[i] or 0) end
 return out
end
function M.Tile(cells,defs)
 local net={0,0,0}
 for _,k in ipairs(cells) do if k then
  local v=M.Vector(defs[k]);if not v then return false end
  for j=1,3 do net[j]=net[j]+v[j] end
 end end
 return math.abs(net[1])+math.abs(net[2])+math.abs(net[3])<.000001,net
end
-- 通用4+4九宫格图案保留中心坑；与作物名称无关。
function M.Shape(cells)
 local counts,total,types={},0,0
 for _,k in ipairs(cells) do if k then total=total+1;if not counts[k] then counts[k]=0;types=types+1 end;counts[k]=counts[k]+1 end end
 if total==8 and types==2 then
  for _,n in pairs(counts) do if n~=4 then return true end end
  return not cells[5]
 end
 return true
end
function M.Board(board,defs,nutrients_only,yieldfn)
 for t=1,#board/9 do
  local cells={};for s=1,9 do cells[s]=board[(t-1)*9+s] end
  if not M.Tile(cells,defs) or (not nutrients_only and not M.Shape(cells)) then return false end
  if t%16==0 and yieldfn then yieldfn()end
 end
 return true
end
-- 枚举一格至多九株的全部互补数量组合。允许同族跨地皮，最终按真实距离验证。
local patternCache,patternOrder={},{}
function M.Patterns(crops,counts,defs,yieldfn)
 local vectors={};for i,k in ipairs(crops) do vectors[i]=M.Vector(defs[k]) end
 local signature={}
 for i,k in ipairs(crops) do signature[#signature+1]=k..':'..math.min(9,counts[k])..':'..(vectors[i] and table.concat(vectors[i],',') or '-') end
 signature=table.concat(signature,'|')
 if patternCache[signature] then return patternCache[signature],vectors end
 local patterns,current,nodes={}, {},0
 local function Search(i,left,total,x,y,z)
  nodes=nodes+1;if nodes%256==0 and yieldfn then yieldfn() end
  if i>#crops then
   if total>0 and math.abs(x)+math.abs(y)+math.abs(z)<.000001 then
    local p={n=total,counts={}};local fours=0;for j=1,#crops do p.counts[j]=current[j];if current[j]==4 then fours=fours+1 end end;p.center_gap=total==8 and fours==2;patterns[#patterns+1]=p
   end
   return
  end
  local v=vectors[i];local maximum=v and math.min(counts[crops[i]],left) or 0
  for n=0,maximum do
   current[i]=n
   Search(i+1,left-n,total+n,x+n*(v and v[1] or 0),y+n*(v and v[2] or 0),z+n*(v and v[3] or 0))
  end
 end
 Search(1,9,0,0,0,0)
 table.sort(patterns,function(a,b)
  if a.n~=b.n then return a.n>b.n end
  for i=1,#crops do if a.counts[i]~=b.counts[i] then return a.counts[i]>b.counts[i] end end
  return false
 end)
 patternCache[signature]=patterns;patternOrder[#patternOrder+1]=signature
 if #patternOrder>16 then patternCache[table.remove(patternOrder,1)]=nil end
 return patterns,vectors
end
-- 连续线性松弛的安全数量上界：逐格互补还必须满足整片净变化为零。
-- 任意对偶系数均给出上界，不把未完成的搜索伪报为全局最优。
function M.Upper(crops,stock,vectors,capacity)
 local best=capacity
 local function Bound(a,b)
  local n=0
  for i,k in ipairs(crops) do local v=vectors[i]
   if v then n=n+stock[k]*math.max(0,1-a*v[1]-b*v[2]) end
  end
  best=math.min(best,math.floor(n+.000001))
 end
 Bound(0,0)
 for i,v in ipairs(vectors) do
  if v[1]~=0 then Bound(1/v[1],0) end
  if v[2]~=0 then Bound(0,1/v[2]) end
  for j=i+1,#vectors do local w=vectors[j];local det=v[1]*w[2]-v[2]*w[1]
   if math.abs(det)>.000001 then Bound((w[2]-v[2])/det,(v[1]-w[1])/det) end
  end
 end
 return best
end
-- 全局库存分配先解净变化方程；最后两个独立作物由方程直接求解，
-- 避免在大量单格组合中重复搜索不同的作物集合。
function M.Allocations(crops,stock,vectors,capacity,yieldfn,options)
 local defs=require('prefabs/farm_plant_defs').PLANT_DEFS
 local order={};for i=1,#crops do order[i]=i end
 local first,second,weight=nil,nil,-1
 for i,v in ipairs(vectors) do for j=i+1,#vectors do local w=vectors[j]
  if v[1]*w[2]-v[2]*w[1]~=0 then
   local cost=stock[crops[i]]*stock[crops[j]]
   if cost>weight then first,second,weight=i,j,cost end
  end
 end end
 if first then
  order={};for i=1,#crops do if i~=first and i~=second then order[#order+1]=i end end
  table.sort(order,function(a,b)return stock[crops[a]]<stock[crops[b]] end)
  order[#order+1]=first;order[#order+1]=second
 end
 local counts,bytotal,best,nodes,limited={}, {},0,0,false
 local seen,classes,keys={}, {},{}
 for i,k in ipairs(crops) do
  local signature=table.concat(vectors[i],',')..':'..(defs[k].family_min_count or 4)..':'..(defs[k].family_check_dist or 4)
  if not classes[signature] then classes[signature]={};keys[#keys+1]=signature end
  classes[signature][#classes[signature]+1]=i
 end
 table.sort(keys)
 local function Store(total)
  if total<=0 or total>capacity then return end
  local signature={}
  for _,key in ipairs(keys) do
   local values={};for _,i in ipairs(classes[key]) do values[#values+1]=counts[i] or 0 end;table.sort(values)
   signature[#signature+1]=key..'='..table.concat(values,',')
  end
  signature=total..';'..table.concat(signature,'|')
  if seen[signature] then return end;seen[signature]=true
  bytotal[total]=bytotal[total] or {}
  if #bytotal[total]<(options and options.uncapped and math.huge or 48) then local a={};for i=1,#crops do a[i]=counts[i] or 0 end;bytotal[total][#bytotal[total]+1]=a end
  best=math.max(best,total)
 end
 local function Allowed(i,n)
  return n>=0 and n%1==0 and n<=stock[crops[i]] and (n==0 or n>=(defs[crops[i]].family_min_count or 4))
 end
 local function Search(at,total,x,y)
  nodes=nodes+1;if nodes>(options and options.node_limit or 24000) then limited=true;return end
  if nodes%128==0 and yieldfn then yieldfn() end
  if total>capacity then return end
  if at>#order then if x==0 and y==0 then Store(total) end;return end
  if first and at==#order-1 then
   local i,j=order[at],order[at+1];local v,w=vectors[i],vectors[j];local det=v[1]*w[2]-v[2]*w[1]
   local a=(-x*w[2]+y*w[1])/det;local b=(-y*v[1]+x*v[2])/det
   if Allowed(i,a) and Allowed(j,b) then counts[i],counts[j]=a,b;Store(total+a+b) end
   counts[i],counts[j]=0,0;return
  end
  local i=order[at];local v=vectors[i];local maximum=math.min(stock[crops[i]],capacity-total)
  for n=maximum,0,-1 do if Allowed(i,n) then
   counts[i]=n;Search(at+1,total+n,x+n*v[1],y+n*v[2])
   if limited then break end
  end end
  counts[i]=0
 end
 Search(1,0,0,0)
 for _,list in pairs(bytotal) do table.sort(list,function(a,b)
  local x,y=0,0;for i=1,#crops do x=x+a[i]*a[i];y=y+b[i]*b[i] end
  if x~=y then return x<y end
  for i=1,#crops do if a[i]~=b[i] then return a[i]>b[i] end end
  return false
 end) end
 return bytotal,best,limited,nodes
end
-- 固定目标株数后联立“总株数+两维净变化”，直接解出最多三个作物数量。
-- 同属性作物按库存排序，只枚举可通过整体改名覆盖的规范代表。
function M.TargetAllocations(crops,stock,vectors,target,defs,yieldfn,node_limit)
 local K=#crops
 local function Det(i,j,k)
  local a,b,c=vectors[i],vectors[j],vectors[k]
  return (b[1]-a[1])*(c[2]-a[2])-(c[1]-a[1])*(b[2]-a[2])
 end
 local pivots,weight={},-1
 for i=1,K do for j=i+1,K do for k=j+1,K do
  local w=(stock[crops[i]]+1)*(stock[crops[j]]+1)*(stock[crops[k]]+1)
  if Det(i,j,k)~=0 and w>weight then pivots={i,j,k};weight=w end
 end end end
 if #pivots==0 then
  for i=1,K do for j=i+1,K do
   local a,b=vectors[i],vectors[j];local w=(stock[crops[i]]+1)*(stock[crops[j]]+1)
   if (a[1]~=b[1] or a[2]~=b[2]) and w>weight then pivots={i,j};weight=w end
  end end
 end
 if #pivots==0 and K>0 then local best=1;for i=2,K do if stock[crops[i]]>stock[crops[best]] then best=i end end;pivots={best} end
 local pivotSet={};for _,i in ipairs(pivots) do pivotSet[i]=true end
 local order={};for i=1,K do if not pivotSet[i] then order[#order+1]=i end end
 table.sort(order,function(a,b)return stock[crops[a]]~=stock[crops[b]] and stock[crops[a]]<stock[crops[b]] or stock[crops[a]]==stock[crops[b]] and a<b end)
 for _,i in ipairs(pivots) do order[#order+1]=i end
 local groups,groupof,rank={}, {},{}
 for i,k in ipairs(crops) do
  local key=table.concat(vectors[i],',')..':'..(defs[k].family_min_count or 4)..':'..(defs[k].family_check_dist or 4)
  if not groups[key] then groups[key]={} end;groups[key][#groups[key]+1]=i;groupof[i]=groups[key]
 end
 for _,group in pairs(groups) do
  table.sort(group,function(a,b)return stock[crops[a]]~=stock[crops[b]] and stock[crops[a]]>stock[crops[b]] or stock[crops[a]]==stock[crops[b]] and a<b end)
  for r,i in ipairs(group) do rank[i]=r end
 end
 local counts,assigned,profiles={}, {},{}
 local nodes,limited=0,false
 local function Allowed(i,n)
  if n<0 or n%1~=0 or n>stock[crops[i]] or n>0 and n<(defs[crops[i]].family_min_count or 4) then return false end
  for _,j in ipairs(groupof[i]) do if assigned[j] and (rank[j]<rank[i] and counts[j]<n or rank[j]>rank[i] and counts[j]>n) then return false end end
  return true
 end
 local suffix={};suffix[K+1]=0;for at=K,1,-1 do suffix[at]=suffix[at+1]+stock[crops[order[at]]] end
 local function Store()
  local copy={};for i=1,K do copy[i]=counts[i] or 0 end;profiles[#profiles+1]=copy
 end
 local function Search(at,total,x,y)
  nodes=nodes+1;if node_limit and nodes>node_limit then limited=true;return end
  if nodes%128==0 and yieldfn then yieldfn() end
  if total>target or total+suffix[at]<target then return end
  if at>K then if total==target and x==0 and y==0 then Store() end;return end
  if at==K-#pivots+1 then
   local R=target-total;local values={}
   if #pivots==3 then
    local i,j,k=pivots[1],pivots[2],pivots[3];local a,b,c=vectors[i],vectors[j],vectors[k]
    local bx,by=-x-R*a[1],-y-R*a[2];local det=Det(i,j,k)
    local v=(bx*(c[2]-a[2])-by*(c[1]-a[1]))/det
    local w=((b[1]-a[1])*by-(b[2]-a[2])*bx)/det
    values={R-v-w,v,w}
   elseif #pivots==2 then
    local a,b=vectors[pivots[1]],vectors[pivots[2]];local axis=a[1]~=b[1] and 1 or 2
    local v=((axis==1 and -x or -y)-R*b[axis])/(a[axis]-b[axis]);values={v,R-v}
   else values={R} end
   local xx,yy=x,y;local ok=true
   for q,i in ipairs(pivots) do
    local n=values[q]
    if not Allowed(i,n) then ok=false;break end
    counts[i]=n;assigned[i]=true;xx=xx+n*vectors[i][1];yy=yy+n*vectors[i][2]
   end
   if ok and xx==0 and yy==0 then Store() end
   for _,i in ipairs(pivots) do assigned[i]=nil;counts[i]=nil end
   return
  end
  local i=order[at];local v=vectors[i]
  for n=math.min(stock[crops[i]],target-total),0,-1 do if Allowed(i,n) then
   counts[i]=n;assigned[i]=true;Search(at+1,total+n,x+n*v[1],y+n*v[2]);assigned[i]=nil;counts[i]=nil
   if limited then break end
  end end
 end
 if K>0 then Search(1,0,0,0) end
 table.sort(profiles,function(a,b)
  local x,y=0,0;for i=1,K do if a[i]>0 then x=x+1 end;if b[i]>0 then y=y+1 end end
  if x~=y then return x<y end
  for i=1,K do if a[i]~=b[i] then return a[i]>b[i] end end
  return false
 end)
 return profiles,limited,nodes,pivots
end
return M
