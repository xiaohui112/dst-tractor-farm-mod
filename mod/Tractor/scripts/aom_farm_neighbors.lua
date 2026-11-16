-- 实际坑位的范围关系只由原版 FindEntities 决定；不以 Lua 距离平方二次过滤。
local M={VERSION='native-findentities-1'}
local cached=setmetatable({},{__mode='k'})
-- 前两项对应现场可用坑位过滤；原版 FamilyStressTest 排除 farm_plant_killjoy。
local EXCLUDE={'INLIMBO','NOCLICK','farm_plant_killjoy'}
local function Key(x,y,z)return string.format('%.17g,%.17g,%.17g',x,y or 0,z)end
local function IsPit(v)
 return v:IsValid() and ((v.prefab=='farm_soil' and v:HasTag('soil'))
  or type(v.prefab)=='string' and v.prefab:match('^farm_plant_') and not v.weed_def)
end
function M.Clear(slots)for _,p in ipairs(slots)do cached[p]=nil end end
local function Query(p,radius)
 local key=Key(p.x,p.y,p.z);local saved=cached[p]
 if not saved or saved.key~=key then saved={key=key,ranges={}};cached[p]=saved end
 local found=saved.ranges[radius]
 if not found then
  found={}
  for _,v in ipairs(TheSim:FindEntities(p.x,p.y or 0,p.z,radius,nil,EXCLUDE))do
   if IsPit(v)then local x,y,z=v.Transform:GetWorldPosition();found[Key(x,y,z)]=true end
  end
  saved.ranges[radius]=found
 end
 return found,key
end
function M.Build(slots,defs,yieldfn)
 local radii={[4]=true};local spacing=GetFarmTillSpacing and GetFarmTillSpacing()or 1.25
 radii[spacing]=true
 for _,d in pairs(defs)do radii[d.family_check_dist or 4]=true end
 local lookup={};for i,p in ipairs(slots)do
  local key=Key(p.x,p.y,p.z);lookup[key]=lookup[key]or {};lookup[key][#lookup[key]+1]=i
 end
 local ranges,complete={},true
 for radius in pairs(radii)do
  local rows={};ranges[radius^2]=rows
  for i,p in ipairs(slots)do
   local found,key=Query(p,radius);local row={};rows[i]=row
   if not found[key]then complete=false end
   for position in pairs(found)do for _,j in ipairs(lookup[position]or {})do row[j]=true end end
   if i%32==0 and yieldfn then yieldfn()end
  end
 end
 return ranges,complete
end
function M.Within(geometry,i,j,radius_squared)
 local rows=geometry.ranges[radius_squared]
 return rows and rows[i] and rows[i][j]or false
end
return M
