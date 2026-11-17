-- 固定最大数量后的排列：整体图案一致 → 完整行列 → 规则留空 → 稳定顺序。
-- 不使用同族分散/距离/跨格接缝奖励；同族仍由 Layout.Valid 严格校验。
local M={VERSION='pattern-first-1'}
local Layout=require('aom_seed_layout')
local FIELDS={'pattern_mismatch','line_cost','hole_cost','order_cost'}
function M.Better(a,b)
 if not b then return true end
 for _,k in ipairs(FIELDS)do
  if math.abs(a[k]-b[k])>.000001 then return a[k]<b[k] end
 end
 return false
end
local function Key(cells)
 local keys={};for i=1,9 do keys[i]=cells[i]or '_' end
 return table.concat(keys,',')
end
local function Style(cells)
 local ordercost=Layout.TileCost(cells)
 local function Axis(transpose)
  local full,breaks,gaps,gap=0,0,0,0
  for z=0,2 do
   local row={};for x=0,2 do row[x+1]=cells[transpose and x*3+z+1 or z*3+x+1]end
   if row[1]and row[1]==row[2]and row[1]==row[3]then full=full+1 end
   local last,at
   for x=1,3 do local k=row[x]
    if k then
     if last then if last~=k then breaks=breaks+1 end;if x>at+1 then breaks=breaks+1 end end
     last,at=k,x
    else gaps=gaps+1;gap=z*3+x-1 end
   end
  end
  return {pattern_mismatch=0,line_cost=breaks*3-full*6,
   -- 单空坑越靠近中心越整齐；仅参与固定数量后的比较，不能排除合法布局。
   hole_cost=gaps==1 and math.abs(gap%3-1)+math.abs(math.floor(gap/3)-1)or 0,
   order_cost=ordercost}
 end
 local a,b=Axis(false),Axis(true);return M.Better(b,a)and b or a
end
local function Copy(a)local out={};for _,k in ipairs(FIELDS)do out[k]=a[k]end;return out end
local function AddStyle(a,b,sign)
 for i=2,#FIELDS do local k=FIELDS[i];a[k]=a[k]+b[k]*sign end
end
local function GroupMismatch(group)
 local size=#group.tiles;local mismatch=0
 for s=1,9 do local squares=0;for _,n in pairs(group.columns[s])do squares=squares+n*n end
  mismatch=mismatch+(size*size-squares)/2
 end
 return mismatch/size
