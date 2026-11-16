-- 无状态的静态候选与完整模版验收；两种策略可共用，不保存任务结果。
local M={}
local Catalog=require('aom_seed_catalog')
local Layout=require('aom_seed_layout')
local Balance=require('aom_seed_balance')
M.Catalog=Catalog
local function Point(x,z)return x..':'..z end
local function Fits(recipe,stock)
 for k,n in pairs(recipe.needs)do if (stock[k]or 0)<n then return false end end
 return true
end
M.Fits=Fits
function M.Prepare(crops,stock,tiles,slots,defs,yieldfn,options)
 options=options or {};local available={};for _,k in ipairs(crops)do available[k]=true end
 local lookup={};for i,t in ipairs(tiles)do lookup[Point(t.x,t.z)]=i end
 local banks={}
 for _,spec in ipairs(Catalog.templates)do if not options.template_id or options.template_id==spec.id then
  local recipes={}
  for _,r in ipairs(spec.recipes)do
   local valid=Fits(r,stock)
   for _,k in pairs(r.map)do if not available[k]then valid=false end end
   if valid then recipes[#recipes+1]=r end
  end
  if #recipes>0 then banks[#banks+1]={spec=spec,recipes=recipes}end
 end end
 local placements={};local validations=0;local geometry_builds=0
 for _,t in ipairs(tiles)do local geometries,checked={},{};for _,bank in ipairs(banks)do for _,v in ipairs(bank.spec.variants)do
  local indices,subtiles,subslots={}, {},{};local fits=true
  for dz=0,v.h-1 do for dx=0,v.w-1 do
   local ti=lookup[Point(t.x+dx*4,t.z+dz*4)]
   if not ti then fits=false else
    indices[#indices+1]=ti;subtiles[#subtiles+1]=tiles[ti]
    for s=1,9 do subslots[#subslots+1]=slots[(ti-1)*9+s]end
   end
  end end
  if fits then
   local accepted={}
   local geometry_key=Point(t.x,t.z)..':'..v.w..':'..v.h
   local geometry=geometries[geometry_key]
   if not geometry then geometry=Layout.Geometry(subtiles,subslots,defs);geometry.balanced=true;geometry.nutrients_only=true;geometries[geometry_key]=geometry;geometry_builds=geometry_builds+1 end
   for _,r in ipairs(bank.recipes)do
    local signature={}
    for _,role in ipairs({'A','B','C','D'})do local k=r.map[role];if k then local d=defs[k];signature[#signature+1]=(d.family_min_count or 4)..':'..(d.family_check_dist or 4)..':'..table.concat(Balance.Vector(d),',')end end
    local key=geometry_key..':'..table.concat(v.cells)..':'..table.concat(signature,'|');local valid=checked[key]
    if valid==nil then
     local board={};for i,role in ipairs(v.cells)do board[i]=r.map[role]or false end
     valid=Layout.Valid(board,geometry);checked[key]=valid;validations=validations+1
    end
    if valid then accepted[#accepted+1]=r end
   end
   if #accepted>0 then placements[#placements+1]={id=bank.spec.id,symmetry=v.symmetry,origin={x=t.x,z=t.z},indices=indices,cells=v.cells,recipes=accepted,n=bank.spec.total,area=#indices}end
  end
  if yieldfn then yieldfn()end
 end end end
 table.sort(placements,function(a,b)
  if a.id~=b.id then return a.id<b.id end
  if a.symmetry~=b.symmetry then return a.symmetry<b.symmetry end
  if a.origin.z~=b.origin.z then return a.origin.z<b.origin.z end
  return a.origin.x<b.origin.x
 end)
 return placements,validations,geometry_builds
end
function M.Validate(board,modules,tiles,season,yieldfn)
 local lookup={};for i,t in ipairs(tiles)do lookup[Point(t.x,t.z)]=i end
 local expected,occupied={},{}
 for i=1,#tiles*9 do expected[i]=false end
 for _,m in ipairs(modules or {})do
  local spec;for _,s in ipairs(Catalog.templates)do if s.id==m.id then spec=s;break end end
  if not spec or not m.origin or type(m.crops)~='table' then return false end
  local variant;for _,v in ipairs(spec.variants)do if v.symmetry==m.symmetry then variant=v;break end end
  if not variant then return false end
  local recipe
  for _,r in ipairs(spec.recipes)do
   local same=true;for role,k in pairs(r.map)do if m.crops[role]~=k then same=false end end
   for role in pairs(m.crops)do if not r.map[role]then same=false end end
   if same then for _,s in ipairs(r.seasons)do if s==season then recipe=r end end end
  end
  if not recipe then return false end
  if yieldfn then yieldfn()end
  local j=0
  for dz=0,variant.h-1 do for dx=0,variant.w-1 do
   local ti=lookup[Point(m.origin.x+dx*4,m.origin.z+dz*4)]
   if not ti or occupied[ti]then return false end;occupied[ti]=true
   for s=1,9 do j=j+1;expected[(ti-1)*9+s]=recipe.map[variant.cells[j]]or false end
  end end
 end
 for i=1,#expected do if (board[i]or false)~=expected[i]then return false end end
 return true
end
return M
