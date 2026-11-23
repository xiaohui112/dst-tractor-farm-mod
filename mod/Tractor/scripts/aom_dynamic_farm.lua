-- 原版定义上的逐格互补巨大化计划；不读取当前土壤肥力。
local M={MAX_TILES=64}
local owner
local budgetFrame,budgetSpent=nil,0
local paused={}
local cache,cacheOrder={},{}
local function Copy(v)if type(v)~="table"then return v end;local out={};for k,x in pairs(v)do out[k]=Copy(x)end;return out end
local Registry=require('aom_farm_registry')
local Seed=require('aom_seed_strategy')
local Layout=require('aom_seed_layout')
local Packing=require('aom_seed_packing')
local Neighbors=require('aom_farm_neighbors')
local Grid=require('aom_farm_grid')
local Budget=require('aom_plan_budget')
local Mount=require('aom_attachment_mount')
local function WorkTilePosition(inst)
 local x,_,z=Mount.WorkPosition(inst)
 local cx,_,cz=TheWorld.Map:GetTileCenterPoint(x,0,z)
 return cx,cz,x,z
end
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
   local x,y,z=v.Transform:GetWorldPosition();local found
   for s=1,9 do local px,pz=tile.x+((s-1)%3-1)*Grid.SPACING,tile.z+(math.floor((s-1)/3)-1)*Grid.SPACING;if (px-x)^2+(pz-z)^2<=.16 then found=s;break end end
   if not found or out[found] then return nil,'FOREIGN_CROP' end
   if not soil and (not expected or expected[found]~=crop or v.weed_def or v:HasTag('farm_plant_killjoy')or v:HasTag('deadplant') or v.components.health and v.components.health:IsDead() or require('aom_crop_state').IsRotten(v)) then return nil,'FOREIGN_CROP' end
   out[found]={x=x,y=y,z=z,cx=tile.x,cz=tile.z,crop=crop or false,soil=soil}
  elseif v:HasTag('farm_plant') or v:HasTag('weed') or v.prefab=='farm_soil_debris' or (not v:HasTag('NOBLOCK') and not v:HasTag('aom_attachment') and not v:HasTag('player') and not v:HasTag('FX') and (v:HasTag('structure') or v:HasTag('wall') or v:HasTag('tree') or v:HasTag('boulder'))) then return nil,'FOREIGN_CROP' end
 end end
 for s=1,9 do if not out[s] then return nil,'NEED_PLOW' end end
 return out
end
function M.Validate(b,yieldfn,defer_spatial)
 if type(b)~='table' or b.dynamic~=true or type(b.tiles)~='table' or #b.tiles<1 or (b.strategy~='GIANT_TEMPLATE' and #b.tiles>M.MAX_TILES) or type(b.slots)~='table' or #b.slots~=#b.tiles*9 then return false end
 local defs=Defs();local seen={};local total=0
 for ti,t in ipairs(b.tiles) do
  if type(t)~='table' or not Number(t.x) or not Number(t.z) or seen[Key(t.x,t.z)] then return false end
  seen[Key(t.x,t.z)]=true
  local planted=0
  for s=1,9 do local p=b.slots[(ti-1)*9+s]
   if type(p)~='table' or not Number(p.x) or not Number(p.z) or not Number(p.y or 0)or p.cx~=t.x or p.cz~=t.z then return false end
   local x,z=t.x+((s-1)%3-1)*Grid.SPACING,t.z+(math.floor((s-1)/3)-1)*Grid.SPACING
   if (p.x-x)^2+(p.z-z)^2>.16 then return false end
   if p.crop then planted=planted+1 end
   if p.crop and (not defs[p.crop] or not defs[p.crop].good_seasons or not defs[p.crop].good_seasons[b.season]) then return false end
  end
  if planted>(TUNING.FARM_PANT_OVERCROWDING_MAX_PLANTS or 10) then return false end
  if yieldfn then yieldfn()end
 end
 local board={};for i,p in ipairs(b.slots)do board[i]=p.crop or false;if p.crop then total=total+1 end end
 -- 存档加载不假设农田实体已恢复；开工前必须重新扫描并走原版空间校验。
 if not defer_spatial then
  Neighbors.Clear(b.slots)
  local geometry=Layout.Geometry(b.tiles,b.slots,defs,yieldfn,b.strategy=='GIANT_TEMPLATE')
  if not Layout.Valid(board,geometry,yieldfn)then return false end
 end
 if b.nutrient_balanced then
  local board={};for i,p in ipairs(b.slots) do board[i]=p.crop end
  if not require('aom_seed_balance').Board(board,defs,b.strategy=='GIANT_TEMPLATE',yieldfn) then return false end
 end
 if b.strategy=='GIANT_TEMPLATE' then
  local board={};for i,p in ipairs(b.slots)do board[i]=p.crop or false end
  if not require('aom_seed_template_data').Validate(board,b.construction and b.construction.modules,b.tiles,b.season,yieldfn)then return false end
 end
 return total>0,total
