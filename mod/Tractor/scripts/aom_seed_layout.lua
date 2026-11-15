-- 数量规划与整片排列。按原版养分向量配比，不读取地皮当前肥力。
local M={}
local ORDER={'carrot','corn','potato','tomato','asparagus','eggplant','pumpkin','watermelon','dragonfruit','durian','garlic','onion','pepper','pomegranate'}
local rank={};for i,k in ipairs(ORDER) do rank[k]=i end
local function Key(a)return table.concat(a,',') end
local function Less(a,b)
 local x,y=rank[a] or 100,rank[b] or 100
 return x~=y and x<y or x==y and a<b
end
function M.Crops(counts,defs,season)
 local crops={}
 for k,n in pairs(counts) do local d=defs[k]
  if d and d.good_seasons and d.good_seasons[season] and n>=(d.family_min_count or 4) then crops[#crops+1]=k end
 end
 table.sort(crops,Less);return crops
end
-- 每种种子允许不用，或至少使用同族最低株数。滑动窗口DP同时求数量及种类上界。
function M.Allocate(crops,counts,defs,capacity,offset,yieldfn)
 local dp={[0]=0};local history={};local ordered={}
 for i=1,#crops do
  local k=crops[(i-1+(offset or 0))%#crops+1];ordered[i]=k
  local minimum,stock=defs[k].family_min_count or 4,math.min(counts[k],capacity)
  local nextdp,choices,queue={}, {}, {};local head,tail=1,0
  for total=0,capacity do
   nextdp[total]=dp[total];choices[total]=-1
   local add=total-minimum
   if add>=0 and dp[add] then
    while head<=tail and dp[queue[tail]]<=dp[add] do tail=tail-1 end
    tail=tail+1;queue[tail]=add
   end
   while head<=tail and queue[head]<total-stock do head=head+1 end
   if head<=tail and (not nextdp[total] or dp[queue[head]]+1>nextdp[total]) then
    nextdp[total]=dp[queue[head]]+1;choices[total]=queue[head]
   end
  end
  dp=nextdp;history[i]=choices;if yieldfn then yieldfn() end
 end
 local upper=capacity;while upper>0 and not dp[upper] do upper=upper-1 end
 local remaining,allocation=upper,{}
 for i=#ordered,1,-1 do local old=history[i][remaining]
  if old>=0 then allocation[#allocation+1]={k=ordered[i],n=remaining-old};remaining=old end
 end
 table.sort(allocation,function(a,b)return Less(a.k,b.k)end)
 -- 相同数量/种类下轮流补余量，避免第一种库存吞掉所有坑位。
 local used=0;for _,a in ipairs(allocation) do a.n=defs[a.k].family_min_count or 4;used=used+a.n end
 while used<upper do
  for _,a in ipairs(allocation) do if used<upper and a.n<counts[a.k] then a.n=a.n+1;used=used+1 end end
 end
 return allocation,upper,dp[upper] or 0
end
local function Transform(a,r)
 local out={}
 for i,k in ipairs(a) do
  local x,z=(i-1)%3,math.floor((i-1)/3)
  if r>=4 then x=2-x end
  for _=1,r%4 do x,z=2-z,x end
  out[z*3+x+1]=k
 end
 return out
end
M.Transform=Transform
local function Placement(a)
 local breaks,inversions,left=0,0,0
 for i,k in ipairs(a) do if k then
  left=left+(i-1)%3
  for j=i+1,9 do if a[j] and Less(a[j],k) then inversions=inversions+1 end end
 end end
 for z=0,2 do local last,at
  for x=0,2 do local k=a[z*3+x+1]
   if k then
    if last then if last~=k then breaks=breaks+1 end;if x>at+1 then breaks=breaks+1 end end
    last,at=k,x
   end
  end
 end
 return breaks*3000+inversions*4+left
end
local function TileCost(a)
 local function Axis(b)
  local full,gaps,gap=0,0,0
  for z=0,2 do local i=z*3+1;if b[i] and b[i]==b[i+1] and b[i]==b[i+2] then full=full+1 end end
  for i,k in ipairs(b) do if not k then gaps=gaps+1;gap=i-1 end end
  return Placement(b)-6000*full+(gaps==1 and (math.abs(gap%3-1)+math.abs(math.floor(gap/3)-1))*5000 or 0)
 end
 local transpose={};for i=1,9 do transpose[i]=a[((i-1)%3)*3+math.floor((i-1)/3)+1] end
 return math.min(Axis(a),Axis(transpose))
end
local candidateCache,cacheOrder={},{}
function M.Candidates(a,yieldfn)
 local counts,crops={},{}
 for _,k in ipairs(a) do if k then if not counts[k] then crops[#crops+1]=k;counts[k]=0 end;counts[k]=counts[k]+1 end end
 table.sort(crops,Less)
 local plants={};for _,k in ipairs(crops) do for _=1,counts[k] do plants[#plants+1]=k end end
 local holes=9-#plants;local signature={}
 for _,k in ipairs(crops) do signature[#signature+1]=k..':'..counts[k] end
 signature=table.concat(signature,'|')..'/'..holes
 local cached=candidateCache[signature];local bank,seen={},{};local classic=true
 local function One(c)
  local sig={};for i,k in ipairs(c) do sig[i]=k or '_' end;sig=Key(sig)
  if not seen[sig] then
   seen[sig]=true;bank[#bank+1]={cells=c,cost=TileCost(c),key=sig,classic=classic}
   if #bank%64==0 and yieldfn then yieldfn() end
  end
 end
 local function Add(b)for r=0,7 do One(Transform(b,r)) end end
 local function Sort()
  table.sort(bank,function(x,y)return x.cost~=y.cost and x.cost<y.cost or x.cost==y.cost and x.key<y.key end)
 end
 if not cached then
 for first=0,3 do for second=0,3 do local third=holes-first-second
  if third>=0 and third<=3 then for align=0,2 do
   local b,nextplant={},1
   for z,gap in ipairs({first,second,third}) do
    local start=align==0 and 0 or align==1 and gap or math.floor(gap/2)
    for x=0,2 do
     local filled=x>=start and x<start+3-gap
     b[(z-1)*3+x+1]=filled and plants[nextplant] or false
     if filled then nextplant=nextplant+1 end
    end
   end
   Add(b)
  end end
 end end
 for _,path in ipairs({{1,2,3,6,9,8,7,4,5},{1,2,3,6,5,4,7,8,9}}) do
  local b={};for i=1,9 do b[path[i]]=plants[i] or false end;Add(b)
 end
 -- 小型多重集完整枚举，补齐旧行带生成器漏掉的中间L形、方块、T形等。
 local factorial={1};for n=1,9 do factorial[n+1]=factorial[n]*n end
 local variants=factorial[10]/factorial[holes+1]
 for _,k in ipairs(crops) do variants=variants/factorial[counts[k]+1] end
 classic=false
 if variants<=2000 then
  local options={};for _,k in ipairs(crops) do options[#options+1]=k end;options[#options+1]=false
  local remaining={};for i,k in ipairs(options) do remaining[i]=k and counts[k] or holes end
  local pattern={}
  local function Enumerate(at)
   if at==10 then local c={};for i,k in ipairs(pattern) do c[i]=k end;One(c);return end
   for i,k in ipairs(options) do if remaining[i]>0 then
    remaining[i]=remaining[i]-1;pattern[at]=k;Enumerate(at+1);remaining[i]=remaining[i]+1
   end end
  end
  Enumerate(1)
 end
 Sort();cached={bank=bank,seen=seen,complete=variants<=2000};candidateCache[signature]=cached;cacheOrder[#cacheOrder+1]=signature
 if #cacheOrder>16 then candidateCache[table.remove(cacheOrder,1)]=nil end
 end
 bank,seen={},{}
 for i,v in ipairs(cached.bank) do bank[i]=v;seen[v.key]=true end;bank.complete=cached.complete
 classic=false;local before=#bank;Add(a);if #bank>before then Sort() end
 return bank
end
function M.Geometry(tiles,slots,defs,yieldfn)
 local near,edges,adjacent,conflicts={}, {}, {},{}
 local radius=4;for _,d in pairs(defs) do radius=math.max(radius,d.family_check_dist or 4) end
 for i,p in ipairs(slots) do
  near[i]={};adjacent[i]={};conflicts[i]={}
  for j,q in ipairs(slots) do
   local d=(p.x-q.x)^2+(p.z-q.z)^2
   if i~=j and d<=(GetFarmTillSpacing and GetFarmTillSpacing() or 1.25)^2 then conflicts[i][#conflicts[i]+1]=j end
   if d<=radius^2 then near[i][#near[i]+1]={j=j,d=d} end
   if i~=j and d<=32/9+.000001 then adjacent[i][#adjacent[i]+1]=j end
  end
  if i%9==0 and yieldfn then yieldfn() end
 end
 for i,a in ipairs(tiles) do for j=i+1,#tiles do local b=tiles[j]
  if math.abs(a.x-b.x)==4 and a.z==b.z then edges[#edges+1]={a=a.x<b.x and i or j,b=a.x<b.x and j or i,horizontal=true}
  elseif math.abs(a.z-b.z)==4 and a.x==b.x then edges[#edges+1]={a=a.z<b.z and i or j,b=a.z<b.z and j or i,horizontal=false} end
 end end
 return {near=near,edges=edges,defs=defs,adjacent=adjacent,conflicts=conflicts}
end
function M.Valid(board,geometry)
 if geometry.conflicts then for i,list in ipairs(geometry.conflicts) do if board[i] then for _,j in ipairs(list) do if board[j] then return false end end end end end
 if geometry.balanced and not require('aom_seed_balance').Board(board,geometry.defs) then return false end
 for i,k in ipairs(board) do if k then
  local n=0;local def=geometry.defs[k]
  for _,q in ipairs(geometry.near[i]) do if q.d<=(def.family_check_dist or 4)^2 and board[q.j]==k then n=n+1 end end
  if n<(def.family_min_count or 4) then return false end
 end end
 return true
end
local function Tile(board,t)
 local a={};for i=1,9 do a[i]=board[(t-1)*9+i] end;return a
end
local function Signature(a)
 local counts,keys={},{}
 for _,k in ipairs(a) do if k then if not counts[k] then counts[k]=0;keys[#keys+1]=k end;counts[k]=counts[k]+1 end end
 table.sort(keys,Less);local out={};for _,k in ipairs(keys) do out[#out+1]=k..':'..counts[k] end
 return table.concat(out,'|'),table.concat(keys,'|')
end
function M.Metrics(board,geometry)
 local localcost,family,seams,repetition,neighbors=0,0,0,0,0
 local signatures={}
 for t=1,#board/9 do local a=Tile(board,t);signatures[t]=Signature(a);localcost=localcost+TileCost(a) end
 for i,k in ipairs(board) do if k then
  local distances={};local radius=(geometry.defs[k].family_check_dist or 4)^2
  for _,q in ipairs(geometry.near[i]) do if q.j~=i and q.d<=radius and board[q.j]==k then distances[#distances+1]=q.d*9/16 end end
  table.sort(distances);for j=1,3 do family=family+(distances[j] or 16) end
 end end
 for _,e in ipairs(geometry.edges) do
  for s=1,9 do local a,b=board[(e.a-1)*9+s],board[(e.b-1)*9+s]
   if a and b and a~=b then neighbors=neighbors+1 end
   if signatures[e.a]~='' and signatures[e.a]==signatures[e.b] and a~=b then repetition=repetition+1 end
  end
  for i=0,2 do
   local a=(e.a-1)*9+(e.horizontal and i*3+3 or 7+i)
   local b=(e.b-1)*9+(e.horizontal and i*3+1 or 1+i)
   if board[a] and board[a]==board[b] then seams=seams+1 end
  end
 end
 -- 仅看最近三个同族会把相隔很远的四株小团误判为同样紧凑。
 -- 加入同族接触分量，鼓励在行列约束允许时将分散小团连起来。
 local visited,types,components,kinds={}, {},0,0
 for i,k in ipairs(board) do if k then
  if not types[k] then types[k]=true;kinds=kinds+1 end
  if not visited[i] then
   components=components+1;local queue={i};visited[i]=true;local at=1
   while at<=#queue do
    for _,j in ipairs(geometry.adjacent[queue[at]]) do
     if not visited[j] and board[j]==k then visited[j]=true;queue[#queue+1]=j end
    end
    at=at+1
   end
  end
 end end
 local fragmentation=components-kinds
 return {score=localcost+family*100-seams*200+neighbors*3+repetition*1000+fragmentation*3000,
  tidy=localcost-seams*200+neighbors*3+repetition*1000,
  family=family,seams=seams,repetition=repetition,localcost=localcost,components=components,fragmentation=fragmentation}
end
-- 给每块地皮分配尽量均匀的数量，再由同族验证决定是否采用。
function M.Distributed(allocation,tiles,rotation,inward,yieldfn,useclassic)
 local tilecount=#tiles
 local total=0;for _,a in ipairs(allocation) do total=total+a.n end
 local active=math.min(tilecount,math.ceil(total/9));local cells,free={},{}
 for t=1,tilecount do cells[t]={};free[t]=9 end
 for c,a in ipairs(allocation) do
  local left=a.n
  while left>0 do
   for j=1,active do local t=(j+c-2)%active+1
    if left>0 and free[t]>0 then cells[t][#cells[t]+1]=a.k;free[t]=free[t]-1;left=left-1 end
   end
  end
 end
 local board={}
 local minx,minz,maxx,maxz=math.huge,math.huge,-math.huge,-math.huge
 for t=1,active do local p=tiles[t];minx=math.min(minx,p.x);maxx=math.max(maxx,p.x);minz=math.min(minz,p.z);maxz=math.max(maxz,p.z) end
 for t=1,tilecount do
  while #cells[t]<9 do cells[t][#cells[t]+1]=false end
  local bank=M.Candidates(cells[t],yieldfn);local selected=bank[1]
  if useclassic then for _,v in ipairs(bank) do if v.classic then selected=v;break end end end
  local a=Transform(selected.cells,rotation or 0)
  if inward and t<=active then
   local lx,lz,hx,hz=2,2,0,0
   for i,k in ipairs(a) do if k then local x,z=(i-1)%3,math.floor((i-1)/3);lx=math.min(lx,x);lz=math.min(lz,z);hx=math.max(hx,x);hz=math.max(hz,z) end end
   local p=tiles[t];local dx=minx==maxx and 0 or p.x==minx and 2-hx or -lx
   local dz=minz==maxz and 0 or p.z==minz and 2-hz or -lz
   local shifted={false,false,false,false,false,false,false,false,false}
   for i,k in ipairs(a) do if k then shifted[(math.floor((i-1)/3)+dz)*3+(i-1)%3+dx+1]=k end end
   a=shifted
  end
  for _,k in ipairs(a) do board[#board+1]=k end
 end
 return board
end
function M.Clustered(allocation,slots,axis)
 local total=0;for _,a in ipairs(allocation) do total=total+a.n end
 local active=math.ceil(total/9)*9;local indices,board={},{}
 for i=1,#slots do board[i]=false;if i<=active then indices[#indices+1]=i end end
 table.sort(indices,function(i,j)
  local p,q=slots[i],slots[j];local x,y=axis==1 and p.x or p.z,axis==1 and q.x or q.z
  if x~=y then return x<y end
  return (axis==1 and p.z or p.x)<(axis==1 and q.z or q.x)
 end)
 local pos=1;for _,a in ipairs(allocation) do for _=1,a.n do board[indices[pos]]=a.k;pos=pos+1 end end
 return board,active
end
-- 可证明的乐观评分下界，用于跳过不可能击败当前解的起始布局。
function M.LowerBound(board,geometry,yieldfn)
 local score=-600*#geometry.edges
 for t=1,#board/9 do
  local cells=Tile(board,t);local bank=M.Candidates(cells,yieldfn)
  if bank.complete then score=score+bank[1].cost
  else
   local counts={};for _,k in ipairs(cells) do if k then counts[k]=(counts[k] or 0)+1 end end
   for _,n in pairs(counts) do score=score-6000*math.floor(n/3) end
  end
  local planted=0;for _,k in ipairs(cells) do if k then planted=planted+1 end end
  local costs={}
  for s=1,9 do
   local i=(t-1)*9+s;local ds={}
   for _,q in ipairs(geometry.near[i]) do if q.j~=i then ds[#ds+1]=q.d end end
   table.sort(ds);costs[s]=((ds[1] or 0)+(ds[2] or 0)+(ds[3] or 0))*9/16*100
  end
  table.sort(costs);for i=1,planted do score=score+costs[i] end
 end
 return score
end
-- 数量已由规划器锁定；先减少分散同族，再缩短同族距离，最后比较排列。
function M.Better(a,b)
 if not b then return true end
 if a.fragmentation~=b.fragmentation then return a.fragmentation<b.fragmentation end
 if math.abs(a.family-b.family)>.000001 then return a.family<b.family end
 return a.tidy<b.tidy-.000001
end
function M.Regularize(board,geometry,yieldfn,classic,trialbudget)
 local before=M.Metrics(board,geometry);local energy=before
 local saved,savedscore=nil,before.score
 local function Save()
  saved={};for i,k in ipairs(board) do saved[i]=k end
 end
 if classic then Save() end
 local groups,sets,banks,active={}, {}, {}, {}
 for t=1,#board/9 do local a=Tile(board,t);local signature,set=Signature(a)
  if signature~='' then
   active[#active+1]=t
   groups[signature]=groups[signature] or {};groups[signature][#groups[signature]+1]=t
   sets[t]=set;banks[t]=M.Candidates(a,yieldfn)
   if classic then
    local current={}
    for r=0,7 do local c=Transform(a,r);local sig={};for i,k in ipairs(c) do sig[i]=k or '_' end;current[Key(sig)]=true end
    local filtered={};for _,v in ipairs(banks[t]) do if v.classic or current[v.key] then filtered[#filtered+1]=v end end;banks[t]=filtered
   end
  end
 end
 local ordered={};for _,group in pairs(groups) do ordered[#ordered+1]=group end
 table.sort(ordered,function(a,b)return a[1]<b[1] end)
 -- 相同组成共享候选库；同族约束允许时整组同时转向，避免单格移动被卡住。
 for _,group in ipairs(ordered) do
  local seen,bank={},{}
  for _,t in ipairs(group) do for _,a in ipairs(banks[t]) do if not seen[a.key] then seen[a.key]=true;bank[#bank+1]=a end end end
  table.sort(bank,function(a,b)return a.cost~=b.cost and a.cost<b.cost or a.cost==b.cost and a.key<b.key end)
  for _,t in ipairs(group) do banks[t]=bank end
 end
 local trials,moves=0,0;local limit=classic and math.max(600,math.min(4000,#active*120)) or math.max(800,math.min(5000,#active*180))
 if trialbudget then limit=math.min(limit,trialbudget) end
 local function Choose(indices,proposal)
  if trials>=limit then return false end
  local different=false
  for j,t in ipairs(indices) do for s=1,9 do if board[(t-1)*9+s]~=proposal[j][s] then different=true;break end end end
  if not different then return false end
  local old={};for j,t in ipairs(indices) do old[j]=Tile(board,t);for s=1,9 do board[(t-1)*9+s]=proposal[j][s] end end
  local metrics=M.Metrics(board,geometry)
  local value=metrics
  local better=M.Better(value,energy) and M.Valid(board,geometry)
  if better then
   energy=value;moves=moves+1
   if classic then savedscore=metrics.score;Save() end
  else for j,t in ipairs(indices) do for s=1,9 do board[(t-1)*9+s]=old[j][s] end end end
  trials=trials+1;if yieldfn and (trials%4==0 or #active>16) then yieldfn() end
  return better
 end
 local function Coherent(group)
  local changed=false
  for i,a in ipairs(banks[group[1]]) do if not classic and i>32 then break end;local proposal={};for j=1,#group do proposal[j]=a.cells end;changed=Choose(group,proposal) or changed end
  return changed
 end
 local changed=true;local passes=0
 while changed and trials<limit do
  changed=false;passes=passes+1
  for _,group in ipairs(ordered) do if #group>1 then changed=Coherent(group) or changed end end
  -- 不同密度、相同作物集合的连通分量，共同调整行列方向。
  local seen={}
  for _,first in ipairs(active) do if not seen[first] then
   local group={first};seen[first]=true;local i=1
   while i<=#group do
    for _,e in ipairs(geometry.edges) do local q=e.a==group[i] and e.b or e.b==group[i] and e.a
     if q and not seen[q] and sets[q]==sets[first] then seen[q]=true;group[#group+1]=q end
    end;i=i+1
   end
   if #group>1 then
    for r=0,7 do local proposal={};for j,t in ipairs(group) do proposal[j]=Transform(banks[t][1].cells,r) end;changed=Choose(group,proposal) or changed end
   end
  end end
  for _,t in ipairs(active) do for i,a in ipairs(banks[t]) do if not classic and i>48 then break end;changed=Choose({t},{a.cells}) or changed end end
  for _,e in ipairs(geometry.edges) do if banks[e.a] and banks[e.b] then
   local original={Tile(board,e.a),Tile(board,e.b)}
   if classic then
    for r=0,7 do changed=Choose({e.a,e.b},{Transform(original[1],r),Transform(original[2],r)}) or changed end
   else
   -- 拐角处两边往往需要朝不同方向转；只同步转向会卡在分散布局中。
   local options={{},{}};local seen={{},{}}
   for j=1,2 do for r=0,7 do
    local a=Transform(original[j],r);local sig={};for i,k in ipairs(a) do sig[i]=k or '_' end;sig=Key(sig)
    if not seen[j][sig] then seen[j][sig]=true;options[j][#options[j]+1]=a end
   end end
   for _,a in ipairs(options[1]) do for _,b in ipairs(options[2]) do changed=Choose({e.a,e.b},{a,b}) or changed end end
   end
  end end
 end
 if saved then for i,k in ipairs(saved) do board[i]=k end end
 return board,{before=before,after=M.Metrics(board,geometry),trials=trials,moves=moves,passes=passes,limited=trials>=limit}
end
return M
