-- 原版定义上的逐格互补巨大化计划；不读取当前土壤肥力。
local M={MAX_TILES=64}
local Registry=require('aom_farm_registry')
local Seed=require('aom_seed_strategy')
local Layout=require('aom_seed_layout')
local Packing=require('aom_seed_packing')
local function Key(x,z)return string.format('%.3f:%.3f',x,z)end
local function Number(x)return type(x)=='number' and x==x and math.abs(x)<1000000 end
local function Defs()return require('prefabs/farm_plant_defs').PLANT_DEFS end
local function Yield()if M._yield then M._yield() end end
function M.Scan(tile,expected)
 local map=TheWorld.Map
 if map:GetTileAtPoint(tile.x,0,tile.z)~=WORLD_TILES.FARMING_SOIL or not map:IsPassableAtPoint(tile.x,0,tile.z) then return nil,'NEED_PLOW' end
 local out={}
 for _,v in ipairs(map:GetEntitiesOnTileAtPoint(tile.x,0,tile.z)) do if v:IsValid() and not v:HasTag('NOCLICK') and not v:HasTag('INLIMBO') then
  local soil=v.prefab=='farm_soil' and v:HasTag('soil')
  local crop=type(v.prefab)=='string' and string.match(v.prefab,'^farm_plant_(.+)$')
  if soil or crop then
   local x,_,z=v.Transform:GetWorldPosition();local found
   for s=1,9 do local px,pz=tile.x+((s-1)%3-1)*4/3,tile.z+(math.floor((s-1)/3)-1)*4/3;if (px-x)^2+(pz-z)^2<=.16 then found=s;break end end
   if not found or out[found] then return nil,'FOREIGN_CROP' end
   if not soil and (not expected or expected[found]~=crop or v.weed_def or v:HasTag('deadplant') or v.components.health and v.components.health:IsDead() or require('aom_crop_state').IsRotten(v)) then return nil,'FOREIGN_CROP' end
   out[found]={x=x,z=z,cx=tile.x,cz=tile.z,crop=crop or false,soil=soil}
  elseif v:HasTag('farm_plant') or v:HasTag('weed') or v.prefab=='farm_soil_debris' or (not v:HasTag('NOBLOCK') and not v:HasTag('aom_attachment') and not v:HasTag('player') and not v:HasTag('FX') and (v:HasTag('structure') or v:HasTag('wall') or v:HasTag('tree') or v:HasTag('boulder'))) then return nil,'FOREIGN_CROP' end
 end end
 for s=1,9 do if not out[s] then return nil,'NEED_PLOW' end end
 return out
end
function M.Validate(b)
 if type(b)~='table' or b.dynamic~=true or type(b.tiles)~='table' or #b.tiles<1 or #b.tiles>M.MAX_TILES or type(b.slots)~='table' or #b.slots~=#b.tiles*9 then return false end
 local defs=Defs();local seen={};local total=0
 local spacing=GetFarmTillSpacing and GetFarmTillSpacing() or 1.25
 for ti,t in ipairs(b.tiles) do
  if type(t)~='table' or not Number(t.x) or not Number(t.z) or seen[Key(t.x,t.z)] then return false end
  seen[Key(t.x,t.z)]=true
  local planted=0
  for s=1,9 do local p=b.slots[(ti-1)*9+s]
   if type(p)~='table' or not Number(p.x) or not Number(p.z) or p.cx~=t.x or p.cz~=t.z then return false end
   local x,z=t.x+((s-1)%3-1)*4/3,t.z+(math.floor((s-1)/3)-1)*4/3
   if (p.x-x)^2+(p.z-z)^2>.16 then return false end
   if p.crop then planted=planted+1 end
   if p.crop and (not defs[p.crop] or not defs[p.crop].good_seasons or not defs[p.crop].good_seasons[b.season]) then return false end
  end
  if planted>(TUNING.FARM_PANT_OVERCROWDING_MAX_PLANTS or 10) then return false end
 end
 for i,p in ipairs(b.slots) do if p.crop then
  total=total+1;local family=0;local d=defs[p.crop]
  for j,q in ipairs(b.slots) do if q.crop then local dd=(p.x-q.x)^2+(p.z-q.z)^2
   if i~=j and dd<=spacing^2 then return false end
   if p.crop==q.crop and dd<=(d.family_check_dist or 4)^2 then family=family+1 end
  end end
  if family<(d.family_min_count or 4) then return false end
 end end
 if b.nutrient_balanced then
  local board={};for i,p in ipairs(b.slots) do board[i]=p.crop end
  if not require('aom_seed_balance').Board(board,defs) then return false end
 end
 return total>0,total
