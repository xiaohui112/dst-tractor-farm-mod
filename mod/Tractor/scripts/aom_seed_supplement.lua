-- 完整模板方案的增量补块：不移动原作物，不占用原模板的必要空坑。
local M={}
local Data=require('aom_seed_template_data')
local Layout=require('aom_seed_layout')
local function Copy(a)local b={};for k,v in pairs(a)do b[k]=v end;return b end

function M.Fill(board,modules,crops,stock,tiles,slots,defs,geometry,yieldfn,options)
 options=options or {}
 local budget=options.supplement_budget or 12000
 local report={attempts=0,work_budget=budget,added=0,limited=false}
 local occupied,free,remaining={}, {},Copy(stock)
 for _,m in ipairs(modules)do for _,ti in ipairs(m.placement.indices)do occupied[ti]=true end end
 for _,k in ipairs(board)do if k then remaining[k]=remaining[k]-1 end end
 for ti=1,#tiles do if not occupied[ti]then free[ti]=true end end
 if not next(free)then return board,modules,report end
 local placements=Data.Prepare(crops,remaining,tiles,slots,defs,yieldfn,
  {supplements=true,allowed_tiles=free,template_id=options.template_id})
 local choices,neighbors,support,adjacent={}, {},{},{}
 for _,edge in ipairs(geometry.edges)do
  adjacent[edge.a]=adjacent[edge.a]or {};adjacent[edge.a][#adjacent[edge.a]+1]=edge.b
  adjacent[edge.b]=adjacent[edge.b]or {};adjacent[edge.b][#adjacent[edge.b]+1]=edge.a
 end
 local prepared=0
 for _,p in ipairs(placements)do
  local ti=p.indices[1];choices[ti]=choices[ti]or {}
  for _,r in ipairs(p.recipes)do
   local score=0;local fits=true
   for s=1,9 do local i=(ti-1)*9+s;local k=r.map[p.cells[s]]
    for _,j in ipairs(geometry.conflicts[i])do if board[j]then fits=false end end
    -- 同配比邻地优先沿用相同的行列图案；数量优先于此排序。
    for _,other in ipairs(adjacent[ti]or {})do
     if board[(other-1)*9+s]==k then score=score+1 end
    end
   end
   if fits then choices[ti][#choices[ti]+1]={placement=p,recipe=r,score=score}end
   prepared=prepared+1;if prepared%32==0 and yieldfn then yieldfn()end
  end
 end
 local order={}
 for ti,list in pairs(choices)do if #list>0 then
  order[#order+1]=ti;neighbors[ti]={};support[ti]=0
  table.sort(list,function(a,b)
   if a.score~=b.score then return a.score>b.score end
   if a.placement.id~=b.placement.id then return a.placement.id<b.placement.id end
   if a.placement.symmetry~=b.placement.symmetry then return a.placement.symmetry<b.placement.symmetry end
   return a.recipe.key<b.recipe.key
  end)
  for s=1,9 do for _,q in ipairs(geometry.near[(ti-1)*9+s])do
   local other=math.floor((q.j-1)/9)+1
   if other~=ti then
    if choices[other]and #choices[other]>0 then neighbors[ti][other]=true end
    if board[q.j]then support[ti]=support[ti]+1 end
   end
  end end
 end end
 table.sort(order,function(a,b)
  if support[a]~=support[b]then return support[a]>support[b]end
  return tiles[a].z~=tiles[b].z and tiles[a].z<tiles[b].z or tiles[a].z==tiles[b].z and tiles[a].x<tiles[b].x
 end)
 local rank={};for i,ti in ipairs(order)do rank[ti]=i end
 for ti,list in pairs(neighbors)do
  local sorted={};for other in pairs(list)do sorted[#sorted+1]=other end
  table.sort(sorted,function(a,b)return rank[a]<rank[b]end);neighbors[ti]=sorted
 end
 board=Copy(board);modules=Copy(modules)
 local processed={}
 for _,root in ipairs(order)do if not processed[root]then
  if report.attempts>=budget then report.limited=true;break end
  -- 邻接空块共同尝试同族，避免逐块验收误杀互相依赖的补块。
  -- 每组最多6块，递归深度不随全田面积增长。
  local group={root};processed[root]=true;local at=1
  while at<=#group and #group<6 do
   for _,ti in ipairs(neighbors[group[at]])do
    if #group<6 and not processed[ti]then
     processed[ti]=true;group[#group+1]=ti
    end
   end
   at=at+1
  end
  local selected,best,bestn={}, {},0
  local function Save(n)
   if n<=bestn then return end
   local indices={}
   for _,m in ipairs(selected)do local ti=m.placement.indices[1]
    for s=1,9 do indices[#indices+1]=(ti-1)*9+s end
   end
   if Data.FamilyValid(board,geometry,indices)then bestn=n;best=Copy(selected)end
  end
  local function Search(index,n)
   if report.attempts>=budget then report.limited=true;Save(n);return end
   report.attempts=report.attempts+1
   if report.attempts%64==0 and yieldfn then yieldfn()end
   if n+9*(#group-index+1)<=bestn then return end
   if index>#group then Save(n);return end
   local ti=group[index]
   for _,m in ipairs(choices[ti])do
    if report.attempts>=budget then report.limited=true;break end
    report.attempts=report.attempts+1
    if report.attempts%64==0 and yieldfn then yieldfn()end
    local p,r=m.placement,m.recipe;local fits=Data.Fits(r,remaining)
    if fits then for s=1,9 do
     for _,j in ipairs(geometry.conflicts[(ti-1)*9+s])do if board[j]then fits=false end end
    end end
    if fits then
     for k,count in pairs(r.needs)do remaining[k]=remaining[k]-count end
     for s=1,9 do board[(ti-1)*9+s]=r.map[p.cells[s]]or false end
     selected[#selected+1]=m;Search(index+1,n+9);selected[#selected]=nil
     for s=1,9 do board[(ti-1)*9+s]=false end
     for k,count in pairs(r.needs)do remaining[k]=remaining[k]+count end
     if bestn==#group*9 then break end
    end
   end
   if bestn<#group*9 then Search(index+1,n)end
  end
  Search(1,0)
  for _,m in ipairs(best)do local p,r=m.placement,m.recipe;local ti=p.indices[1]
   for k,count in pairs(r.needs)do remaining[k]=remaining[k]-count end
   for s=1,9 do board[(ti-1)*9+s]=r.map[p.cells[s]]or false end
   modules[#modules+1]={placement=p,recipe=r}
  end
  report.added=report.added+bestn
  if yieldfn then yieldfn()end
 end end
 return board,modules,report
end
return M
