-- 多配比连续区域构造。只输出完整校验的上界见证；失败不排除全局解。
local M={}
function M.Find(crops,stock,tiles,slots,defs,patterns,target,yieldfn,on_candidate)
 if #tiles<6 then return nil end
 local Layout=require('aom_seed_layout');local Balance=require('aom_seed_balance')
 local vectors={};for c,k in ipairs(crops)do vectors[c]=Balance.Vector(defs[k])end
 local whole=Layout.Geometry(tiles,slots,defs,yieldfn);whole.balanced=true
 for direction=0,3 do
  local order={};for i=1,#tiles do order[i]=i end
  table.sort(order,function(a,b)
   local x,z=tiles[a].x,tiles[a].z;local u,v=tiles[b].x,tiles[b].z
   if direction%2==1 then x,z,u,v=z,x,v,u end
   if direction>=2 then x,z,u,v=-x,-z,-u,-v end
   return z~=v and z<v or z==v and x<u
  end)
  local remaining={};for c,k in ipairs(crops)do remaining[c]=stock[k]end
  local board={};for i=1,#slots do board[i]=false end
  local total,at=0,1
  while at<=#order and total<target do
   local run=1
   while at+run<=#order do
    local a,b=tiles[order[at+run-1]],tiles[order[at+run]]
    local straight=direction%2==0 and a.z==b.z and math.abs(a.x-b.x)==4 or direction%2==1 and a.x==b.x and math.abs(a.z-b.z)==4
    if not straight then break end;run=run+1
   end
   local size=run>3 and run%3==1 and 2 or math.min(3,run)
   local subtiles,subslots={},{}
   for j=0,size-1 do local t=order[at+j];subtiles[#subtiles+1]=tiles[t];for s=1,9 do subslots[#subslots+1]=slots[(t-1)*9+s]end end
   local geometry=Layout.Geometry(subtiles,subslots,defs,yieldfn);geometry.balanced=true
   local choices={}
   for pi,p in ipairs(patterns)do
    local fits=p.n*size<=target-total;local cost=0
    for c,n in ipairs(p.counts)do
     if n*size>remaining[c] or n>0 and n*size<(defs[crops[c]].family_min_count or 4)then fits=false;break end
     if n>0 then cost=cost+n/(remaining[c]+1)+(n<(defs[crops[c]].family_min_count or 4)-1 and 100 or 0)end
    end
    if fits then
     local rest={};for c,k in ipairs(crops)do rest[k]=remaining[c]-p.counts[c]*size end
     if Balance.Upper(crops,rest,vectors,(#tiles-at-size+1)*9)<target-total-p.n*size then fits=false end
    end
    if fits then choices[#choices+1]={p=p,cost=cost,pi=pi}end
   end
   table.sort(choices,function(a,b)return a.p.n~=b.p.n and a.p.n>b.p.n or a.p.n==b.p.n and (a.cost~=b.cost and a.cost<b.cost or a.cost==b.cost and a.pi<b.pi)end)
   local found
   for ci,choice in ipairs(choices)do
    if ci>24 then break end
    local cells={};for c,n in ipairs(choice.p.counts)do for _=1,n do cells[#cells+1]=crops[c]end end
    while #cells<9 do cells[#cells+1]=false end
    local placed
    for ci2,candidate in ipairs(Layout.Candidates(cells,yieldfn))do
     if ci2>16 then break end
     local sub={};for j=1,size do for s=1,9 do sub[#sub+1]=candidate.cells[s]end end
     if Layout.Valid(sub,geometry)then placed=sub;break end
     if yieldfn then yieldfn()end
    end
    if not placed then
     local names,counts={},{}
     for c,n in ipairs(choice.p.counts)do if n>0 then names[#names+1]=crops[c];counts[crops[c]]=n*size end end
     local sub,proof=require('aom_seed_exact').Maximize(names,counts,subtiles,subslots,defs,nil,0,choice.p.n*size,yieldfn,{node_limit=256,work_limit=12000})
     if sub and proof.total==choice.p.n*size and Layout.Valid(sub,geometry)then placed=sub end
    end
    if placed then
     for j=0,size-1 do local t=order[at+j];for s=1,9 do board[(t-1)*9+s]=placed[j*9+s]end end
     for c,n in ipairs(choice.p.counts)do remaining[c]=remaining[c]-n*size end
     total=total+choice.p.n*size;found=true
    end
    if found then break end
   end
   at=at+size
   if yieldfn then yieldfn()end
  end
  if total>0 and Layout.Valid(board,whole)then
   if on_candidate then on_candidate(board,total)end
   if total==target then return board end
  end
 end
 return nil
end
return M
