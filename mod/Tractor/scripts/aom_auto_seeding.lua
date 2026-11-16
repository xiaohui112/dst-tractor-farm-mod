-- 自动巨大化入口：新轮次统一动态规划；旧v3模板计划保留坐标续播。
local Block=require("aom_block_plan")
local Seed=require("aom_seed_strategy")
local Crops=require("aom_crop_state")
local M={}
local function Key(x,z)return string.format("%.3f:%.3f",x,z)end
local function Combo(id)
    for _,list in pairs(Block.BLOCKS) do for _,c in ipairs(list) do if c.id==id then return c end end end
end
function M.IsGrid(c)
    if not c or c.reference_only or c.shape~="grid" or #c.not_giant>0 then return false end
    return (c.width==1 or c.width==2) and (c.height==1 or c.height==2)
end
local function HasSeeds(counts,needs)
    for crop,n in pairs(needs) do if (counts[crop] or 0)<n then return false end end
    return true
end
local function Remaining(b,c)
    local needs={}
    for i,p in ipairs(c.slots) do
        if p.crop and not b.completed[i] then needs[p.crop]=(needs[p.crop] or 0)+1 end
    end
    return needs
end
local function Scan(cx,cz)
    local map=TheWorld.Map
    local field={}
    for dx=-1,1 do for dz=-1,1 do
        local x,z=cx+dx*4,cz+dz*4
        local tile={points={}}
        field[Key(x,z)]=tile
        tile.ready=map:GetTileAtPoint(x,0,z)==WORLD_TILES.FARMING_SOIL and map:IsPassableAtPoint(x,0,z)
        if tile.ready then
            for _,v in ipairs(map:GetEntitiesOnTileAtPoint(x,0,z)) do
                if v:IsValid() and not v:HasTag("NOCLICK") and not v:HasTag("INLIMBO") then
                    local crop=type(v.prefab)=="string" and string.match(v.prefab,"^farm_plant_(.+)$")
                    local soil=v.prefab=="farm_soil" and v:HasTag("soil")
                    if soil or crop then
                        local px,_,pz=v.Transform:GetWorldPosition()
                        if crop and (v.weed_def or Crops.IsRotten(v) or v:HasTag("deadplant")
                            or v.components.health and v.components.health:IsDead()) then crop=false end
                        tile.points[#tile.points+1]={x=px,z=pz,crop=crop or false,soil=soil}
                    elseif v:HasTag("farm_plant") or v:HasTag("weed") or v:HasTag("weedplantstress")
                        or v.prefab=="farm_soil_debris" then
                        tile.blocked=true
                    elseif v.prefab~="aom_tractor_chassis" and not v:HasTag("NOBLOCK")
                        and not v:HasTag("aom_attachment") and not v:HasTag("player") and not v:HasTag("FX")
                        and (v:HasTag("structure") or v:HasTag("wall") or v:HasTag("boulder") or v:HasTag("tree")) then
                        tile.blocked=true
                    end
                end
            end
        end
    end end
    return field
end
-- 每个模板格的九个坑（含留空位）都必须存在；允许规则九宫格的轻微坐标差异。
local function Match(b,c,field)
    local slots=Block.WorldSlots(b)
    local used,positions,completed={}, {}, {}
    local done=0
    for i,p in ipairs(slots) do
        local key=Key(p.cx,p.cz)
        local tile=field[key]
        if not tile or not tile.ready then return false,"NEED_PLOW" end
        if tile.blocked then return false,"FOREIGN_CROP" end
        local marks=used[key] or {};used[key]=marks
        local match,best
        for j,v in ipairs(tile.points) do
            local d=(v.x-p.x)^2+(v.z-p.z)^2
            if not marks[j] and d<=(b.positions and .04 or .16) and (not best or d<best) then match,best=j,d end
        end
        if not match then return false,b.completed[i] and "PLANT_MISSING" or "NEED_PLOW" end
        marks[match]=true
        local v=tile.points[match]
        if not v.soil and (not p.crop or p.crop~=v.crop) then return false,"FOREIGN_CROP" end
        if b.completed[i] and v.soil then return false,"PLANT_MISSING" end
        if not v.soil then completed[i]=true;done=done+1 end
        positions[i]={x=v.x,z=v.z}
    end
    for key,marks in pairs(used) do
        for j in ipairs(field[key].points) do if not marks[j] then return false,"FOREIGN_CROP" end end
    end
    -- 使用实际坐标校验同类距离与间距，不能只靠种子总数。
    local defs=require("prefabs/farm_plant_defs").PLANT_DEFS
    local spacing=GetFarmTillSpacing and GetFarmTillSpacing() or TUNING.FARM_TILL_SPACING or 1.25
    for i,p in ipairs(slots) do if p.crop then
        local def=defs[p.crop];local family=0
        for j,q in ipairs(slots) do if q.crop then
            local d=(positions[i].x-positions[j].x)^2+(positions[i].z-positions[j].z)^2
            if i~=j and d<=spacing^2 then return false,"MOUNDS_TOO_CLOSE" end
            if p.crop==q.crop and d<=(def.family_check_dist or 4)^2 then family=family+1 end
        end end
        if family<(def.family_min_count or 4) then return false,"NO_FAMILY" end
    end end
    b.positions=b.positions or positions
    b.completed,b.done=completed,done
    b.automatic,b.confirmed=true,true
    return true
end
function M.GetTargets(inst,cx,cz)
    local season=TheWorld.state.season
    local counts=inst.components.aom_attachment_store:CountSeedsByCrop(Seed.GetCropOfSeedItem)
    local b=inst._block
    if b and inst._aom_preview_plan==b then return nil,"PLAN_READY" end
    local Dynamic=require('aom_dynamic_farm')
    if b and b.dynamic then
        if b.done>=b.total and Dynamic.Scan({x=cx,z=cz}) then
            inst._block=nil;b=nil
        else
            local targets,why=Dynamic.Targets(inst,cx,cz)
            return targets,why=='COMPLETE' and 'NOTHING_TO_DO' or why
        end
    end
    -- v3旧计划只续播，不再用养分平衡模板创建新轮次。
    local c=b and Combo(b.combo_id)
    if b and c and b.done>=c.total then
        local _,tiles=Block.WorldSlots(b)
        if tiles[Key(cx,cz)] and not Dynamic.Scan({x=cx,z=cz}) then return nil,'NOTHING_TO_DO' end
    end
    if b and M.IsGrid(c) and (b.automatic or b.done>0) and b.done<c.total then
        if b.season~=season then return nil,'SEASON_CHANGED' end
        local valid,reason=Block.ValidateCombo(c,season)
        if not valid then return nil,reason end
        local _,tiles=Block.WorldSlots(b)
        if not tiles[Key(cx,cz)] then
            if not HasSeeds(counts,Remaining(b,c)) then return nil,'MISSING_SEEDS' end
            return nil,'NEXT_TILE'
        end
        local matched,why=Match(b,c,Scan(cx,cz))
        if not matched then return nil,why end
        if b.done>=c.total then return M.GetTargets(inst,cx,cz) end
        return Block.GetTargets(inst,season,counts,cx,cz,false)
    end
    if inst._aom_dynamic_reason then local why=inst._aom_dynamic_reason;inst._aom_dynamic_reason=nil;return nil,why end
    if inst._aom_dynamic_job then
        if inst._aom_background then Dynamic.Start(inst,cx,cz)end
        return nil,'PLANNING'
    end
    if inst.DoTaskInTime then Dynamic.Start(inst,cx,cz);return nil,'PLANNING' end
    local plan,why=Dynamic.Build(inst,cx,cz)
    if not plan then return nil,why end
    inst._block=plan;inst._aom_plan_outdated=nil
    return Dynamic.Targets(inst,cx,cz)
end
return M