end
local function Build(board,geometry,yieldfn,classic,withbank)
 local state={pattern_mismatch=0,line_cost=0,hole_cost=0,order_cost=0,groups={},active={},cells={},styles={},keys={},bytile={}}
 local signatures,stylecache={},{}
 local function Entry(cells)
  local key=Key(cells);local entry=stylecache[key]
  if not entry then entry={cells=cells,key=key,style=Style(cells)};stylecache[key]=entry end
  return entry
 end
 for t=1,#board/9 do
  local cells=Layout.Tile(board,t);local signature=Layout.Signature(cells)
  if signature~=''then
   local group=signatures[signature]
   if not group then group={tiles={},columns={},bank={},seen={}};for s=1,9 do group.columns[s]={}end
    signatures[signature]=group;state.groups[#state.groups+1]=group
    if withbank then
     for _,v in ipairs(Layout.Candidates(cells,yieldfn))do
      if not classic or v.classic then
       local e=Entry(v.cells);group.bank[#group.bank+1]=e;group.seen[e.key]=true
      end
     end
    end
   end
   local entry=Entry(cells)
   group.tiles[#group.tiles+1]=t;state.active[#state.active+1]=t;state.bytile[t]=group
   state.cells[t]=cells;state.keys[t]=entry.key;state.styles[t]=entry.style;AddStyle(state,entry.style,1)
   for s=1,9 do local k=cells[s]or '_';group.columns[s][k]=(group.columns[s][k]or 0)+1 end
   if withbank then for r=0,7 do local e=Entry(Layout.Transform(cells,r))
    if not group.seen[e.key]then group.bank[#group.bank+1]=e;group.seen[e.key]=true end
   end end
  end
  if t%16==0 and yieldfn then yieldfn()end
 end
 local function LessTile(a,b)
  local p,q=geometry.tiles and geometry.tiles[a],geometry.tiles and geometry.tiles[b]
  if p and q then if p.z~=q.z then return p.z<q.z end;if p.x~=q.x then return p.x<q.x end end
  return a<b
 end
 table.sort(state.active,LessTile)
 for _,group in ipairs(state.groups)do
  table.sort(group.tiles,LessTile);group.mismatch=GroupMismatch(group);state.pattern_mismatch=state.pattern_mismatch+group.mismatch
  table.sort(group.bank,function(a,b)
   if M.Better(a.style,b.style)then return true end;if M.Better(b.style,a.style)then return false end
   return a.key<b.key
  end)
 end
 table.sort(state.groups,function(a,b)return LessTile(a.tiles[1],b.tiles[1])end)
 return state,Entry
end
function M.Metrics(board,geometry)
 return Copy(Build(board,geometry))
end
function M.Regularize(board,geometry,yieldfn,classic,trialbudget,trace)
 if trace then trace:Stage('arrange_candidates')end
 -- 旧指标只在首尾计算以兼容诊断/导出，不进入候选评分的热路径。
 local before=Layout.Metrics(board,geometry,yieldfn)
 local state,Entry=Build(board,geometry,yieldfn,classic,true)
 local beforepattern=Copy(state);for _,k in ipairs(FIELDS)do before[k]=state[k]end
 local trials,moves,passes=0,0,0
 local limit=trialbudget or math.max(800,math.min(5000,#state.active*180))
 local budget={group=0,region=0,tile=0,pair=0}
 local function Settled(group)
  if group.settled~=nil then return group.settled end
  group.settled=false
  if group.mismatch>.000001 then return false end
  for _,t in ipairs(group.tiles)do if M.Better(group.bank[1].style,state.styles[t])then return false end end
  group.settled=true;return true
 end
 local function Set(t,entry)
  local group=state.bytile[t];local old=state.cells[t]
  group.settled=nil
  for s=1,9 do local a,b=old[s]or '_',entry.cells[s]or '_'
   group.columns[s][a]=group.columns[s][a]-1;group.columns[s][b]=(group.columns[s][b]or 0)+1
   board[(t-1)*9+s]=entry.cells[s]
  end
  AddStyle(state,state.styles[t],-1);AddStyle(state,entry.style,1)
  state.cells[t]=entry.cells;state.styles[t]=entry.style;state.keys[t]=entry.key
 end
 local function Choose(indices,proposal,phase)
  if trials>=limit then return false end
  local old,touched={},{};local different=false
  for j,t in ipairs(indices)do
   local entry=proposal[j];if state.keys[t]~=entry.key then different=true end
   old[j]=Entry(state.cells[t]);touched[state.bytile[t]]=true
  end
  if not different then return false end
  local energy=Copy(state)
  for group in pairs(touched)do state.pattern_mismatch=state.pattern_mismatch-group.mismatch end
  for j,t in ipairs(indices)do Set(t,proposal[j])end
  for group in pairs(touched)do state.pattern_mismatch=state.pattern_mismatch+GroupMismatch(group)end
  local better=M.Better(state,energy)and Layout.Valid(board,geometry,yieldfn)
  if better then
   moves=moves+1;for group in pairs(touched)do group.mismatch=GroupMismatch(group)end
  else
   for j,t in ipairs(indices)do Set(t,old[j])end
   for _,k in ipairs(FIELDS)do state[k]=energy[k]end
  end
  trials=trials+1;budget[phase]=budget[phase]+1
  if yieldfn and (trials%4==0 or #state.active>16)then yieldfn()end
  return better
 end
 local function Coherent(indices,entry,phase)
  local proposal={};for j=1,#indices do proposal[j]=entry end
  return Choose(indices,proposal,phase)
 end
 if trace then trace:Stage('arrange_group_bank')end
 -- 一轮给每组一个候选，先覆盖全田，再深入某一组；已达到候选下界的组直接结束。
 for candidate=1,32 do
  for _,group in ipairs(state.groups)do if not Settled(group)and group.bank[candidate]then
   Coherent(group.tiles,group.bank[candidate],'group')
  end end
  if trials>=limit then break end
 end
 -- 全组无法统一时，按相同组成的实际连通区域再尝试。
 local adjacency={};for _,t in ipairs(state.active)do adjacency[t]={}end
 for _,e in ipairs(geometry.edges)do if state.bytile[e.a]and state.bytile[e.a]==state.bytile[e.b]then
  adjacency[e.a][#adjacency[e.a]+1]=e.b;adjacency[e.b][#adjacency[e.b]+1]=e.a
 end end
 local regions,seen={},{}
 for _,first in ipairs(state.active)do if not seen[first]then
  local region={first};seen[first]=true;local at=1
  while at<=#region do for _,t in ipairs(adjacency[region[at]])do if not seen[t]then seen[t]=true;region[#region+1]=t end end;at=at+1 end
  local group=state.bytile[first]
  if #region>1 and #region<#group.tiles then table.sort(region,function(a,b)return a<b end);regions[#regions+1]={tiles=region,group=group}end
 end end
 if trace then trace:Stage('arrange_search')end
 for candidate=1,8 do for _,r in ipairs(regions)do
  if not Settled(r.group)and r.group.bank[candidate]then Coherent(r.tiles,r.group.bank[candidate],'region')end
 end end
 -- 单格按候选轮转，双格按邻边轮转，避免左上角先花光预算。
 local changed=true
 while changed and trials<limit do
  changed=false;passes=passes+1
  for candidate=1,48 do
   for _,t in ipairs(state.active)do local group=state.bytile[t]
    if not Settled(group)and group.bank[candidate]then changed=Choose({t},{group.bank[candidate]},'tile')or changed end
   end
   if trials>=limit then break end
  end
  for rotation=0,7 do for _,e in ipairs(geometry.edges)do
   local a,b=state.bytile[e.a],state.bytile[e.b]
   if a and b and (not Settled(a)or not Settled(b))then
    local ca,cb=state.cells[e.a],state.cells[e.b]
    changed=Choose({e.a,e.b},{Entry(Layout.Transform(ca,rotation)),Entry(Layout.Transform(cb,rotation))},'pair')or changed
   end
  end end
 end
 assert(Layout.Valid(board,geometry,yieldfn),'arrangement final validation failed')
 local after=Layout.Metrics(board,geometry,yieldfn);for _,k in ipairs(FIELDS)do after[k]=state[k]end
 assert(not M.Better(beforepattern,state),'arrangement worsened pattern objective')
 if trace then
  trace:Context({arrangement_trials=trials,arrangement_moves=moves,arrangement_passes=passes,arrangement_trial_limit=limit,
   arrangement_objective=M.VERSION,pattern_mismatch_before=beforepattern.pattern_mismatch,pattern_mismatch_after=state.pattern_mismatch})
  trace:Stage('arrange_finalize')
 end
 return board,{before=before,after=after,objective=M.VERSION,trials=trials,moves=moves,passes=passes,limited=trials>=limit,phase_trials=budget}
end
return M