end
local function Solve(tiles,slots,counts,season)
 local defs=Defs();local crops=Layout.Crops(counts,defs,season)
 if #crops==0 then Packing.last_report={total=0,upper=0,optimal=true,quantity_seconds=0,arrangement_seconds=0};return nil,'MISSING_SEEDS' end
 local board,details=Packing.Balanced(crops,counts,tiles,slots,defs,Yield)
 if not board then return nil,details.upper==0 and 'NO_BALANCED_COMBO' or 'NO_FAMILY' end
 for i,k in ipairs(board) do slots[i].crop=k;slots[i].index=i end
 local b={dynamic=true,version=4,season=season,tiles=tiles,slots=slots,completed={},done=0,total=details.total,
  upper=details.upper,relaxed_upper=details.relaxed_upper,optimal=details.optimal==true,confirmed=true,automatic=true,nutrient_balanced=true,
  arrangement=details.arrangement,construction=details}
 if not M.Validate(b) then return nil,'NO_FAMILY' end
 return b
end
function M.Build(inst,cx,cz)
 -- 索引是缓存，重启后仍按真实九宫格恢复连通范围；无效地皮不作为桥梁。
 local queue={{x=cx,z=cz}};local seen={[Key(cx,cz)]=true};local usable,slots={},{}
 local i=1
 while i<=#queue do
  local tile=queue[i];i=i+1
  local points,why=M.Scan(tile)
  if points then
   if #usable>=M.MAX_TILES then return nil,'FARM_TOO_LARGE' end
   usable[#usable+1]=tile;Registry.Record(TheWorld,tile.x,tile.z)
   for _,p in ipairs(points) do slots[#slots+1]=p end
   for _,offset in ipairs({{0,-4},{-4,0},{4,0},{0,4}}) do
    local x,z=tile.x+offset[1],tile.z+offset[2];local key=Key(x,z)
    if not seen[key] then seen[key]=true;queue[#queue+1]={x=x,z=z} end
   end
  elseif tile.x==cx and tile.z==cz then return nil,why end
  Yield()
 end
 return Solve(usable,slots,inst.components.aom_attachment_store:CountSeedsByCrop(Seed.GetCropOfSeedItem),TheWorld.state.season)
end
function M.Targets(inst,cx,cz)
 local b=inst._block
 if b.season~=TheWorld.state.season then return nil,'SEASON_CHANGED' end
 local counts=inst.components.aom_attachment_store:CountSeedsByCrop(Seed.GetCropOfSeedItem)
 local remaining,targets={},{};local done=0
 for ti,tile in ipairs(b.tiles) do
  local expected={};for s=1,9 do expected[s]=b.slots[(ti-1)*9+s].crop end
  local points,reason=M.Scan(tile,expected);if not points then return nil,reason end
  for s,p in ipairs(points) do local i=(ti-1)*9+s;local plan=b.slots[i]
   if (p.x-plan.x)^2+(p.z-plan.z)^2>.04 then return nil,'NO_FAMILY' end
   if plan.crop then
    if not p.soil then b.completed[i]=true elseif b.completed[i] then return nil,'PLANT_MISSING' end
    if b.completed[i] then done=done+1 else remaining[plan.crop]=(remaining[plan.crop] or 0)+1;if tile.x==cx and tile.z==cz then targets[#targets+1]=plan end end
   end
  end
 end
 b.done=done
 for k,n in pairs(remaining) do if (counts[k] or 0)<n then return nil,'MISSING_SEEDS' end end
 if #targets==0 then return nil,done==b.total and 'COMPLETE' or 'NEXT_TILE' end
 return targets
end
function M.Start(inst,cx,cz)
 local co=coroutine.create(function()return M.Build(inst,cx,cz)end);inst._aom_dynamic_job=co
 local function Tick()
  if inst._aom_dynamic_job~=co then return end
  if inst.IsValid and not inst:IsValid() or inst._attachment_type~='seeder' or inst._seed_strategy~='GIANT' or not inst._working then inst._aom_dynamic_job=nil;return end
  M._yield=coroutine.yield
  local ok,b,why
  -- 时间额度仅用于让出下一帧，不中止搜索或改变方案选择。
  local started=os.clock()
  for _=1,128 do
   ok,b,why=coroutine.resume(co)
   if not ok or coroutine.status(co)=='dead' then break end
   if os.clock()-started>=.004 then break end
  end
  M._yield=nil
  if not ok then inst._aom_dynamic_error=tostring(b);b=nil;why='FAILED' end
  if not ok or coroutine.status(co)=='dead' then
   inst._aom_dynamic_job=nil
   if b then inst._block=b;inst._aom_plan_outdated=nil else inst._aom_dynamic_reason=why end
   if inst._working then local x,_,z=inst.Transform:GetWorldPosition();x,_,z=TheWorld.Map:GetTileCenterPoint(x,0,z);require('aom_drive').WorkTile(inst,x,z) end
  else inst:DoTaskInTime(FRAMES or 1/30,Tick) end
 end
 inst:DoTaskInTime(FRAMES or 1/30,Tick)
end
return M
