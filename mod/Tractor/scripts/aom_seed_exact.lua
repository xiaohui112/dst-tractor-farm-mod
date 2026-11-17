-- 完整的坑位约束搜索。启发式只提供下界；较大数量逐个排除后才交付计划。
-- 域同时满足逐格互补、库存、原版距离同族与坑距；空坑位置不限制可行域。
local M={}
function M.Prepare(crops,stock,defs,vectors,capacity,yieldfn)
 local data={allocations={},targets={},upper=capacity,limited=false,nodes=0}
 function data.Get(target)
  if data.targets[target] then return data.targets[target] end
  local list,limited,nodes=require('aom_seed_balance').TargetAllocations(crops,stock,vectors,target,defs,yieldfn,1000000)
  local entry={allocations=list,limited=limited,nodes=nodes};data.targets[target]=entry;data.allocations[target]=list;data.nodes=data.nodes+nodes
  return entry
 end
 for target=capacity,1,-1 do
  local entry=data.Get(target)
  if entry.limited or #entry.allocations>0 then data.upper=target;data.limited=entry.limited;return data end
 end
 data.upper=0;return data
end
-- 按原版净变化分解库存的可行性构造。只接受达到全田上界的见证；
-- 分组或局部探测失败不会排除全田目标，也不会提供不可行证明。
function M.BlockWitness(crops,stock,tiles,slots,defs,target,yieldfn,prepared)
 local T,K=#tiles,#crops
 if T<4 or K>14 or target<=27 then return nil end
 local entry=prepared.Get(target);local Balance=require('aom_seed_balance');local Layout=require('aom_seed_layout')
 local whole=Layout.Geometry(tiles,slots,defs,yieldfn);whole.balanced=true
 local vectors={};for c,k in ipairs(crops) do vectors[c]=Balance.Vector(defs[k]) end
 local calls=0;local savedProgress=M.progress
 for ai,allocation in ipairs(entry.allocations) do
  if ai>8 or calls>=48 then break end
  local active={};local possible=true
  for c,n in ipairs(allocation) do if n>0 then active[#active+1]=c;if n>2*(defs[crops[c]].family_min_count or 4)-1 then possible=false end end end
  if possible then
   local powers={};for i=1,#active do powers[i]=2^(i-1) end
   local function Has(mask,i)return mask%(powers[i]*2)>=powers[i] end
   local groups,contains={},{}
   for i=1,#active do contains[i]={} end
   local function Enumerate(at,mask,total,x,y)
    if total>36 then return end
    if at>#active then
     if total>0 and x==0 and y==0 and mask<2^#active-1 then
      local group={mask=mask,total=total,minimum=math.ceil(total/9),crops={}}
      for i,c in ipairs(active) do if Has(mask,i) then group.crops[#group.crops+1]=c;contains[i][#contains[i]+1]=group end end
      groups[#groups+1]=group
     end
     return
    end
    Enumerate(at+1,mask,total,x,y)
    local c=active[at];local n=allocation[c];local v=vectors[c]
    Enumerate(at+1,mask+powers[at],total+n,x+n*v[1],y+n*v[2])
   end
   Enumerate(1,0,0,0,0)
   local memo,choice={[0]=0},{}
   local function Partition(mask)
    if memo[mask] then return memo[mask] end
    local first;for i=1,#active do if Has(mask,i) then first=i;break end end
    local best=math.huge
    for _,g in ipairs(contains[first]) do
     local fits=true;for i=1,#active do if Has(g.mask,i) and not Has(mask,i) then fits=false;break end end
     if fits then local score=Partition(mask-g.mask)+g.minimum*100+1;if score<best then best=score;choice[mask]=g end end
    end
    memo[mask]=best;return best
   end
   local all=2^#active-1;local score=Partition(all)
   if score<math.huge and math.floor(score/100)<=T then
    local parts={};local mask=all
    while mask>0 do local g=choice[mask];parts[#parts+1]=g;mask=mask-g.mask end
    if #parts>1 then
     table.sort(parts,function(a,b)return #a.crops~=#b.crops and #a.crops>#b.crops or #a.crops==#b.crops and a.total>b.total end)
     local cache={};local initial={};for t=1,T do initial[t]=t end
     local function Place(at,available,board)
      if calls>=48 then return nil end
      if at>#parts then if Layout.Valid(board,whole) then return board end;return nil end
      local part=parts[at];local reserve=0;for q=at+1,#parts do reserve=reserve+parts[q].minimum end
      local names,counts={},{};local token={}
      for _,c in ipairs(part.crops) do local k=crops[c];names[#names+1]=k;counts[k]=allocation[c];token[#token+1]=k..':'..allocation[c] end
      local blockkey=table.concat(token,',')
      for size=part.minimum,math.min(part.minimum+1,#available-reserve) do
       local proposals={};local seen={}
       local function Add(indices)
        local copy={};for i,v in ipairs(indices) do copy[i]=v end;table.sort(copy)
        local key=table.concat(copy,',');if seen[key] then return end;seen[key]=true
        local distance=0;for i,t in ipairs(copy) do for j=1,i-1 do local a,b=tiles[t],tiles[copy[j]];distance=distance+(a.x-b.x)^2+(a.z-b.z)^2 end end
        proposals[#proposals+1]={indices=copy,key=key,score=distance}
       end
       if #available<=12 then
        local selected={}
        local function Choose(first,left)
         if left==0 then Add(selected);return end
         for i=first,#available-left+1 do selected[#selected+1]=available[i];Choose(i+1,left-1);selected[#selected]=nil end
        end
        Choose(1,size)
       else
        for _,anchor in ipairs(available) do
         local order={};for i,t in ipairs(available) do order[i]=t end
         local p=tiles[anchor];local function D(t)local q=tiles[t];return (p.x-q.x)^2+(p.z-q.z)^2 end
         table.sort(order,function(a,b)local x,y=D(a),D(b);return x~=y and x<y or x==y and a<b end)
         local chosen={};for i=1,size do chosen[i]=order[i] end;Add(chosen)
        end
       end
       table.sort(proposals,function(a,b)return a.score~=b.score and a.score<b.score or a.score==b.score and a.key<b.key end)
       for index,proposal in ipairs(proposals) do
        if index>12 or calls>=48 then break end
        local key=blockkey..'/'..proposal.key;local localboard=cache[key]
        if localboard==nil then
         calls=calls+1;local subtiles,subslots={},{}
         for _,t in ipairs(proposal.indices) do subtiles[#subtiles+1]=tiles[t];for s=1,9 do subslots[#subslots+1]=slots[(t-1)*9+s] end end
         local result,proof=M.Maximize(names,counts,subtiles,subslots,defs,nil,0,part.total,yieldfn,{node_limit=512,work_limit=100000})
         M.progress=savedProgress
         localboard=result and proof.total==part.total and result or false;cache[key]=localboard
        end
        if localboard then
         local used,remaining={},{};for _,t in ipairs(proposal.indices) do used[t]=true end
         for _,t in ipairs(available) do if not used[t] then remaining[#remaining+1]=t end end
         local nextboard={};for i,k in ipairs(board) do nextboard[i]=k end
         for q,t in ipairs(proposal.indices) do for s=1,9 do nextboard[(t-1)*9+s]=localboard[(q-1)*9+s] end end
         local result=Place(at+1,remaining,nextboard);if result then return result end
        end
       end
      end
      return nil
     end
     local board={};for i=1,#slots do board[i]=false end
     local result=Place(1,initial,board);if result then M.progress=savedProgress;return result end
    end
   end
  end
 end
 M.progress=savedProgress
 return nil
end
-- 库存只够使用部分地皮时，先在若干紧凑子集上寻找达到全田安全上界的见证。
-- 子集失败只表示本次探测失败；不会排除全田的任何方案或降低目标。
function M.SubsetWitness(crops,stock,tiles,slots,defs,target,yieldfn,prepared,patterns,seed)
 local T=#tiles;local minimum=math.ceil(target/patterns[1].n)
 if minimum>=T then return nil end
 local Layout=require('aom_seed_layout')
 local whole=Layout.Geometry(tiles,slots,defs,yieldfn);whole.balanced=true
 local used={};for t=1,T do local n=0;for s=1,9 do if seed and seed[(t-1)*9+s] then n=n+1 end end;used[t]=n end
 local attempted={};local savedProgress=M.progress
 for size=minimum,math.min(T-1,minimum+2) do
  local proposals={}
  for anchor=1,T do
   local order={};for t=1,T do order[t]=t end
   local p=tiles[anchor]
   local function Distance(t)local q=tiles[t];return (p.x-q.x)^2+(p.z-q.z)^2 end
   table.sort(order,function(a,b)local x,y=Distance(a),Distance(b);return x~=y and x<y or x==y and a<b end)
   local indices,score={},0;for i=1,size do indices[i]=order[i];score=score+Distance(order[i]) end;table.sort(indices)
   proposals[#proposals+1]={indices=indices,score=score}
  end
  table.sort(proposals,function(a,b)return a.score~=b.score and a.score<b.score or a.score==b.score and table.concat(a.indices,',')<table.concat(b.indices,',') end)
  local active={};for t=1,T do active[t]=t end
  table.sort(active,function(a,b)return used[a]~=used[b] and used[a]>used[b] or used[a]==used[b] and a<b end)
  local first={};for i=1,size do first[i]=active[i] end;table.sort(first);table.insert(proposals,1,{indices=first})
  local attempts=0
  for _,proposal in ipairs(proposals) do
   local key=table.concat(proposal.indices,',')
   if not attempted[key] then
    attempted[key]=true;attempts=attempts+1
    local subtiles,subslots={},{}
    for _,t in ipairs(proposal.indices) do subtiles[#subtiles+1]=tiles[t];for s=1,9 do subslots[#subslots+1]=slots[(t-1)*9+s] end end
    local board,proof=M.Maximize(crops,stock,subtiles,subslots,defs,nil,0,target,yieldfn,{node_limit=256,work_limit=12000,prepared=prepared,patterns=patterns})
    M.progress=savedProgress
    if board and proof.total==target then
     local full={};for i=1,#slots do full[i]=false end
     for at,t in ipairs(proposal.indices) do for s=1,9 do full[(t-1)*9+s]=board[(at-1)*9+s] end end
     if Layout.Valid(full,whole) then return full end
    end
    if attempts>=4 then break end
   end
  end
 end
 M.progress=savedProgress
 return nil
end
function M.Maximize(crops,stock,tiles,slots,defs,seed,lower,upper,yieldfn,options)
 local progress={lower=lower,upper=upper,nodes=0,work=0};M.progress=progress
 if options and options.observe then options.observe(progress)end
 local Balance=require('aom_seed_balance')
 local Layout=require('aom_seed_layout')
 local patterns=options and options.patterns or Balance.Patterns(crops,stock,defs,yieldfn)
 local geometry=Layout.Geometry(tiles,slots,defs,yieldfn);geometry.balanced=true
 local K,N,T=#crops,#slots,#tiles
 local powers,single,all={}, {},0
 for c=0,K do powers[c]=2^c;single[2^c]=c;all=all+2^c end
 local function Has(mask,c)return mask%(powers[c]*2)>=powers[c] end
 local sizes,values={},{}
 local function Values(mask)
  if not values[mask] then
   local a={};for c=0,K do if Has(mask,c) then a[#a+1]=c end end
   values[mask]=a;sizes[mask]=#a
  end
  return values[mask]
 end
 local neighbors,conflicts={},{}
 local spacing=(GetFarmTillSpacing and GetFarmTillSpacing() or 1.25)^2
 for i,p in ipairs(slots) do
  conflicts[i]={}
  for _,j in ipairs(geometry.conflicts[i])do conflicts[i][#conflicts[i]+1]=j end
 end
 for c,k in ipairs(crops) do
  neighbors[c]={}
  for i=1,N do local a={};for _,q in ipairs(geometry.near[i]) do if Layout.InRange(geometry,i,q.j,(defs[k].family_check_dist or 4)^2) then a[#a+1]=q.j end end;neighbors[c][i]=a end
 end
 local caps={};for c,k in ipairs(crops) do caps[c]=stock[k] end
 local reachCache,commonCache,mapCache={}, {},{}
 local function NeighborMap(c,i)
  mapCache[c]=mapCache[c] or {}
  if not mapCache[c][i] then local a={};for _,j in ipairs(neighbors[c][i]) do a[j]=true end;mapCache[c][i]=a end
  return mapCache[c][i]
 end
 local function Reach(c,i)
  reachCache[c]=reachCache[c] or {}
  if not reachCache[c][i] then
   local a={};for _,j in ipairs(neighbors[c][i]) do for _,q in ipairs(neighbors[c][j]) do a[q]=true end end
   reachCache[c][i]=a
  end
  return reachCache[c][i]
 end
 local function Common(c,i,j)
  commonCache[c]=commonCache[c] or {};commonCache[c][i]=commonCache[c][i] or {}
  if not commonCache[c][i][j] then
   local a={};local map=NeighborMap(c,j)
   for _,q in ipairs(neighbors[c][i]) do if map[q] then a[#a+1]=q end end
   commonCache[c][i][j]=a
  end
  return commonCache[c][i][j]
 end
 local minimum={};for c,k in ipairs(crops) do minimum[c]=defs[k].family_min_count or 4 end
 local nodes,propagations,work=0,0,0
 local aborted=false
 local cooperative=false
 local function Step()
  if options and options.incumbent and work%128==0 then
   local candidate,n=options.incumbent();if candidate and n>lower then seed,lower=candidate,n;progress.lower=lower end
  end
  work=work+1;if options and options.work_limit and work>options.work_limit then aborted=true end;if work%128==0 then progress.nodes=nodes;progress.work=work;if cooperative then coroutine.yield() elseif yieldfn then yieldfn() end end
 end
 local function Copy(a)local b={};for i,v in ipairs(a) do b[i]=v end;return b end
 -- 带容量二分匹配与交替图强连通分量，排除多个同族争用同一批坑位的死路。
 local function Cardinality(domains,target)
  local required={[0]=N-target};local sum=N-target
  for c=1,K do required[c]=caps[c];sum=sum+caps[c] end
  local owners,match={},{};for c=0,K do owners[c]={} end
  local order={};for i=1,N do order[i]=i;Values(domains[i]) end
  table.sort(order,function(a,b)return sizes[domains[a]]~=sizes[domains[b]] and sizes[domains[a]]<sizes[domains[b]] or sizes[domains[a]]==sizes[domains[b]] and a<b end)
  local function Assign(i,seen)
   for _,c in ipairs(Values(domains[i])) do if not seen[c] then
    seen[c]=true
    if #owners[c]<required[c] then owners[c][#owners[c]+1]=i;match[i]=c;return true end
    for at,j in ipairs(owners[c]) do if Assign(j,seen) then owners[c][at]=i;match[i]=c;return true end end
   end end
   return false
  end
  for _,i in ipairs(order) do if not Assign(i,{}) then return false,false end end
  local extra=sum~=N and 1 or 0
  local adj={};for i=1,N+K+1+extra do adj[i]={} end
  for i,mask in ipairs(domains) do for _,c in ipairs(Values(mask)) do
   if match[i]~=c then adj[i][#adj[i]+1]=N+c+1 end
  end end
  for c=0,K do for _,i in ipairs(owners[c]) do adj[N+c+1][#adj[N+c+1]+1]=i end end
  if extra==1 then
   local residual=N+K+2
   for c=0,K do if #owners[c]<required[c] then adj[N+c+1][#adj[N+c+1]+1]=residual end end
   for i=1,N do adj[residual][#adj[residual]+1]=i end
  end
  local index,low,onstack,stack,component={}, {}, {}, {},{}
  local serial,components=0,0
  local function Visit(i)
   serial=serial+1;index[i],low[i]=serial,serial;stack[#stack+1]=i;onstack[i]=true
   for _,j in ipairs(adj[i]) do
    if not index[j] then Visit(j);low[i]=math.min(low[i],low[j])
    elseif onstack[j] then low[i]=math.min(low[i],index[j]) end
   end
   if low[i]==index[i] then
    components=components+1
    repeat local j=table.remove(stack);onstack[j]=nil;component[j]=components until j==i
   end
  end
  for i=1,N+K+1+extra do if not index[i] then Visit(i) end end
  local changed=false
  for i,mask in ipairs(domains) do
   for _,c in ipairs(Values(mask)) do if match[i]~=c and component[i]~=component[N+c+1] then domains[i]=domains[i]-powers[c];changed=true end end
   if domains[i]==0 then return false,false end
  end
  return true,changed
 end
 local profileGroups,groupKeys={},{}
 for c,k in ipairs(crops) do
  local key=table.concat(Balance.Vector(defs[k]),',')..':'..minimum[c]..':'..(defs[k].family_check_dist or 4)
  if not groupKeys[key] then groupKeys[key]=#profileGroups+1;profileGroups[#profileGroups+1]={} end
  local group=profileGroups[groupKeys[key]];group[#group+1]=c
 end
 local activeProfiles=nil
 local profileData,matchCache,matchOrder={}, {},{}
 local matchHead,matchTail=1,0
 local function ProfileBounds(lo,hi)
  if not activeProfiles or #activeProfiles>2000 then return lo,hi end
  local outlo,outhi={},{};for c=1,K do outlo[c]=math.huge;outhi[c]=-1 end
  local ranges={}
  for g,group in ipairs(profileGroups) do local tokens={g};for _,c in ipairs(group) do tokens[#tokens+1]=lo[c];tokens[#tokens+1]=hi[c] end;ranges[g]=table.concat(tokens,',') end
  local any=false
  for _,profile in ipairs(activeProfiles) do
   local data=profileData[profile]
   if not data then
    data={};profileData[profile]=data
    for g,group in ipairs(profileGroups) do local values={};for _,c in ipairs(group) do values[#values+1]=profile[c] end;table.sort(values);data[g]={values=values,key=table.concat(values,',')} end
   end
   local results={};local feasible=true
   for g,group in ipairs(profileGroups) do
    local key=ranges[g]..'/'..data[g].key;local result=matchCache[key]
    if result==nil then
     local values=data[g].values;local taken,assignment={},{}
     local lower,upper={},{};for _,c in ipairs(group) do lower[c]=math.huge;upper[c]=-1 end
     local found=false
     local function Match(at)
      if at>#group then found=true;for _,c in ipairs(group) do lower[c]=math.min(lower[c],assignment[c]);upper[c]=math.max(upper[c],assignment[c]) end;return end
      local c=group[at];local seen={}
      for i,n in ipairs(values) do if not taken[i] and not seen[n] and n>=lo[c] and n<=hi[c] then
       seen[n]=true;taken[i]=true;assignment[c]=n;Match(at+1);taken[i]=nil
      end end
     end
     Match(1);result=found and {lo=lower,hi=upper} or false
     matchCache[key]=result;matchTail=matchTail+1;matchOrder[matchTail]=key
     if matchTail-matchHead>20000 then matchCache[matchOrder[matchHead]]=nil;matchOrder[matchHead]=nil;matchHead=matchHead+1 end
    end
    if not result then feasible=false;break end;results[g]=result
   end
   if feasible then
    any=true
    for g,group in ipairs(profileGroups) do for _,c in ipairs(group) do outlo[c]=math.min(outlo[c],results[g].lo[c]);outhi[c]=math.max(outhi[c],results[g].hi[c]) end end
   end
  end
  if not any then return nil end
  return outlo,outhi
 end
 local boundsCache=setmetatable({},{__mode="k"})
 local function Propagate(domains,lists,target)
  local changed=true;local limits,lowerlimits={},{};for c,k in ipairs(crops) do limits[c]=caps[c];lowerlimits[c]=0 end
  while changed do
   if aborted then return false end
   changed=false;propagations=propagations+1;Step()
   local function Set(i,mask)
    if mask==0 then return false end
    if mask~=domains[i] then domains[i]=mask;changed=true end
    return true
   end
   local counts,possible={},{}
   for c=0,K do counts[c]=0;possible[c]=0 end
   for i,mask in ipairs(domains) do
    if mask==0 then return false end
    local c=single[mask];if c then counts[c]=counts[c]+1 end
    for _,v in ipairs(Values(mask)) do possible[v]=possible[v]+1 end
    if c and c>0 then for _,j in ipairs(conflicts[i]) do if not Set(j,Has(domains[j],0) and 1 or 0) then return false end end end
   end
   local stocklimit={[0]=N-target}
   for c,k in ipairs(crops) do stocklimit[c]=caps[c] end
   for c=0,K do
    if counts[c]>stocklimit[c] then return false end
    if c==0 and possible[c]<stocklimit[c] then return false end
    if c>0 and counts[c]>0 and possible[c]<minimum[c] then return false end
    local exclude=counts[c]==stocklimit[c] or c>0 and possible[c]<minimum[c]
    local force=c==0 and possible[c]==stocklimit[c]
    for i,mask in ipairs(domains) do if Has(mask,c) and single[mask]==nil then
     if exclude then if not Set(i,mask-powers[c]) then return false end
     elseif force then if not Set(i,powers[c]) then return false end end
    end end
   end
   local tilemin,tilemax,totalmin={}, {},{}
   for c=1,K do totalmin[c]=0 end
   for t=1,T do
    local bounds=boundsCache[lists[t]]
    if not bounds then
     local lo,hi={},{};for c=1,K do lo[c]=9;hi[c]=0 end
     for _,pattern in ipairs(lists[t])do for c=1,K do lo[c]=math.min(lo[c],pattern.counts[c]);hi[c]=math.max(hi[c],pattern.counts[c])end end
     bounds={lo,hi};boundsCache[lists[t]]=bounds
    end
    tilemin[t],tilemax[t]=bounds[1],bounds[2]
    for c=1,K do totalmin[c]=totalmin[c]+tilemin[t][c]end
   end
   -- 原版同族条件是“每株至少三个邻居”，允许五株以上非团状支持。
   for c=1,K do
    for i,mask in ipairs(domains) do if Has(mask,c) then
     local support,n={},0
     for _,j in ipairs(neighbors[c][i]) do if Has(domains[j],c) then n=n+1;support[n]=j end end
     local bytile={}
     for _,j in ipairs(support)do local t=math.floor((j-1)/9)+1;bytile[t]=(bytile[t]or 0)+1 end
     local supportmax,outside=0,totalmin[c];local capacity={}
     for t,n in pairs(bytile)do capacity[t]=math.min(n,tilemax[t][c]);supportmax=supportmax+capacity[t];outside=outside-math.min(tilemin[t][c],n)end
     local sumcapacity=supportmax
     supportmax=math.min(supportmax,limits[c]-outside)
     if supportmax<minimum[c] then if not Set(i,domains[i]-powers[c]) then return false end
     elseif single[domains[i]]==c then
      if n==minimum[c] then for _,j in ipairs(support) do if not Set(j,powers[c]) then return false end end end
      -- 半径内某格的可用坑位恰好全部必需时，直接强制这些支持点。
      for _,j in ipairs(support) do local t=math.floor((j-1)/9)+1
       if bytile[t]>0 and minimum[c]-(sumcapacity-capacity[t])==bytile[t] then if not Set(j,powers[c]) then return false end end
      end
      -- 不超过2m-1株且每株至少m个同族时，每对株必有至少2m-n个公共支持。
      if limits[c]<=2*minimum[c]-1 then
       local reachable=Reach(c,i);local required=2*minimum[c]-limits[c]
       for j,other in ipairs(domains) do if Has(other,c) then
        if not reachable[j] then if not Set(j,other-powers[c]) then return false end
        else
         local common={};for _,q in ipairs(Common(c,i,j)) do if Has(domains[q],c) then common[#common+1]=q end end
         if #common<required then if not Set(j,domains[j]-powers[c]) then return false end
         elseif single[domains[j]]==c and #common==required then for _,q in ipairs(common) do if not Set(q,powers[c]) then return false end end end
        end
       end end
      end
      -- 库存恰好四颗时，四株必成团；推广到库存较多时的“半径外配额”。
      local outside=0;local inside={};for _,j in ipairs(neighbors[c][i]) do inside[j]=true end
      for j,other in ipairs(domains) do if not inside[j] and single[other]==c then outside=outside+1 end end
      local limit=limits[c]-minimum[c]
      if outside>limit then return false end
      if outside==limit then for j,other in ipairs(domains) do if not inside[j] and Has(other,c) and single[other]==nil then if not Set(j,other-powers[c]) then return false end end end end
     end
    end end
    Step()
   end
   local mins,maxs={},{};local summin,summax=0,0
   for t=1,T do
    local fixed,available={},{}
    for c=0,K do fixed[c]=0;available[c]=0 end
    for i=(t-1)*9+1,t*9 do local mask=domains[i];local c=single[mask]
     if c then fixed[c]=fixed[c]+1 end
     for _,v in ipairs(Values(mask)) do available[v]=available[v]+1 end
    end
    local allowed={};local lo,hi=9,0
    for _,p in ipairs(lists[t]) do
     local ok=9-p.n>=fixed[0] and 9-p.n<=available[0]
     if ok then for c=1,K do if p.counts[c]<fixed[c] or p.counts[c]>available[c] then ok=false;break end end end
     if ok then allowed[#allowed+1]=p;lo=math.min(lo,p.n);hi=math.max(hi,p.n) end
     Step()
    end
    if #allowed==0 then return false end
    if #allowed~=#lists[t]then lists[t]=allowed end;mins[t],maxs[t]=lo,hi;summin=summin+lo;summax=summax+hi
   end
   if target<summin or target>summax then return false end
   local globalmin,globalmax={},{};for c=1,K do globalmin[c]=0;globalmax[c]=0 end
   for t=1,T do
    local lo=target-(summax-maxs[t]);local hi=target-(summin-mins[t])
    local allowed={};local mincount,maxcount={},{}
    for c=0,K do mincount[c]=9;maxcount[c]=0 end
    for _,p in ipairs(lists[t]) do if p.n>=lo and p.n<=hi then
     allowed[#allowed+1]=p
     for c=0,K do local n=c==0 and 9-p.n or p.counts[c];mincount[c]=math.min(mincount[c],n);maxcount[c]=math.max(maxcount[c],n) end
    end end
    if #allowed==0 then return false end;if #allowed~=#lists[t]then lists[t]=allowed end
    for c=1,K do globalmin[c]=globalmin[c]+mincount[c];globalmax[c]=globalmax[c]+maxcount[c] end
    for c=0,K do
     local fixed,available=0,0
     for i=(t-1)*9+1,t*9 do if single[domains[i]]==c then fixed=fixed+1 end;if Has(domains[i],c) then available=available+1 end end
     if fixed>maxcount[c] or available<mincount[c] then return false end
     if fixed==maxcount[c] then
      for i=(t-1)*9+1,t*9 do local mask=domains[i];if Has(mask,c) and single[mask]==nil and not Set(i,mask-powers[c]) then return false end end
     elseif available==mincount[c] then
      for i=(t-1)*9+1,t*9 do if Has(domains[i],c) and not Set(i,powers[c]) then return false end end
     end
    end
   end
   local totalmax,totalmin=0,0
   for c=1,K do
    globalmax[c]=math.min(globalmax[c],limits[c])
    globalmin[c]=math.max(globalmin[c],lowerlimits[c])
    if globalmax[c]<minimum[c] then globalmax[c]=0 end
    if globalmin[c]>0 then globalmin[c]=math.max(globalmin[c],minimum[c]) end
    if globalmin[c]>globalmax[c] then return false end
    totalmax=totalmax+globalmax[c];totalmin=totalmin+globalmin[c]
   end
   if totalmax<target or totalmin>target then return false end
   if activeProfiles then
    local lo,hi=ProfileBounds(globalmin,globalmax);if not lo then return false end
    totalmin,totalmax=0,0
    for c=1,K do
     if lo[c]>lowerlimits[c] then lowerlimits[c]=lo[c];changed=true end
     globalmin[c],globalmax[c]=lo[c],hi[c]
     totalmin,totalmax=totalmin+lo[c],totalmax+hi[c]
    end
   end
   for c=1,K do
    local lo=math.max(globalmin[c],target-(totalmax-globalmax[c]))
    if lo>0 then lo=math.max(lo,minimum[c]) end
    local hi=math.min(globalmax[c],target-(totalmin-globalmin[c]))
    if hi<minimum[c] then hi=0 end
    if lo>hi then return false end
    if hi<limits[c] then limits[c]=hi;changed=true end
    local fixed,available=0,0
    for _,mask in ipairs(domains) do if single[mask]==c then fixed=fixed+1 end;if Has(mask,c) then available=available+1 end end
    if fixed>hi or available<lo then return false end
    if fixed==hi then
     for i,mask in ipairs(domains) do if single[mask]==nil and Has(mask,c) and not Set(i,mask-powers[c]) then return false end end
    elseif available==lo then
     for i,mask in ipairs(domains) do if Has(mask,c) and not Set(i,powers[c]) then return false end end
    end
   end
   if not changed then
    local feasible,narrowed=Cardinality(domains,target)
    if not feasible then return false end
    changed=narrowed
   end
  end
  return true
 end
 local signatures={}
 for c,k in ipairs(crops) do signatures[c]=table.concat(Balance.Vector(defs[k]),',')..':'..minimum[c]..':'..(defs[k].family_check_dist or 4)..':'..stock[k] end
 -- 将搜索顺序按田形规范化；只改变分支顺序，所有距离仍取现场原始坐标。
 local canonical,canonicalKey=0,nil
 local function Transform(x,z,r)
  if r>=4 then x=-x end
  for _=1,r%4 do x,z=-z,x end
  return x,z
 end
 for r=0,7 do
  local pts={};local minx,minz,maxx,maxz=math.huge,math.huge,-math.huge,-math.huge
  for _,t in ipairs(tiles) do local x,z=Transform(t.x/4,t.z/4,r);pts[#pts+1]={x,z};minx=math.min(minx,x);minz=math.min(minz,z);maxx=math.max(maxx,x);maxz=math.max(maxz,z) end
  table.sort(pts,function(a,b)return a[2]~=b[2] and a[2]<b[2] or a[2]==b[2] and a[1]<b[1] end)
  local tokens={string.format('%04d:%04d',1000-(maxx-minx),maxz-minz)}
  for _,t in ipairs(pts) do tokens[#tokens+1]=(t[1]-minx)..','..(t[2]-minz) end
  local key=table.concat(tokens,';');if not canonicalKey or key<canonicalKey then canonical,canonicalKey=r,key end
 end
 local rankCache={}
 local function Ranks(direction)
  direction=direction or 0
  if rankCache[direction] then return rankCache[direction] end
  local ordered,rank={},{};for i=1,N do ordered[i]=i end
  if direction>=4 then for i=1,N do rank[i]=direction==4 and i or N+1-i end;rankCache[direction]=rank;return rank end
  local function Position(i)
   local x,z=Transform(slots[i].x,slots[i].z,canonical)
   for _=1,direction do x,z=-z,x end
   return x,z
  end
  table.sort(ordered,function(a,b)local x,z=Position(a);local u,v=Position(b);return z~=v and z<v or z==v and x<u end)
  for at,i in ipairs(ordered) do rank[i]=at end
  rankCache[direction]=rank;return rank
 end
 -- 逐格候选的库存总和约束。缓存只依赖计数集合，不包含搜索顺序或启发式结果。
 local quotaCache,quotaOrder={},{};local quotaHead,quotaTail=1,0
 local countPowers={};for n=0,9 do countPowers[n]=2^n end
 local function CountHas(mask,n)return mask%(countPowers[n]*2)>=countPowers[n] end
 local spatialQuotaCache={}
 local function SpatialQuota(counts,total,c)
  local key=(defs[crops[c]].family_check_dist or 4)..':'..table.concat(counts,',')
  if spatialQuotaCache[key]~=nil then return spatialQuotaCache[key] end
  local active={};for i=1,N do active[i]=counts[math.floor((i-1)/9)+1]>0 end
  local changed=true
  while changed do
   changed=false
   for i=1,N do if active[i] then
    local support={};for t=1,T do support[t]=0 end
    for _,j in ipairs(neighbors[c][i]) do if active[j] then local t=math.floor((j-1)/9)+1;support[t]=support[t]+1 end end
    local maximum=0;for t=1,T do maximum=maximum+math.min(counts[t],support[t]) end
    local ok=maximum>=4
    if ok then
     local compatible={};for t=1,T do compatible[t]=0 end
     local linked=NeighborMap(c,i)
     for j=1,N do if active[j] and (total>4 or linked[j]) then
      local common={};for t=1,T do common[t]=0 end
      for _,q in ipairs(Common(c,i,j)) do if active[q] then local t=math.floor((q-1)/9)+1;common[t]=common[t]+1 end end
      local maximum=0;for t=1,T do maximum=maximum+math.min(counts[t],common[t]) end
      if maximum>=8-total then local t=math.floor((j-1)/9)+1;compatible[t]=compatible[t]+1 end
     end end
     for t=1,T do if compatible[t]<counts[t] then ok=false;break end end
    end
    if not ok then active[i]=false;changed=true end
   end end
   local available={};for t=1,T do available[t]=0 end
   for i=1,N do if active[i] then local t=math.floor((i-1)/9)+1;available[t]=available[t]+1 end end
   for t=1,T do if available[t]<counts[t] then spatialQuotaCache[key]=false;return false end end
   Step()
  end
  spatialQuotaCache[key]=true;return true
 end
 local function Quotas(masks,total,c)
  local key=(defs[crops[c]].family_check_dist or 4)..':'..total..':'..table.concat(masks,',');local cached=quotaCache[key]
  if cached~=nil then return cached end
  local choices,prefix,suffix={}, {[0]={[0]=true}}, {[T+1]={[0]=true}}
  for t,mask in ipairs(masks) do
   choices[t]={};for n=0,math.min(9,total) do if CountHas(mask,n) then choices[t][#choices[t]+1]=n end end
   local sums={};for n in pairs(prefix[t-1]) do for _,v in ipairs(choices[t]) do if n+v<=total then sums[n+v]=true end end end;prefix[t]=sums
  end
  local result=false
  if prefix[T][total] then
   for t=T,1,-1 do local sums={};for n in pairs(suffix[t+1]) do for _,v in ipairs(choices[t]) do if n+v<=total then sums[n+v]=true end end end;suffix[t]=sums end
   result={}
   for t=1,T do
    local mask=0
    for _,v in ipairs(choices[t]) do for n in pairs(prefix[t-1]) do if suffix[t+1][total-v-n] then mask=mask+countPowers[v];break end end end
    result[t]=mask
   end
  end
  -- 小份同族的逐格配额还必须具有空间支持。这里只用必要条件剪枝，
  -- 与实际坑位竞争无关；枚举预算耗尽时保留原计数支持，不作无解判断。
  if result and T<=9 then
   local supported={};for t=1,T do supported[t]=0 end
   local counts,visits,limited={},0,false
   local found=false
   local function Enumerate(t,left)
    visits=visits+1;if visits>12000 then limited=true;return end
    if t>T then
     if left==0 and SpatialQuota(counts,total,c) then
      found=true;for q,n in ipairs(counts) do if not CountHas(supported[q],n) then supported[q]=supported[q]+countPowers[n] end end
     end
     return
    end
    for _,n in ipairs(choices[t]) do if n<=left and suffix[t+1][left-n] then
     counts[t]=n;Enumerate(t+1,left-n);if limited then return end
    end end
   end
   Enumerate(1,total)
   if not limited then result=found and supported or false end
  end
  quotaCache[key]=result;quotaTail=quotaTail+1;quotaOrder[quotaTail]=key
  if quotaTail-quotaHead>20000 then quotaCache[quotaOrder[quotaHead]]=nil;quotaOrder[quotaHead]=nil;quotaHead=quotaHead+1 end
  return result
 end
 -- 只记忆完整排除的剩余状态；截断状态不能当成不可行证据。
 local failedCover,failedOrder={},{};local failedHead,failedTail=1,0
 local patternIDs={};for i,p in ipairs(patterns) do patternIDs[p]=i end
 local listKeys=setmetatable({},{__mode='k'})
 local function ListKey(list)
  if not listKeys[list] then local a={};for _,p in ipairs(list) do a[#a+1]=patternIDs[p] or 0 end;listKeys[list]=table.concat(a,',') end
  return listKeys[list]
 end
 local function Cover(allocation,target,nodeLimit,direction)
  for _,list in ipairs(conflicts) do if #list>0 then return nil,false,false end end
  local radius,minimumFamily=nil,nil
  for c,k in ipairs(crops) do if allocation[c]>0 then
   if allocation[c]>7 then return nil,false,false end
   if radius and radius~=(defs[k].family_check_dist or 4) then return nil,false,false end
   radius=defs[k].family_check_dist or 4
   if (defs[k].family_min_count or 4)~=4 then return nil,false,false end
   minimumFamily=c
  end end
  if not minimumFamily then return nil,false,false end
  local adjacent,linked={},{}
  for i=1,N do adjacent[i]=neighbors[minimumFamily][i];linked[i]={};for _,j in ipairs(adjacent[i]) do linked[i][j]=true end end
  local rank=Ranks(direction)
  local classof,classkeys,classes={}, {},0
  for c,k in ipairs(crops) do
   local key=table.concat(Balance.Vector(defs[k]),',')
   if not classkeys[key] then classes=classes+1;classkeys[key]=classes end
   classof[c]=classkeys[key]
  end
  local totals={};for g=1,classes do totals[g]=0 end
  for c,n in ipairs(allocation) do totals[classof[c]]=totals[classof[c]]+n end
  local projection={}
  for _,p in ipairs(patterns) do
   local counts={};for g=1,classes do counts[g]=0 end
   for c,n in ipairs(p.counts) do counts[classof[c]]=counts[classof[c]]+n end
   projection[p]=counts
  end
  local holes=N-target;local initialLists={}
  for t=1,T do
   local list={}
   for _,p in ipairs(patterns) do
    local ok=p.n>=9-holes
    for c=1,K do if p.counts[c]>allocation[c] then ok=false;break end end
    if ok then list[#list+1]=p end
   end
   if holes>=9 then local p={n=0,counts={}};for c=1,K do p.counts[c]=0 end;projection[p]={};for g=1,classes do projection[p][g]=0 end;list[#list+1]=p end
   if #list==0 then return nil,false,true end;initialLists[t]=list
  end
  local cut=false;local visits=0
  local function CheckBudget()
   visits=visits+1;Step()
   if aborted then return false end
   if nodeLimit and visits>nodeLimit*32 then cut=true;return false end
   return true
  end
  local function Refine(lists,free,board,c,counts)
   local out={};local totalmin,totalmax=0,0
   for t,list in ipairs(lists) do
    local capacity=0;for i=(t-1)*9+1,t*9 do if free[i] or board[i] then capacity=capacity+1 end end
    local allowed={};local lo,hi=9,0
    for _,p in ipairs(list) do
     if p.n<=capacity and (not c or p.counts[c]==counts[t]) then
      allowed[#allowed+1]=p;lo=math.min(lo,p.n);hi=math.max(hi,p.n)
     end
    end
    if #allowed==0 then return nil end
    out[t]=allowed;totalmin=totalmin+lo;totalmax=totalmax+hi
   end
   if target<totalmin or target>totalmax then return nil end
   local changed=true
   while changed do
    changed=false
    local mins,maxs,summin,summax={}, {}, {},{}
    for g=1,classes do summin[g]=0;summax[g]=0 end
    for t,list in ipairs(out) do
     mins[t],maxs[t]={},{}
     for g=1,classes do mins[t][g]=N;maxs[t][g]=0 end
     for _,p in ipairs(list) do for g,n in ipairs(projection[p]) do mins[t][g]=math.min(mins[t][g],n);maxs[t][g]=math.max(maxs[t][g],n) end end
     for g=1,classes do summin[g]=summin[g]+mins[t][g];summax[g]=summax[g]+maxs[t][g] end
    end
    for g=1,classes do if totals[g]<summin[g] or totals[g]>summax[g] then return nil end end
    for t,list in ipairs(out) do
     local kept={}
     for _,p in ipairs(list) do
      local ok=true
      for g,n in ipairs(projection[p]) do if n<totals[g]-(summax[g]-maxs[t][g]) or n>totals[g]-(summin[g]-mins[t][g]) then ok=false;break end end
      if ok then kept[#kept+1]=p else changed=true end
     end
     if #kept==0 then return nil end;out[t]=kept
     Step()
    end
    -- 除了养分类总量，每一种作物的跨地皮计数也必须恰好用满本分支的配额。
    -- 精确子集和支持可排除“区间包含配额、实际计数却凑不出配额”的组合。
    for c,total in ipairs(allocation) do if total>0 then
     local masks={}
     for t,list in ipairs(out) do local mask=0;local seen={};for _,p in ipairs(list) do local n=p.counts[c];if not seen[n] then seen[n]=true;mask=mask+countPowers[n] end end;masks[t]=mask end
     local supported=Quotas(masks,total,minimumFamily);if not supported then return nil end
     for t,list in ipairs(out) do if supported[t]~=masks[t] then
      local kept={};for _,p in ipairs(list) do if CountHas(supported[t],p.counts[c]) then kept[#kept+1]=p end end
      if #kept==0 then return nil end;out[t]=kept;changed=true
     end end
     Step()
    end end
   end
   return out
  end
  local Search
  local function Explore(free,board,lists,remaining,left,blank)
   nodes=nodes+1
   if not CheckBudget() then return nil end
   if left==0 then if Layout.Valid(board,geometry) then return board end;return nil end
   lists=Refine(lists,free,board);if not lists then return nil end
   local coarseTile,coarseGroups,coarseSize=nil,nil,math.huge
   for t,list in ipairs(lists) do
    local groups,keys={},{}
    for _,p in ipairs(list) do
     local key=table.concat(projection[p],',')
     if not groups[key] then groups[key]={};keys[#keys+1]=key end
     groups[key][#groups[key]+1]=p
    end
    if #keys>1 and #keys<=32 and #keys<coarseSize then
     coarseTile,coarseGroups,coarseSize=t,{},#keys
     for _,key in ipairs(keys) do coarseGroups[#coarseGroups+1]=groups[key] end
    end
   end
   if coarseTile then
    local function Score(group)
     local score=0
     for _,n in ipairs(projection[group[1]]) do if n>0 and n<4 then score=score+(4-n)^2 end end
     return score
    end
    table.sort(coarseGroups,function(a,b)return Score(a)<Score(b) end)
    for _,group in ipairs(coarseGroups) do
     local nextlists=Copy(lists);nextlists[coarseTile]=group
     local result=Search(free,board,nextlists,remaining,left,blank)
     if result then return result end
     if cut or aborted then return nil end
    end
    return nil
   end
   local component,regions,degrees={}, {},{}
   for i,v in ipairs(free) do if v and not component[i] then
    local id=#regions+1;local region={points={i},tiles={}};regions[id]=region;component[i]=id
    local at=1
    while at<=#region.points do
     local point=region.points[at];at=at+1
     local t=math.floor((point-1)/9)+1;region.tiles[t]=(region.tiles[t] or 0)+1
     local degree=0
     for _,j in ipairs(adjacent[point]) do if free[j] then
      degree=degree+1
      if not component[j] then component[j]=id;region.points[#region.points+1]=j end
     end end
     degrees[point]=degree
    end
   end end
   if #regions>1 then
    local sums={[0]=true};local total=0
    for _,n in ipairs(remaining) do if n>0 then for q=total,0,-1 do if sums[q] then sums[q+n]=true end end;total=total+n end end
    local empty=0
    for _,region in ipairs(regions) do
     local filled=math.min(#region.points,total);while filled>0 and not sums[filled] do filled=filled-1 end
     empty=empty+#region.points-filled
    end
    if empty>blank then return nil end
   end
   local regionAllowed={}
   for c,n in ipairs(remaining) do if n>0 then
    regionAllowed[c]={};local possible=false
    for id,region in ipairs(regions) do if #region.points>=n then
     local capacity=0;local ok=true
     for t,list in ipairs(lists) do
      local lo,hi=9,0;for _,p in ipairs(list) do lo=math.min(lo,p.counts[c]);hi=math.max(hi,p.counts[c]) end
      local available=region.tiles[t] or 0
      if available<lo then ok=false;break end
      capacity=capacity+math.min(available,hi)
     end
     if ok and capacity>=n then regionAllowed[c][id]=true;possible=true end
    end end
    if not possible then return nil end
   end end
   local first,degree=nil,math.huge
   for i,v in ipairs(free) do if v then
    local n=degrees[i];if n<degree or n==degree and rank[i]<rank[first] then first,degree=i,n end
   end end
   if not first then return nil end
   local function Hole()
    if blank==0 then return nil end
    local nextfree=Copy(free);nextfree[first]=false
    local nextlists=Refine(lists,nextfree,board)
    if nextlists then return Search(nextfree,Copy(board),nextlists,remaining,left,blank-1) end
   end
   if degree<4 then return Hole() end
   local triedHole=false
   if seed and not seed[first] and blank>0 then
    triedHole=true;local candidate=Hole();if candidate then return candidate end
    if cut or aborted then return nil end
   end
   local kinds={};for c,n in ipairs(remaining) do if n>0 then kinds[#kinds+1]=c end end
   table.sort(kinds,function(a,b)
    local x,y=seed and seed[first]==crops[a] and 1 or 0,seed and seed[first]==crops[b] and 1 or 0
    if x~=y then return x>y end
    return remaining[a]~=remaining[b] and remaining[a]<remaining[b] or remaining[a]==remaining[b] and a<b
   end)
   local equivalent={}
   for _,c in ipairs(kinds) do
    if cut or aborted then return nil end
    local signature=table.concat(Balance.Vector(defs[crops[c]]),',')..':'..remaining[c]
    local quota={};local fixed=true
    for t,list in ipairs(lists) do
     local n=list[1].counts[c];quota[t]=n
     for _,p in ipairs(list) do if p.counts[c]~=n then fixed=false;break end end
    end
    -- 固定的逐格配额完全相同的未放置作物，可互换几何颜色；不合并同族数量。
    if fixed then signature='fixed:'..remaining[c]..':'..table.concat(quota,',') end
    if not equivalent[signature] and regionAllowed[c][component[first]] then
     equivalent[signature]=true
     local size=remaining[c];local lo,hi={},{}
     local required,capacity=0,0
     for t,list in ipairs(lists) do
      lo[t],hi[t]=9,0
      for _,p in ipairs(list) do lo[t]=math.min(lo[t],p.counts[c]);hi[t]=math.max(hi[t],p.counts[c]) end
      required=required+lo[t];capacity=capacity+hi[t]
     end
     if required<=size and capacity>=size and hi[math.floor((first-1)/9)+1]>0 then
      -- n<=7、每点度数至少3：任意两点必有公共邻居，因此完整候选都在锚点两跳内。
      local reachable={};for _,j in ipairs(adjacent[first]) do if free[j] then for _,q in ipairs(adjacent[j]) do if free[q] then reachable[q]=true end end end end
      local candidates={}
      for i in pairs(reachable) do if i~=first and hi[math.floor((i-1)/9)+1]>0 then candidates[#candidates+1]=i end end
      table.sort(candidates,function(a,b)
       local sa,sb=seed and seed[a]==crops[c] and 1 or 0,seed and seed[b]==crops[c] and 1 or 0
       if sa~=sb then return sa>sb end
       local pa,pb=slots[a],slots[b];local p=slots[first]
       local function Cost(q)
        local x,z=q.x-p.x,q.z-p.z;local axis=(direction or 0)%5
        local cross=axis==1 and x or axis==2 and z or axis==3 and x+z or axis==4 and x-z or 0
        return x*x+z*z+cross*cross*.8
       end
       local x,y=Cost(pa),Cost(pb)
       return x~=y and x<y or x==y and rank[a]<rank[b]
      end)
      local candidateIndex={};for at,i in ipairs(candidates) do candidateIndex[i]=at end
      local selected,selectedSet,support,residual,low={}, {}, {}, {},{}
      local count={};for t=1,T do count[t]=0 end
      for i,n in pairs(degrees) do residual[i]=n;if n<4 then low[i]=true end end
      local suffix={}
      local points=Copy(candidates);points[#points+1]=first
      for _,i in ipairs(points) do
       local a={};local n=0
       for at=#candidates,1,-1 do if linked[i][candidates[at]] then n=n+1 end;a[at]=n end
       suffix[i]=a
      end
      local function Push(i)
       local n=1
       for _,j in ipairs(selected) do if linked[i][j] then support[j]=support[j]+1;n=n+1 end end
       selected[#selected+1]=i;selectedSet[i]=true;support[i]=n
       local t=math.floor((i-1)/9)+1;count[t]=count[t]+1
       for _,j in ipairs(adjacent[i]) do if residual[j] then
        residual[j]=residual[j]-1
        if not selectedSet[j] and residual[j]<4 then low[j]=true else low[j]=nil end
       end end
      end
      local function Pop()
       local i=table.remove(selected);selectedSet[i]=nil;support[i]=nil
       for _,j in ipairs(selected) do if linked[i][j] then support[j]=support[j]-1 end end
       local t=math.floor((i-1)/9)+1;count[t]=count[t]-1
       for _,j in ipairs(adjacent[i]) do if residual[j] then
        residual[j]=residual[j]+1
        if not selectedSet[j] and residual[j]<4 then low[j]=true else low[j]=nil end
       end end
      end
      Push(first)
      local function Generate(at)
       if not CheckBudget() then return nil end
       local need=size-#selected
       if #candidates-at+1<need then return nil end
       local deficit=0;for t=1,T do if count[t]>hi[t] then return nil end;deficit=deficit+math.max(0,lo[t]-count[t]) end
       if deficit>need then return nil end
       -- 移走本组后，剩余种植点也必须各有至少三个同族候选邻居。
       -- 被孤立的点只能一并归入本组或成为空坑，提前剪掉无法覆盖的碎片。
       local forced,unavailable=0,0
       for i in pairs(low) do
        forced=forced+1
        if not candidateIndex[i] or candidateIndex[i]<at then unavailable=unavailable+1 end
       end
       if forced>need+blank or unavailable>blank then return nil end
       for _,i in ipairs(selected) do
        local n=support[i]
        if n+need<4 then return nil end
        if n+math.min(need,suffix[i][at] or 0)<4 then return nil end
       end
       if need==0 then
        local nextfree,nextboard=Copy(free),Copy(board)
        for _,i in ipairs(selected) do nextfree[i]=false;nextboard[i]=crops[c] end
        local nextlists=Refine(lists,nextfree,nextboard,c,count)
        if nextlists then
         local nextremaining=Copy(remaining);nextremaining[c]=0
         return Search(nextfree,nextboard,nextlists,nextremaining,left-1,blank)
        end
        return nil
       end
       for atindex=at,#candidates-need+1 do
        local i=candidates[atindex]
        Push(i)
        local result=Generate(atindex+1)
        Pop()
        if result then return result end
        if cut or aborted then return nil end
       end
       return nil
      end
      local result=Generate(1);if result then return result,false,true end
     end
    end
   end
   if cut or aborted or triedHole then return nil end
   return Hole()
  end
  Search=function(free,board,lists,remaining,left,blank)
   local cells={};for i=1,N do cells[i]=free[i] and 'f' or board[i] and 'p' or '.' end
   local tokens={table.concat(cells),table.concat(remaining,','),blank}
   for _,list in ipairs(lists) do tokens[#tokens+1]=ListKey(list) end
   local key=table.concat(tokens,';')
   if failedCover[key] then return nil end
   local result=Explore(free,board,lists,remaining,left,blank)
   if not result and not cut and not aborted then
    failedCover[key]=true;failedTail=failedTail+1;failedOrder[failedTail]=key
    if failedTail-failedHead>16000 then failedCover[failedOrder[failedHead]]=nil;failedOrder[failedHead]=nil;failedHead=failedHead+1 end
   end
   return result
  end
  local free,board={},{};for i=1,N do free[i]=true;board[i]=false end
  local left=0;for _,n in ipairs(allocation) do if n>0 then left=left+1 end end
  local result=Search(free,board,initialLists,Copy(allocation),left,holes)
  return result,cut,true
 end
 local preparedData
 local function Find(target,allocation,nodeLimit,direction,patternFirst,method)
  progress.target=target;progress.allocation=allocation and table.concat(allocation,',') or 'variable';progress.budget=nodeLimit;progress.direction=direction
  for c,k in ipairs(crops) do caps[c]=allocation and allocation[c] or stock[k] end
  local targetData=preparedData and preparedData.targets[target]
  activeProfiles=not allocation and targetData and not targetData.limited and targetData.allocations or nil
  if allocation and method~="patterns" and method~="hybrid" and (target~=N or method=="groups") then
   local board,cut,eligible=Cover(allocation,target,nodeLimit,direction)
   if eligible then return board,cut end
  end
  local rank=Ranks(direction)
  local initial,lists={},{}
  for i=1,N do initial[i]=target==N and all-1 or all end
  for t=1,T do
   local a={};for _,p in ipairs(patterns) do a[#a+1]=p end
   local zero={n=0,counts={}};for c=1,K do zero.counts[c]=0 end;a[#a+1]=zero;lists[t]=a
  end
  if method or patternFirst then
   local scores={}
   for _,p in ipairs(patterns) do local cost=0;for c,n in ipairs(p.counts) do if n>0 then cost=cost+n*math.max(0,minimum[c]-n)*100+1 end end;scores[p]=cost end
   for _,list in ipairs(lists) do table.sort(list,function(a,b)
    if a.n~=b.n then return a.n>b.n end
    local x,y=scores[a] or 0,scores[b] or 0
    return x~=y and x<y or x==y and (patternIDs[a] or 0)<(patternIDs[b] or 0)
   end) end
  end
  local visited,cut=0,false
  local function Search(domains,patternsbytile)
   nodes=nodes+1;visited=visited+1;Step()
   if nodeLimit and visited>nodeLimit then cut=true;return nil end
   if aborted or options and options.node_limit and nodes>options.node_limit then aborted=true;return nil end
   if not Propagate(domains,patternsbytile,target) then return nil end
   -- 少量逐格配比先分支；半径内同族上界会立即排除整片不可行配比，
   -- 无需把每个坑的颜色逐一试完才发现某端地皮只能容纳一两株同族。
   local patternTile,patternRank=nil,math.huge
   for t,list in ipairs(patternsbytile) do
    if #list>1 then
     local degree=0;for _,edge in ipairs(geometry.edges) do if edge.a==t or edge.b==t then degree=degree+1 end end
     local rank=#list*100+(method=="hybrid" and -degree or (direction or 0)%2==0 and degree or -degree)
     if rank<patternRank or rank==patternRank and Ranks(direction)[(t-1)*9+1]<Ranks(direction)[(patternTile-1)*9+1] then patternTile,patternRank=t,rank end
    end
   end
   local function ApplyPatterns()
    for _,pattern in ipairs(patternsbytile[patternTile]) do
     if aborted or cut then return nil end
     local child=Copy(patternsbytile);child[patternTile]={pattern}
     local candidate=Search(Copy(domains),child);if candidate then return candidate end
    end
    return nil
   end
   if (target==N or patternFirst or method=="patterns") and patternTile and (allocation or patternFirst) then return ApplyPatterns() end
   -- 配额已经固定时，少量同族作为完整组决定；大族仍允许多个分离支持团。
   -- 这避免在“大库存+少量余种”时把同一个小族拆成大量逐坑决定。
   local sumcaps=0;for _,n in ipairs(caps) do sumcaps=sumcaps+n end
   if sumcaps==target then
    local chosenCrop,choiceRank=nil,math.huge
    local assigned,possible={},{}
    for c=1,K do assigned[c]={};possible[c]={} end
    for i,mask in ipairs(domains) do
     for _,c in ipairs(Values(mask)) do if c>0 then possible[c][#possible[c]+1]=i end end
     local c=single[mask];if c and c>0 then assigned[c][#assigned[c]+1]=i end
    end
    for c,n in ipairs(caps) do
     if n>=4 and n<=7 and minimum[c]==4 and #assigned[c]<n then
      local score=(#possible[c]-#assigned[c])*10+(n-#assigned[c])
      if score<choiceRank then chosenCrop,choiceRank=c,score end
     end
    end
    if chosenCrop then
     local c=chosenCrop;local size=caps[c];local near,linked={},{}
     for i=1,N do linked[i]={};for _,j in ipairs(neighbors[c][i]) do linked[i][j]=true end end
     local anchors={}
     if #assigned[c]>0 then anchors[1]=assigned[c][1]
     else for _,i in ipairs(possible[c]) do anchors[#anchors+1]=i end;table.sort(anchors,function(a,b)return rank[a]<rank[b] end) end
     local fixedQuota,lo,hi={}, {},{}
     for t,list in ipairs(patternsbytile) do
      fixedQuota[t]={};lo[t],hi[t]=9,0
      for _,p in ipairs(list) do fixedQuota[t][p.counts[c]]=true;lo[t]=math.min(lo[t],p.counts[c]);hi[t]=math.max(hi[t],p.counts[c]) end
     end
     local generated=0
     for _,anchor in ipairs(anchors) do
      if aborted or cut then return nil end
      local reachable={}
      for _,j in ipairs(neighbors[c][anchor]) do if Has(domains[j],c) then
       for _,q in ipairs(neighbors[c][j]) do if Has(domains[q],c) then reachable[q]=true end end
      end end
      local selected,selectedSet,counts={}, {},{};for t=1,T do counts[t]=0 end
      local ok=true
      if #assigned[c]>0 then
       for _,i in ipairs(assigned[c]) do
        if not reachable[i] then ok=false;break end
        selected[#selected+1]=i;selectedSet[i]=true;local t=math.floor((i-1)/9)+1;counts[t]=counts[t]+1
       end
      else selected[1]=anchor;selectedSet[anchor]=true;counts[math.floor((anchor-1)/9)+1]=1 end
      if ok then
       local candidates={}
       for i in pairs(reachable) do if not selectedSet[i] and (#assigned[c]>0 or rank[i]>rank[anchor]) then candidates[#candidates+1]=i end end
       table.sort(candidates,function(a,b)
        local pa,pb,p=slots[a],slots[b],slots[anchor]
        local x,y=(pa.x-p.x)^2+(pa.z-p.z)^2,(pb.x-p.x)^2+(pb.z-p.z)^2
        return x~=y and x<y or x==y and rank[a]<rank[b]
       end)
       local suffix,tileSuffix={},{}
       local points=Copy(candidates);for _,i in ipairs(selected) do points[#points+1]=i end
       for _,i in ipairs(points) do
        local row={};local n=0;for at=#candidates,1,-1 do if linked[i][candidates[at]] then n=n+1 end;row[at]=n end;suffix[i]=row
       end
       for t=1,T do local row={};local n=0;for at=#candidates,1,-1 do if math.floor((candidates[at]-1)/9)+1==t then n=n+1 end;row[at]=n end;tileSuffix[t]=row end
       local function Generate(at)
        generated=generated+1;Step()
        if aborted then return nil end
        if nodeLimit and generated>nodeLimit*64 then cut=true;return nil end
        local need=size-#selected
        if #candidates-at+1<need then return nil end
        local deficit=0
        for t=1,T do
         if counts[t]>hi[t] or counts[t]+math.min(need,tileSuffix[t][at] or 0)<lo[t] then return nil end
         deficit=deficit+math.max(0,lo[t]-counts[t])
        end
        if deficit>need then return nil end
        for _,i in ipairs(selected) do
         local n=0;for _,j in ipairs(selected) do if linked[i][j] then n=n+1 end end
         if n+math.min(need,suffix[i][at] or 0)<4 then return nil end
        end
        if need==0 then
         for t=1,T do if not fixedQuota[t][counts[t]] then return nil end end
         local child=Copy(domains)
         for i,mask in ipairs(child) do
          if selectedSet[i] then child[i]=powers[c]
          elseif Has(mask,c) then child[i]=mask-powers[c];if child[i]==0 then return nil end end
         end
         return Search(child,Copy(patternsbytile))
        end
        for atindex=at,#candidates-need+1 do
         local i=candidates[atindex];local t=math.floor((i-1)/9)+1
         selected[#selected+1]=i;selectedSet[i]=true;counts[t]=counts[t]+1
         local result=Generate(atindex+1)
         counts[t]=counts[t]-1;selectedSet[i]=nil;selected[#selected]=nil
         if result then return result end
         if aborted or cut then return nil end
        end
        return nil
       end
       local result=Generate(1);if result then return result end
      end
     end
     return nil
    end
   end
   if patternTile and (allocation or patternFirst) then return ApplyPatterns() end
   local chosen,bestRank=nil,math.huge
   for i,mask in ipairs(domains) do if single[mask]==nil then
    Values(mask)
    local score=sizes[mask]*10000+#patternsbytile[math.floor((i-1)/9)+1]*10+#geometry.near[i]
    if score<bestRank or score==bestRank and rank[i]<rank[chosen] then chosen,bestRank=i,score end
   end end
   if not chosen then
    local board={};for i,mask in ipairs(domains) do local c=single[mask];board[i]=c>0 and crops[c] or false end
    if Layout.Valid(board,geometry) then return board end
    return nil
   end
   local options=Copy(Values(domains[chosen]));local used={}
   for c=1,K do used[c]=0 end
   for _,mask in ipairs(domains) do local c=single[mask];if c and c>0 then used[c]=used[c]+1 end end
   local function Cost(c)
    if c==0 then return -1000 end
    local n=0;for _,j in ipairs(neighbors[c][chosen]) do if single[domains[j]]==c then n=n+1 end end
    return n*100+(seed and seed[chosen]==crops[c] and 30 or 0)+(caps[c]-used[c])
   end
   table.sort(options,function(a,b)local x,y=Cost(a),Cost(b);return x~=y and x>y or x==y and a<b end)
   local tried={}
   for _,c in ipairs(options) do
    if aborted or cut then return nil end
    local equivalent=false
    if c>0 and used[c]==0 then for _,previous in ipairs(tried) do if previous>0 and used[previous]==0 and signatures[c]==signatures[previous] and caps[c]==caps[previous] then
     equivalent=true;for _,mask in ipairs(domains) do if Has(mask,c)~=Has(mask,previous) then equivalent=false;break end end
     if equivalent then break end
    end end end
    if not equivalent then
     tried[#tried+1]=c
     local child=Copy(domains);child[chosen]=powers[c]
     local candidate=Search(child,Copy(patternsbytile));if candidate then return candidate end
    end
   end
   return nil
  end
  local board=Search(initial,lists)
  return board,cut
 end
 local initialupper=upper
 if lower==upper then return seed,{total=lower,upper=lower,relaxed_upper=upper,optimal=true,nodes=0,propagations=0,mode='upper-bound-witness'} end
 local vectors={};for c,k in ipairs(crops) do vectors[c]=Balance.Vector(defs[k]) end
 preparedData=options and options.prepared or M.Prepare(crops,stock,defs,vectors,upper,yieldfn)
 local allocations,globalupper,limited=preparedData.allocations,preparedData.upper,preparedData.limited
 if not limited then upper=math.min(upper,globalupper) end
 for target=upper,lower+1,-1 do
  if options and options.incumbent then
   local candidate,n=options.incumbent()
   if candidate and n>lower then seed,lower=candidate,n end
   if target<=lower then return seed,{total=lower,upper=lower,optimal=true,nodes=nodes,propagations=propagations,mode='shared-incumbent-proof'}end
  end
  local entry=preparedData.Get(target);limited=entry.limited
  progress.preparation_limited=limited;progress.total_profiles=#entry.allocations
  if limited or #entry.allocations>0 then
   -- 不先锁定库存配额的有界探测，补足配额优先搜索不擅长的布局。
   -- 未完成的探测不提供不可行证明；任意完整失败则覆盖整个目标数量。
   local direct,exhausted=nil,false
   for _,budget in ipairs({32}) do
    for _,direction in ipairs({0,3}) do
     for strategy=0,1 do
      local cut;direct,cut=Find(target,nil,budget,direction,strategy==1)
      if direct or aborted or not cut then exhausted=not cut and not direct;break end
     end
     if direct or aborted or exhausted then break end
    end
    if direct or aborted or exhausted then break end
   end
   if direct then return direct,{total=target,upper=target,relaxed_upper=initialupper,optimal=true,nodes=nodes,propagations=propagations,mode='exact-variable-witness'} end
   if aborted then return seed,{total=lower,upper=initialupper,optimal=false,pending=true,nodes=nodes,propagations=propagations,prepared=preparedData} end
   if not exhausted then
   local tasks={}
   local function AddTask(allocation,profile,direction,method)
    tasks[#tasks+1]={allocation=allocation,profile=profile,direction=direction,method=method,quantum=32,
     thread=coroutine.create(function()return Find(target,allocation,nil,direction,nil,method)end)}
   end
   for ai,allocation in ipairs(entry.allocations) do
    if target==N then AddTask(allocation,ai,0,'patterns');AddTask(allocation,ai,3,'groups')
    else AddTask(allocation,ai,0,'groups');AddTask(allocation,ai,3,'patterns') end
    local large=false;for _,n in ipairs(allocation) do if n>7 then large=true;break end end
    if large then AddTask(allocation,ai,2,'hybrid') end
   end
   if limited then AddTask(nil,0,0,'patterns') end
   local at=1;cooperative=true
   while #tasks>0 do
    if aborted then break end
    if at>#tasks then at=1 end
    local task=tasks[at]
    -- caps/activeProfiles是传播器共享的上下文，每次恢复搜索前重建当前配额。
    for c,k in ipairs(crops) do caps[c]=task.allocation and task.allocation[c] or stock[k] end
    activeProfiles=not task.allocation and not entry.limited and entry.allocations or nil
    progress.target=target;progress.profiles=#tasks;progress.profile=task.profile;progress.direction=task.direction;progress.method=task.method;progress.allocation=task.allocation and table.concat(task.allocation,',') or 'variable'
    task.started_nodes=task.started_nodes or nodes;task.started_work=task.started_work or work
    local ok,board=coroutine.resume(task.thread)
    if not ok then error(board,0) end
    if coroutine.status(task.thread)=='dead' then
     if board then
      cooperative=false
      return board,{total=target,upper=target,relaxed_upper=initialupper,optimal=true,nodes=nodes,propagations=propagations,mode='exact-resumable-profiles'}
     end
     -- 任一完整搜索已排除此配额，其余分支顺序无需重复证明。
     for i=#tasks,1,-1 do if tasks[i].profile==task.profile then table.remove(tasks,i) end end
     at=1
    else
     if yieldfn then yieldfn() end
     local grouped=task.method=='groups'
     local slice=grouped and work-task.started_work>=task.quantum*32 or not grouped and (nodes-task.started_nodes>=task.quantum or work-task.started_work>=task.quantum*2048)
     if slice then task.quantum=task.quantum*8;task.started_nodes=nil;task.started_work=nil;at=at+1 end
    end
   end
   cooperative=false
   if aborted then return seed,{total=lower,upper=initialupper,optimal=false,pending=true,nodes=nodes,propagations=propagations,prepared=preparedData} end
   end
  end
 end
 return seed,{total=lower,upper=lower,relaxed_upper=initialupper,optimal=true,nodes=nodes,propagations=propagations,mode='exact-pit-constraints'}
end
return M