end
local function PitKey(p)return string.format('%.17g,%.17g,%.17g',p.x,p.y or 0,p.z)end
local function InputKey(slots,counts,season,strategy,template_id)
 local defs=Defs();local crops=Layout.Crops(counts,defs,season)
 local signature={Grid.VERSION,Neighbors.VERSION,season,strategy or 'GIANT',template_id or '',require('aom_seed_catalog').version}
 for _,k in ipairs(crops)do
  local d=defs[k];signature[#signature+1]=k..':'..counts[k]..':'..(d.family_min_count or 4)..':'..(d.family_check_dist or 4)
  signature[#signature+1]=table.concat(require('aom_seed_balance').Vector(d)or {},',')
 end
 local points={};for i,p in ipairs(slots)do if i%128==0 then Yield()end;points[#points+1]=string.format('%.17g,%.17g,%.17g,%.17g,%.17g',p.x,p.y or 0,p.z,p.cx,p.cz)end;table.sort(points);for _,v in ipairs(points)do signature[#signature+1]=v end
 signature[#signature+1]=tostring(GetFarmTillSpacing and GetFarmTillSpacing()or 1.25)..':'..tostring(TUNING.FARM_PANT_OVERCROWDING_MAX_PLANTS or 10)
 return table.concat(signature,'|')
end
local function Solve(tiles,slots,counts,season,trace,strategy,task,template_id)
 strategy=strategy=="GIANT_TEMPLATE" and "GIANT_TEMPLATE" or "GIANT"
 if trace then trace:Stage("crop_filter")end
 local defs=Defs();local crops=Layout.Crops(counts,defs,season)
 if trace then trace:Context({season=season,seasonal_crop_kinds=#crops})end
 if #crops==0 then task.quantity_seconds=0;task.arrangement_seconds=0;task.phase='done';task.last_report={total=0,upper=0,optimal=true,quantity_seconds=0,arrangement_seconds=0};return nil,'MISSING_SEEDS' end
 local key=InputKey(slots,counts,season,strategy,template_id);local saved=cache[key];task.input_key=key
 local board,details
 if saved then
  board={};for i,p in ipairs(slots)do board[i]=saved.points[PitKey(p)]or false end;details=Copy(saved.details);details.quantity_seconds=0;details.arrangement_seconds=0;details.template_prepare_seconds=0;details.template_select_seconds=0;details.cache_hit=true
  local tile_lookup={};for i,t in ipairs(tiles)do tile_lookup[t.x..':'..t.z]=i end
  for _,m in ipairs(details.modules or {})do
   local spec=require('aom_seed_template_data').Spec(m.id)
   if spec then for _,v in ipairs(spec.variants)do if v.symmetry==m.symmetry then
    m.tiles={};for dz=0,v.h-1 do for dx=0,v.w-1 do
     m.tiles[#m.tiles+1]=tile_lookup[(m.origin.x+dx*4)..':'..(m.origin.z+dz*4)]
    end end
   end end end
  end
  task.last_report=details;task.quantity_seconds=0;task.arrangement_seconds=0;task.phase='done'
  if trace then trace:Stage('cache_hit');trace:Context({cache_hit=true})end
 else
  if strategy=="GIANT_TEMPLATE" then
   board,details=require('aom_seed_templates').Build(crops,counts,tiles,slots,defs,Yield,{trace=trace,task=task,template_id=template_id})
  else board,details=Packing.Balanced(crops,counts,tiles,slots,defs,Yield,trace,task)end
  if board and (details.optimal or strategy=="GIANT_TEMPLATE") then
   local points={};for i,p in ipairs(slots)do points[PitKey(p)]=board[i]end
   cache[key]={points=points,details=Copy(details)};cacheOrder[#cacheOrder+1]=key
   if #cacheOrder>8 then cache[table.remove(cacheOrder,1)]=nil end
  end
 end
 if not board then return nil,details.invalid_geometry and 'NEED_PLOW' or details.upper==0 and 'NO_BALANCED_COMBO' or 'NO_FAMILY' end
 if trace then trace:Stage("plan_materialize")end
 for i,k in ipairs(board) do slots[i].crop=k;slots[i].index=i end
 local b={dynamic=true,version=4,strategy=strategy,season=season,tiles=tiles,slots=slots,completed={},done=0,total=details.total,
  upper=details.upper,relaxed_upper=details.relaxed_upper,optimal=details.optimal==true,confirmed=true,automatic=true,nutrient_balanced=true,
  arrangement=details.arrangement,construction=details}
 if trace then trace:Stage("final_validation")end
 if not M.Validate(b,Yield) then return nil,'NO_FAMILY' end
 if strategy=='GIANT_TEMPLATE' then require('aom_template_preview').Prepare(b,Yield)end
 return b
end
function M.Gather(inst,cx,cz,trace)
 if trace then trace:Stage("field_scan")end
 -- 索引是缓存，重启后仍按真实九宫格恢复连通范围；无效地皮不作为桥梁。
 local queue={{x=cx,z=cz}};local seen={[Key(cx,cz)]=true};local usable,slots={},{}
 local i=1
 while i<=#queue do
  local tile=queue[i];i=i+1
  local points,why=M.Scan(tile)
  if points then
   if inst._seed_strategy~='GIANT_TEMPLATE' and #usable>=M.MAX_TILES then return nil,'FARM_TOO_LARGE' end
   usable[#usable+1]=tile;Registry.Record(TheWorld,tile.x,tile.z)
   for _,p in ipairs(points) do slots[#slots+1]=p end
   for _,offset in ipairs({{0,-4},{-4,0},{4,0},{0,4}}) do
    local x,z=tile.x+offset[1],tile.z+offset[2];local key=Key(x,z)
    if not seen[key] then seen[key]=true;queue[#queue+1]={x=x,z=z} end
   end
  elseif tile.x==cx and tile.z==cz then return nil,why end
  Yield()
 end
 if trace then
  local centres={};for _,tile in ipairs(usable)do centres[#centres+1]=string.format('%.3f,%.3f',tile.x,tile.z)end
  trace:Context({valid_tiles=#usable,soil_slots=#slots,scan_attempts=i-1,tile_centres=table.concat(centres,'|')})
  trace:Stage("inventory")
 end
 local counts=inst.components.aom_attachment_store:CountSeedsByCrop(Seed.GetCropOfSeedItem)
 if trace then
  local stock={};for k,n in pairs(counts)do stock[#stock+1]=k..':'..n end;table.sort(stock)
  trace:Context({seed_stock=table.concat(stock,','),seed_item_total=inst.components.aom_attachment_store:GetSeedCount()})

 end
 return usable,slots,counts
end
function M.Build(inst,cx,cz,trace)
 local task={strategy=inst._seed_strategy or 'GIANT',phase='scan'};inst._aom_planning_task=task
 local tiles,slots,counts=M.Gather(inst,cx,cz,trace)
 if not tiles then return nil,slots end
 return Solve(tiles,slots,counts,TheWorld.state.season,trace,inst._seed_strategy,task,inst._aom_template_id)
end
local function CurrentKey(inst,cx,cz)
 local tiles,slots,counts=M.Gather(inst,cx,cz)
 return tiles and InputKey(slots,counts,TheWorld.state.season,inst._seed_strategy=="GIANT_TEMPLATE" and "GIANT_TEMPLATE" or "GIANT",inst._aom_template_id)or nil
end
function M.Targets(inst,cx,cz)
 local b=inst._block
 if b.strategy=='GIANT_TEMPLATE' then return M.TemplateTargets(inst,cx,cz)end
 if b.season~=TheWorld.state.season then return nil,'SEASON_CHANGED' end
 local counts=inst.components.aom_attachment_store:CountSeedsByCrop(Seed.GetCropOfSeedItem)
 local remaining,targets={},{};local done=0;local current={};local moved=false
 for ti,tile in ipairs(b.tiles) do
  local expected={};for s=1,9 do expected[s]=b.slots[(ti-1)*9+s].crop end
  local points,reason=M.Scan(tile,expected);if not points then return nil,reason end
  for s,p in ipairs(points) do local i=(ti-1)*9+s;local plan=b.slots[i]
   if (p.x-plan.x)^2+(p.z-plan.z)^2>.04 then return nil,'NO_FAMILY' end
   if p.x~=plan.x or p.z~=plan.z or (p.y or 0)~=(plan.y or 0)then moved=true end
   current[i]={x=p.x,y=p.y,z=p.z,cx=p.cx,cz=p.cz,crop=plan.crop or false}
   if plan.crop then
    if not p.soil then b.completed[i]=true elseif b.completed[i] then return nil,'PLANT_MISSING' end
    if b.completed[i] then done=done+1 else remaining[plan.crop]=(remaining[plan.crop] or 0)+1;if tile.x==cx and tile.z==cz then targets[#targets+1]=plan end end
   end
  end
 end
 if moved or b._native_needs_validation then
  if not M.Validate({dynamic=true,tiles=b.tiles,slots=current,season=b.season,nutrient_balanced=b.nutrient_balanced})then return nil,'NO_FAMILY' end
  for i,p in ipairs(current)do b.slots[i].x=p.x;b.slots[i].y=p.y;b.slots[i].z=p.z end
  b._native_needs_validation=nil;if moved then b.optimal=false end
 end
 b.done=done
 for k,n in pairs(remaining) do if (counts[k] or 0)<n then return nil,'MISSING_SEEDS' end end
 if #targets==0 then return nil,done==b.total and 'COMPLETE' or 'NEXT_TILE' end
 return targets
end
function M.TemplateTargets(inst,cx,cz)
 local b=inst._block
 if b.season~=TheWorld.state.season then return nil,'SEASON_CHANGED' end
 local Preview=require('aom_template_preview');local index=Preview.Prepare(b)
 local module=index.bytile[cx..':'..cz];local targets={}
 local current,tiles,board={}, {},{}
 local scan_tiles=module and module.tiles or {};local focus={}
 if module and module.field_family then
  -- 同族可以跨模块；只重扫覆盖同族半径的邻域，工作量不随全田扩大。
  local radius=0;local defs=Defs()
  for _,i in ipairs(module.indices)do local k=b.slots[i].crop
   if k then radius=math.max(radius,defs[k].family_check_dist or 4)end
  end
  local reach=math.ceil((radius+2*Grid.SPACING+.4)/4);scan_tiles={}
  for dz=-reach,reach do for dx=-reach,reach do
   local ti=index.tiles[(cx+dx*4)..':'..(cz+dz*4)]
   if ti then scan_tiles[#scan_tiles+1]=ti end
  end end
 end
 if module then for _,ti in ipairs(scan_tiles)do
  local tile=b.tiles[ti];local expected={}
  for s=1,9 do expected[s]=b.slots[(ti-1)*9+s].crop end
  local points,why=M.Scan(tile,expected);if not points then return nil,why end
  tiles[#tiles+1]=tile
  for s,p in ipairs(points)do local i=(ti-1)*9+s;local planned=b.slots[i]
   if (p.x-planned.x)^2+(p.z-planned.z)^2>.04 then return nil,'NO_FAMILY' end
   current[#current+1]=p;board[#board+1]=planned.crop or false
   if tile.x==cx and tile.z==cz then focus[#focus+1]=#current end
   if planned.crop then
    if not p.soil then Preview.Complete(b,i)elseif b.completed[i]then return nil,'PLANT_MISSING' end
    if not b.completed[i] and tile.x==cx and tile.z==cz then targets[#targets+1]=planned end
   end
  end
 end end
 if module then
  local geometry=Layout.Geometry(tiles,current,Defs(),nil,true);geometry.balanced=true;geometry.nutrients_only=true
  if module.field_family then
   local Data=require('aom_seed_template_data')
   if not Data.StructuralValid(board,geometry)or not Data.FamilyValid(board,geometry,focus)then return nil,'NO_FAMILY' end
  elseif not Layout.Valid(board,geometry)then return nil,'NO_FAMILY' end
 end
 local stock=inst.components.aom_attachment_store:CountSeedsByCrop(Seed.GetCropOfSeedItem)
 for k,n in pairs(index.remaining)do if (stock[k]or 0)<n then return nil,'MISSING_SEEDS' end end
 if #targets==0 then return nil,b.done==b.total and 'COMPLETE'or 'NEXT_TILE' end
 return targets
end
function M.Cancel(inst,reason)
 if owner==inst then owner=nil end
 if reason=='WORK_STOPPED' and inst._aom_dynamic_job and inst._aom_job_key then
  inst._aom_suspended_job=inst._aom_dynamic_job;inst._aom_dynamic_job=nil
  paused[#paused+1]=setmetatable({inst},{__mode='v'})
  if #paused>4 then local old=table.remove(paused,1)[1];if old and old~=inst and old._aom_suspended_job then M.Cancel(old,'PAUSED_CACHE_EVICTED')end end
  return
 end
 require('aom_plan_timing').Cancel(inst,reason)
 inst._aom_dynamic_job=nil;inst._aom_suspended_job=nil;inst._aom_preview_plan=nil;inst._aom_background=nil
end
function M.Start(inst,cx,cz,background)
 if not background and owner and owner~=inst and owner._aom_background then M.Cancel(owner,'WORK_STOPPED')end
 local template=inst._seed_strategy=='GIANT_TEMPLATE'
 local key=not template and CurrentKey(inst,cx,cz)or nil
 local same=template and inst._aom_job_strategy=='GIANT_TEMPLATE' and inst._aom_job_template_id==inst._aom_template_id or key and key==inst._aom_job_key
 if same and (inst._aom_suspended_job or inst._aom_dynamic_job and inst._aom_background)then
  inst._aom_dynamic_job=inst._aom_suspended_job or inst._aom_dynamic_job;inst._aom_suspended_job=nil
  inst._aom_background=background or false
  if not background and inst._aom_plan_request then
   if inst._aom_plan_trace then inst._aom_plan_trace.request_wall=inst._aom_plan_request.wall end
   inst._aom_plan_request=nil
  end
  if inst._aom_plan_trace then inst._aom_plan_trace.quiet=background;inst._aom_plan_trace:Context({tick_cpu_budget_ms=Budget.Milliseconds(background)})end
  if not inst._aom_job_scheduled then inst._aom_job_scheduled=true;inst:DoTaskInTime(FRAMES or 1/30,inst._aom_job_tick)end
  return
 end
 M.Cancel(inst,'REPLACED');inst._aom_job_key=key or (template and 'template-pending'or nil);inst._aom_job_strategy=inst._seed_strategy;inst._aom_job_template_id=inst._aom_template_id;inst._aom_background=background or false
 local trace=require('aom_plan_timing').New(inst,cx,cz,background);inst._aom_plan_trace=trace
 local co=coroutine.create(function()
  local b,why=M.Build(inst,cx,cz,trace)
  if template and b and CurrentKey(inst,cx,cz)~=inst._aom_planning_task.input_key then return nil,'INPUT_CHANGED' end
  return b,why
 end);inst._aom_dynamic_job=co
 local function Tick()
  if inst._aom_dynamic_job~=co then
   if inst._aom_suspended_job==co then inst._aom_job_scheduled=false end
   if owner==inst and not inst._aom_dynamic_job then owner=nil end;return
  end
  inst._aom_job_scheduled=false
  if inst.IsValid and not inst:IsValid() or inst._attachment_type~='seeder' or not inst._aom_background and (not Seed.IsGiant(inst._seed_strategy) or not inst._working) then
   M.Cancel(inst,'STATE_CHANGED');return
  end
  -- 共享模块有阶段状态；世界内串行推进规划任务，防止多车叠加预算或污染上下文。
  if owner and owner~=inst then inst._aom_job_scheduled=true;inst:DoTaskInTime(FRAMES or 1/30,Tick);return end
  local frame=GetTick and GetTick()or nil
  if frame~=budgetFrame then budgetFrame,budgetSpent=frame,0 end
  local allowance=Budget.Milliseconds(inst._aom_background)/1000
  if frame and budgetSpent>=allowance then inst._aom_job_scheduled=true;inst:DoTaskInTime(FRAMES or 1/30,Tick);return end
  local available=frame and allowance-budgetSpent or allowance
  owner=inst
  trace:TickBegin()
  local sliceStart=os.clock()
  local function Finish(reason)
   if frame then budgetSpent=budgetSpent+os.clock()-sliceStart end
   trace:TickEnd(reason)
  end
  M._yield=coroutine.yield
  local ok,b,why
  local started=os.clock();local yielded_for="resume_limit"
  for _=1,1024 do
   trace:ResumeBegin(os.clock())
   ok,b,why=coroutine.resume(co)
   local resumed_at=os.clock();trace:ResumeEnd(resumed_at)
   if not ok or coroutine.status(co)=='dead' then break end
   if resumed_at-started>=available then yielded_for="cpu_budget";break end
   if inst._aom_dynamic_job~=co then M._yield=nil;Finish('cancelled');return end
  end
  M._yield=nil
  if not ok then inst._aom_dynamic_error=tostring(b);b=nil;why='FAILED';trace:Context({error=inst._aom_dynamic_error})end
  if not ok or coroutine.status(co)=='dead' then
   inst._aom_dynamic_job=nil;owner=nil
   if b and key and CurrentKey(inst,cx,cz)~=key then
    Finish('input_changed');trace:Complete('cancelled','INPUT_CHANGED');inst._aom_background=nil
    if inst._working then M.Start(inst,cx,cz)end
    return
   end
   if inst._aom_background then
    inst._aom_background=nil;inst._aom_prepared_key=key
    Finish('complete');trace:Complete(b and 'prepared' or 'failed',why,b);return
   end
   if b then
    trace:Stage('plan_commit')
    inst._block=b;inst._aom_plan_outdated=nil
    require('aom_block_plan').Sync(inst,trace)
    trace:Stage('completion_message')
    require('aom_work_status').Set(inst,'PLAN_READY')
    local construction=b.construction or {}
    trace:Context({plan_payload_bytes=inst._plan_net and #inst._plan_net:value() or 0,
     quantity_active_cpu_ms=string.format('%.3f',(construction.quantity_seconds or 0)*1000),
     arrangement_active_cpu_ms=string.format('%.3f',(construction.arrangement_seconds or 0)*1000)})
    Finish('complete');trace:Complete('complete',nil,b)
    inst._aom_preview_plan=b;trace:Stage('preview_wait')
    inst:DoTaskInTime(2,function()
     if inst.IsValid and not inst:IsValid() then M.Cancel(inst,'ENTITY_REMOVED');return end
     if inst._aom_preview_plan~=b then return end
     inst._aom_preview_plan=nil
     if inst._block~=b or not inst._working or inst._attachment_type~='seeder' or not Seed.IsGiant(inst._seed_strategy) then
      M.Cancel(inst,'STATE_CHANGED');return
     end
     local cx,cz,x,z=WorkTilePosition(inst)
     for _,tile in ipairs(b.tiles)do
      if tile.x==cx and tile.z==cz then
       trace:RunBegin();trace:Stage('sow_dispatch')
       require('aom_drive').WorkTile(inst,cx,cz,x,z)
       trace:RunEnd()
       return
      end
     end
     trace:Stage('await_sow_tile')
    end)
    return
   else inst._aom_dynamic_reason=why end
   Finish('failed');trace:Complete('failed',why)
   if template and why=='INPUT_CHANGED' and inst._working then M.Start(inst,cx,cz);return end
   if inst._working then
    local cx,cz,x,z=WorkTilePosition(inst)
    if cx and cz then require('aom_drive').WorkTile(inst,cx,cz,x,z)end
   end
  else
   Finish(yielded_for)
   inst._aom_job_scheduled=true;inst:DoTaskInTime(FRAMES or 1/30,Tick)
  end
 end
 inst._aom_job_tick=Tick;inst._aom_job_scheduled=true
 inst:DoTaskInTime(FRAMES or 1/30,Tick)
end
-- 仅在实际游戏中、骑乘空闲且目标田明确时预计算。稳定两次采样才启动。
function M.PrepareNearby(inst)
 if inst._seed_strategy=='GIANT_TEMPLATE' then return end
 if not GetTimeRealSeconds or not inst._rider or inst._working or inst._block or inst._attachment_type~='seeder' then return end
 local now=GetTimeRealSeconds();if now<(inst._aom_prepare_after or 0)then return end;inst._aom_prepare_after=now+2
 local x,z=WorkTilePosition(inst)
 local key=x and z and CurrentKey(inst,x,z)
 if key~=inst._aom_candidate_key then
  inst._aom_candidate_key=key
  if inst._aom_background then M.Cancel(inst,'BACKGROUND_INPUT_CHANGED')end
  return
 end
 if not key or key==inst._aom_prepared_key or inst._aom_dynamic_job or owner then return end
 if inst._aom_suspended_job and not inst._aom_background then return end
 M.Start(inst,x,z,true)
end
return M
