--[[
	Tractor —— 原版农场动作封装层

	本文件是整个 Mod 的"唯一真相来源"：
	拖拉机的六种挂件，每一个最终都落到这里的一行原版调用上。

	不在这里出现任何"农业数值"：
	- 水分：TheWorld.components.farming_manager:AddSoilMoistureAtPoint(...)
	- 养分：走肥料自身的 fertilizer 组件与 COMPONENT_ACTIONS 的 FERTILIZE 路径
	- 犁地：terraformer:Terraform(pt, doer)（园艺耕地机）+ farmtiller Till（园艺锄）
	- 播种：farmplantable:Plant(soil, planter)（种子用的就是它）
	- 收获：走 HARVEST 的 crops/pickable/... 分发逻辑
	- 铲草：确认 DIG 可作业后调用 workable:WorkedBy(doer, 剩余工作量)

	任何一条原版 API 改名，只需要改这一个文件。
]]

-- 返回值为 "ok" / nil, reason
local AOMFarmWork = {}

-- 原版杂草也带 farm_plant 标签；真正作物的组件/定义优先，兼容误加 weed 标签。
local function IsFarmPlant(target)
    if target.components.farmplantstress~=nil or target.plant_def~=nil then return true end
    if target.weed_def~=nil or target:HasTag("weedplantstress") then return false end
    return (type(target.prefab)=="string" and string.sub(target.prefab,1,11)=="farm_plant_")
        or target:HasTag("farm_plant")
end

-- 该作物是否可收获
-- 原版 farm plant 的收获走 pickable：CanBePicked / Pick
-- （核对 components/pickable.lua:382 CanBePicked、:535 Pick）
local function CanHarvestPlant(target)
	if not IsFarmPlant(target) then
		return false
	end
	local pickable = target.components.pickable
	return pickable ~= nil and pickable:CanBePicked()
end

---------------------------------------------------------------------------
-- 工具：点 -> 地皮中心；地皮内实体查找
---------------------------------------------------------------------------

-- 把一个世界坐标点吸附到它所在地皮的中心（防止拖拉机在格子边缘作业）
function AOMFarmWork.GetTileCenter(x, y, z)
	local map = TheWorld.Map
	local cx, _, cz = map:GetTileCenterPoint(x, y, z)
	if cx == nil then
		cx, cz = x, z
	end
	return cx, y, cz
end

local function SameTile(target,x,z)
    local sx,_,sz=target.Transform:GetWorldPosition()
    local cx,_,cz=AOMFarmWork.GetTileCenter(sx,0,sz)
    local tx,_,tz=AOMFarmWork.GetTileCenter(x,0,z)
    return math.abs(cx-tx)<.01 and math.abs(cz-tz)<.01
end

-- 找某点附近半径 r 内所有"空土坑" farm_soil
-- 原版 farm_soil.lua：可再种的空坑带 tag "soil"，被占用/崩塌后加 "NOCLICK" "NOBLOCK"
local function FindEmptySoil(x, y, z, r)
	local ents = TheSim:FindEntities(x, y, z, r, { "soil" }, { "NOCLICK", "INLIMBO" })
	local result = {}
	for _, v in ipairs(ents) do
		if v.prefab == "farm_soil" and v:IsValid() then
            local sx, _, sz = v.Transform:GetWorldPosition()
            local cx, _, cz = AOMFarmWork.GetTileCenter(sx, 0, sz)
            local tx, _, tz = AOMFarmWork.GetTileCenter(x, 0, z)
            if math.abs(cx-tx)<.01 and math.abs(cz-tz)<.01 then
                table.insert(result, v)
            end
		end
	end
	return result
end

-- 找某点附近半径 r 内所有可收获的"农作物"（不碰浆果丛等其它植物）
local function FindMaturePlants(x, y, z, r)
	local ents = TheSim:FindEntities(x, y, z, r, nil, { "NOCLICK", "INLIMBO" })
	local result = {}
	for _, v in ipairs(ents) do
		if v:IsValid() and SameTile(v,x,z) and CanHarvestPlant(v) then
			table.insert(result, v)
		end
	end
	return result
end

-- 作物保护优先于杂草名/标签，避免其他 Mod 给作物添加 weed 标签后被误铲。
local function IsDebris(v)
    return not IsFarmPlant(v) and (v.prefab == "farm_soil_debris"
        or (type(v.prefab)=="string" and string.sub(v.prefab,1,5)=="weed_")
        or v:HasTag("weed"))
end

-- 找某点附近半径 r 内的杂草与园艺残渣
local function FindWeedsAndDebris(x, y, z, r)
	local ents = TheSim:FindEntities(x, y, z, r, nil, { "NOCLICK", "INLIMBO", "player", "INV_MISC" })
	local result = {}
	for _, v in ipairs(ents) do
		-- 原版杂草 prefab：weed_forgetmelots / weed_firenettle / weed_tillweed / weed_ivy
		-- 原版残渣 prefab：farm_soil_debris（两者 workable 动作都是 DIG）
		if v:IsValid() and SameTile(v,x,z) and IsDebris(v) then
			table.insert(result, v)
		end
	end
	return result
end

---------------------------------------------------------------------------
-- 1) 开垦机：对应园艺耕地机（铺地皮）+ 园艺锄（挖坑）+ 铲子（清残渣杂草）
---------------------------------------------------------------------------

-- 一格4×4，半对角约2.828；先覆盖边角，再按所属地块过滤。
local FIELD_RADIUS = 2.9
local SOIL_MATCH_SQ = .0001
-- 规划器也用同一判定：只自动铲除原版 DIG 路径可处理的杂物。
function AOMFarmWork.IsClearableDebris(v)
    if not v:IsValid() or not IsDebris(v) then return false end
    local w=v.components.workable
    return w~=nil and w:GetWorkAction()==ACTIONS.DIG and w:CanBeWorked()
end

-- 原版 farm_plow.OnTerraform 的杂物规则；不调用其 Finished，避免拆掉载体。
-- 2～4是随机尝试次数；距离已有新杂物不足1的位置会跳过，不强行补数量。
function AOMFarmWork.SpawnPloughDebris(holder,pt)
    local cx,cy,cz=TheWorld.Map:GetTileCenterPoint(pt:Get())
    local extent=TILE_SCALE*.9
    local positions={}
    for _=1,math.random(TUNING.FARM_PLOW_DRILLING_DEBRIS_MIN,TUNING.FARM_PLOW_DRILLING_DEBRIS_MAX) do
        local x=cx+math.random()*extent-extent/2
        local z=cz+math.random()*extent-extent/2
        local near=false
        for _,p in ipairs(positions) do
            if (x-p.x)^2+(z-p.z)^2<1 then near=true;break end
        end
        if not near then
            positions[#positions+1]={x=x,z=z}
            TheWorld.Map:CollapseSoilAtPoint(x,cy,z)
            SpawnPrefab("farm_soil_debris").Transform:SetPosition(x,cy,z)
        end
    end
end

function AOMFarmWork.GetTerraformer(inst)
    if inst._aom_terraformer==nil then
        local holder=CreateEntity()
        holder.entity:AddTransform()
        holder:AddTag("NOCLICK");holder:AddTag("NOBLOCK");holder:AddTag("FX")
        holder:AddComponent("terraformer")
        holder.components.terraformer.turf=WORLD_TILES.FARMING_SOIL
        holder.components.terraformer.plow=true
        holder.components.terraformer.onterraformfn=AOMFarmWork.SpawnPloughDebris
        holder.persists=false
        inst._aom_terraformer=holder
        inst:ListenForEvent("onremove",function()
            if inst._aom_terraformer and inst._aom_terraformer:IsValid() then inst._aom_terraformer:Remove() end
            inst._aom_terraformer=nil
        end)
    end
    return inst._aom_terraformer
end

-- 与 map.lua 的 TILLSOIL_IGNORE_TAGS 保持同步（拖拉机临时带 NOBLOCK 以绕过占用判定）
local function CanDigPitAt(map, x, z)
    return map:GetTileAtPoint(x,0,z) == WORLD_TILES.FARMING_SOIL
        and map:CanTillSoilAtPoint(x, 0, z, false)
end

local function GetMoundTargets(x,z,targets)
    if targets then return targets end
    local out={}
    for dx=-1,1 do
        for dz=-1,1 do out[#out+1]={x=x+dx,z=z+dz} end
    end
    return out
end
local function Matches(soil,p)
    local x,_,z=soil.Transform:GetWorldPosition()
    return (x-p.x)^2+(z-p.z)^2<=SOIL_MATCH_SQ
end

-- 修改地皮、铲除或删除旧坑前先保护作物和不可清理的障碍。
-- 配比模式的 targets 仅含尚未播种的位置；已记录作物由规划器核对后保留。
local function CheckProtected(x,z,doer,targets)
    for _,v in ipairs(TheWorld.Map:GetEntitiesOnTileAtPoint(x,0,z)) do
        if v:IsValid() and v~=doer then
            if IsDebris(v) then
                if not AOMFarmWork.IsClearableDebris(v) then return false,"UNCLEARABLE_DEBRIS" end
            elseif IsFarmPlant(v) then
                if targets==nil then return false,"PROTECTED_CROP" end
                local px,_,pz=v.Transform:GetWorldPosition()
                for _,p in ipairs(targets) do
                    if (px-p.x)^2+(pz-p.z)^2<.99 then return false,"BLOCKED_MOUND" end
                end
            elseif v.prefab~="farm_soil" and not (
                v:HasTag("NOBLOCK") or v:HasTag("NOCLICK") or v:HasTag("FX")
                or v:HasTag("DECOR") or v:HasTag("locomotor") or v:HasTag("player")
                or v:HasTag("aom_tractor") or v.components.inventoryitem~=nil
            ) then return false,"BLOCKED_MOUND" end
        end
    end
    return true
end

-- 普通与配比模式共用完成标准，不把“做过一部分”当作完成。
function AOMFarmWork.IsFieldReady(x,y,z,targets)
    if not CheckProtected(x,z,nil,targets) then return false end
    if TheWorld.Map:GetTileAtPoint(x,y,z)~=WORLD_TILES.FARMING_SOIL then return false end
    if #FindWeedsAndDebris(x,y,z,FIELD_RADIUS)>0 then return false end
    local wanted=GetMoundTargets(x,z,targets)
    local soils=FindEmptySoil(x,y,z,FIELD_RADIUS)
    if #soils~=#wanted then return false end
    for _,p in ipairs(wanted) do
        local found=false
        for _,soil in ipairs(soils) do if Matches(soil,p) then found=true;break end end
        if not found then return false end
    end
    return true
end

-- 返回 changed, reason, ready。部分改动也记录消耗，但必须暂停而不是宣告完成。
function AOMFarmWork.Plough(x,y,z,doer,tf,targets,vehicle)
    local safe,reason=CheckProtected(x,z,doer,targets)
    if not safe then return false,reason,false end
    if AOMFarmWork.IsFieldReady(x,y,z,targets) then return false,"ALREADY_TILLED",true end
    local map=TheWorld.Map
    local new_land=map:GetTileAtPoint(x,y,z)~=WORLD_TILES.FARMING_SOIL
    if doer==nil and (new_land or #FindWeedsAndDebris(x,y,z,FIELD_RADIUS)>0) then
        return false,"NO_WORKER",false
    end
    local changed=false
    if new_land then
        if tf==nil then return false,"NO_TERRAFORMER",false end
        -- 成功铺农田后同步进入 onterraformfn，产生原版规则的杂物。
        if not tf.components.terraformer:Terraform(Vector3(x,y,z),doer) then
            return false,"CANNOT_PLOW",false
        end
        changed=true
    end

    -- 原版 WorkedBy 会触发杂物自身的掉落回调；绝不手动 Remove 杂物或代造掉落。
    for _,v in ipairs(FindWeedsAndDebris(x,y,z,FIELD_RADIUS)) do
        if v:IsValid() then
            if not AOMFarmWork.IsClearableDebris(v) then return changed,"UNCLEARABLE_DEBRIS",false end
            local w=v.components.workable
            local before=w:GetWorkLeft()
            w:WorkedBy(doer,before)
            if not v:IsValid() or w:GetWorkLeft()<before then changed=true end
        end
    end
    -- 清理未完成时保留旧土坑，不能接着删坑、挖坑。
    if #FindWeedsAndDebris(x,y,z,FIELD_RADIUS)>0 then return changed,"CLEARING_INCOMPLETE",false end
    local still_safe,blocked=CheckProtected(x,z,doer,targets)
    if not still_safe then return changed,blocked,false end

    local wanted=GetMoundTargets(x,z,targets)
    -- 挖坑期间让占用检查忽略拖拉机本身（NOBLOCK 在 TILLSOIL_IGNORE_TAGS 里）。
    local vehicle_had_noblock = type(vehicle) == "table" and type(vehicle.HasTag) == "function"
        and vehicle:HasTag("NOBLOCK")
    if type(vehicle) == "table" and type(vehicle.AddTag) == "function" and not vehicle_had_noblock then
        vehicle:AddTag("NOBLOCK")
    end
    local kept={}
    for _,soil in ipairs(FindEmptySoil(x,y,z,FIELD_RADIUS)) do
        local keep=false
        for i,p in ipairs(wanted) do
            if not kept[i] and Matches(soil,p) then kept[i]=true;keep=true;break end
        end
        if not keep then soil:Remove();changed=true end
    end
    for _,p in ipairs(wanted) do
        local found=false
        for _,soil in ipairs(FindEmptySoil(x,y,z,FIELD_RADIUS)) do
            if Matches(soil,p) then found=true;break end
        end
        -- Map:CanTillSoilAtPoint 会检查“部署点是否被占用”，而拖拉机正停在待挖的这格上，
        -- 会让 3x3 坑位全部被判占用（土皮铺好却不挖坑）。挖坑这一瞬间给车加 NOBLOCK
        -- 让占用检查忽略它，之后立刻去掉，作物/建筑仍由 CheckProtected 提前挡掉。
        if not found and CanDigPitAt(map,p.x,p.z) then
            map:CollapseSoilAtPoint(p.x,0,p.z)
            local soil=SpawnPrefab("farm_soil")
            if soil then soil.Transform:SetPosition(p.x,0,p.z);changed=true end
        end
    end
    if type(vehicle) == "table" and type(vehicle.RemoveTag) == "function" and not vehicle_had_noblock then
        vehicle:RemoveTag("NOBLOCK")
    end
    local ready=AOMFarmWork.IsFieldReady(x,y,z,targets)
    if changed and doer then doer:PushEvent("tilling") end
    if ready then return changed,nil,true end
    return changed,"BLOCKED_MOUND",false
end

---------------------------------------------------------------------------
-- 2) 播种机：对应种子 PLANTSEED（farmplantable:Plant）
---------------------------------------------------------------------------

-- 普通播种一次一颗；只搜索本格，不越界补种到相邻地皮。
function AOMFarmWork.Seed(x,y,z,doer,seed)
    if not seed or not seed.components.farmplantable then return false,"NO_SEED" end
    for _,soil in ipairs(FindEmptySoil(x,y,z,FIELD_RADIUS)) do
        if seed.components.farmplantable:Plant(soil,doer) then return true end
    end
    return false,"NO_SOIL"
end

-- 配比播种只操作规划器指定的那个坑，绝不挑另一个空坑凑数。
function AOMFarmWork.SeedAt(target,doer,seed)
    if not seed or not seed:IsValid() or not seed.components.farmplantable then return false,"NO_SEED" end
    for _,soil in ipairs(TheSim:FindEntities(target.x,0,target.z,.2,{"soil"},{"NOCLICK","INLIMBO"})) do
        if soil.prefab=="farm_soil" and soil:IsValid() then
            return seed.components.farmplantable:Plant(soil,doer)
        end
    end
    return false,"NO_SOIL"
end

---------------------------------------------------------------------------
-- 3) 洒水机：单次原版水壶动作，驾驶层按实时水分重复到满
---------------------------------------------------------------------------

function AOMFarmWork.Water(x,y,z,doer)
    if not AOMFarmWork.IsFarmTileAt(x,y,z) then return false,"NOT_SOIL" end
    return require("aom_soil_moisture").Apply(x,y,z)
end

---------------------------------------------------------------------------
-- 4) 施肥机：对应肥料 FERTILIZE
---------------------------------------------------------------------------

-- 判断该格是否是可施肥的农田（原版 farming_manager 只对农田格维护养分格）
function AOMFarmWork.IsFarmTileAt(x, y, z)
	local fm = TheWorld.components.farming_manager
	if fm == nil then return false end
	local map = TheWorld.Map
	local tx, ty = map:GetTileCoordsAtPoint(x, y, z)
	-- _nutrientgrid 有数据 = 该格被农场系统接管
	return fm:GetTileNutrients(tx, ty) ~= nil and map:GetTileAtPoint(x, y, z) == WORLD_TILES.FARMING_SOIL
end

-- 单份肥料使用的兼容入口；整格补齐与结算由 aom_fertilizer / 驾驶层负责。
function AOMFarmWork.Fertilize(x,y,z,doer,fertilizer)
    return require("aom_fertilizer").Apply(x,z,doer,fertilizer)
end

---------------------------------------------------------------------------
-- 5) 除草机：对应铲子 DIG（只铲杂草与残渣）
---------------------------------------------------------------------------

function AOMFarmWork.Weed(x, y, z, doer)
    local targets=FindWeedsAndDebris(x,y,z,FIELD_RADIUS)
    if #targets==0 then return false,"NOTHING_TO_DO",true end
    if doer==nil then return false,"NO_WORKER",false end
    -- 整批预检，遇到非 DIG 或不可工作的杂草时不先清理一部分。
    for _,v in ipairs(targets) do
        if not AOMFarmWork.IsClearableDebris(v) then return false,"UNCLEARABLE_WEED",false end
    end
    local changed=false
    for _,v in ipairs(targets) do
        -- 前一株的原版/Mod回调可能改变后续实体，逐株重新保护作物及邻格。
        if v:IsValid() and SameTile(v,x,z) and IsDebris(v) then
            if not AOMFarmWork.IsClearableDebris(v) then return changed,"UNCLEARABLE_WEED",false end
            local w=v.components.workable
            local before=w:GetWorkLeft()
            w:WorkedBy(doer,before)
            if not v:IsValid() or w:GetWorkLeft()<before then changed=true end
        end
    end
    -- 调用不等于成功：工作量未减少不收费，部分完成/回调新生杂草均需暂停。
    if #FindWeedsAndDebris(x,y,z,FIELD_RADIUS)>0 then return changed,"WEEDING_INCOMPLETE",false end
    return changed,nil,true
end

---------------------------------------------------------------------------
-- 6) 收割机：原版采摘 + 巨大产物 HAMMER，产量与种子沿用原版回调。
---------------------------------------------------------------------------

-- 只接管真实作物定义的巨大产物，不触碰同为 HAMMER 的建筑和打蜡装饰。
local OVERSIZED_PRODUCTS={}
for crop,def in pairs(require("prefabs/farm_plant_defs").PLANT_DEFS) do
    local product=def.product_oversized or crop.."_oversized"
    OVERSIZED_PRODUCTS[product]=true
    OVERSIZED_PRODUCTS[product.."_rotten"]=true
end
local function IsOversizedProduce(v)
    return v:IsValid() and v:HasTag("oversized_veggie") and OVERSIZED_PRODUCTS[v.prefab]==true
end
local function FindOversizedProduce(x,y,z)
    local out={}
    for _,v in ipairs(TheSim:FindEntities(x,y,z,FIELD_RADIUS,{"oversized_veggie"},{"NOCLICK","INLIMBO"})) do
        local item=v.components.inventoryitem
        if IsOversizedProduce(v) and SameTile(v,x,z) and (item==nil or item.owner==nil) then out[#out+1]=v end
    end
    return out
end
local function BreakOversized(v,doer)
    local w=v.components.workable
    if w==nil or w:GetWorkAction()~=ACTIONS.HAMMER or not w:CanBeWorked() then return false,false end
    local before=w:GetWorkLeft()
    w:WorkedBy(doer,before)
    local changed=not v:IsValid() or w:GetWorkLeft()<before
    return changed,not v:IsValid() or not IsOversizedProduce(v)
end

-- 返回 changed, reason, ready；采摘与锤开在同一格内结算一次。
function AOMFarmWork.Harvest(x, y, z, doer)
    local targets=FindMaturePlants(x,y,z,FIELD_RADIUS)
    if #targets==0 and #FindOversizedProduce(x,y,z)==0 then return false,"NOTHING_TO_DO",true end
    if doer==nil then return false,"NO_WORKER",false end
    local changed=false
    for _,v in ipairs(targets) do
        if v:IsValid() and SameTile(v,x,z) and CanHarvestPlant(v) then
            local px,py,pz=v.Transform:GetWorldPosition()
            local p=v.components.pickable
            local _,loot=p:Pick(doer)
            local picked=not v:IsValid() or v.components.pickable~=p or not p:CanBePicked()
            changed=changed or picked
            if not picked then return changed,"HARVEST_INCOMPLETE",false end
            -- 原版 Pick 返回本次产物。只把本次新生成的巨大物件从驾驶员身上落回原株位置。
            for _,item in ipairs(type(loot)=="table" and loot or {}) do
                if IsOversizedProduce(item) then
                    local inventoryitem=item.components.inventoryitem
                    local owner=inventoryitem and inventoryitem.owner
                    if owner~=nil then
                        local inventory=doer.components.inventory
                        if owner~=doer or inventory==nil then return changed,"HARVEST_INCOMPLETE",false end
                        inventory:DropItem(item,true,false,Vector3(px,py,pz))
                        if not item:IsValid() or inventoryitem.owner~=nil then return changed,"HARVEST_INCOMPLETE",false end
                    end
                    item.Transform:SetPosition(px,py,pz)
                    local worked,ready=BreakOversized(item,doer)
                    changed=changed or worked
                    if not ready then return changed,"HARVEST_INCOMPLETE",false end
                end
            end
        end
    end
    -- 再扫描同格地面，包含采摘回调直接落地的产物和此前已采下的巨大产物。
    for _,v in ipairs(FindOversizedProduce(x,y,z)) do
        if IsOversizedProduce(v) and SameTile(v,x,z) then
            local item=v.components.inventoryitem
            if item==nil or item.owner==nil then
                local worked,ready=BreakOversized(v,doer)
                changed=changed or worked
                if not ready then return changed,"HARVEST_INCOMPLETE",false end
            end
        end
    end
    if #FindMaturePlants(x,y,z,FIELD_RADIUS)>0 or #FindOversizedProduce(x,y,z)>0 then
        return changed,"HARVEST_INCOMPLETE",false
    end
    return changed,nil,true
end

---------------------------------------------------------------------------
-- 预检：判断"此刻作业是否会真的做成一件事"
-- 用途：先预检通过再扣物料，避免失败时物料凭空消失
---------------------------------------------------------------------------

local function HasEmptySoilAt(x, y, z)
	return #FindEmptySoil(x, y, z, FIELD_RADIUS) > 0
end


-- 返回 true 表示"值得尝试作业"
function AOMFarmWork.CanWorkAt(att_type, x, y, z)
	if att_type == AOM_ATTACHMENT_TYPE.PLOW then
        -- 错位和多余空坑也需要整理，不能仅检查 CanTill。
        return not AOMFarmWork.IsFieldReady(x,y,z)
	elseif att_type == AOM_ATTACHMENT_TYPE.SEEDER then
		return HasEmptySoilAt(x, y, z)
	elseif att_type == AOM_ATTACHMENT_TYPE.IRRIGATOR then
		return AOMFarmWork.IsFarmTileAt(x, y, z)
	elseif att_type == AOM_ATTACHMENT_TYPE.FERTILIZER then
		local Fertilizer=require("aom_fertilizer")
        local n=Fertilizer.Read(x,z)
        return n~=nil and not Fertilizer.Full(n)
	elseif att_type == AOM_ATTACHMENT_TYPE.WEEDER then
		return #FindWeedsAndDebris(x, y, z, 2.9) > 0
	elseif att_type == AOM_ATTACHMENT_TYPE.HARVESTER then
		return #FindMaturePlants(x,y,z,FIELD_RADIUS)>0 or #FindOversizedProduce(x,y,z)>0
	end
	return false
end

---------------------------------------------------------------------------
-- 通用：按挂件类型分发
---------------------------------------------------------------------------

-- payload 里可以带 seed / fertilizer
function AOMFarmWork.DoWork(att_type, x, y, z, doer, payload)
	payload = payload or {}
	if att_type == AOM_ATTACHMENT_TYPE.PLOW then
		return AOMFarmWork.Plough(x, y, z, doer, payload.terraformer, payload.targets)
	elseif att_type == AOM_ATTACHMENT_TYPE.SEEDER then
		if payload.target then return AOMFarmWork.SeedAt(payload.target,doer,payload.seed) end
        return AOMFarmWork.Seed(x, y, z, doer, payload.seed)
	elseif att_type == AOM_ATTACHMENT_TYPE.IRRIGATOR then
		return AOMFarmWork.Water(x, y, z, doer)
	elseif att_type == AOM_ATTACHMENT_TYPE.FERTILIZER then
		return AOMFarmWork.Fertilize(x, y, z, doer, payload.fertilizer)
	elseif att_type == AOM_ATTACHMENT_TYPE.WEEDER then
		return AOMFarmWork.Weed(x, y, z, doer)
	elseif att_type == AOM_ATTACHMENT_TYPE.HARVESTER then
		return AOMFarmWork.Harvest(x, y, z, doer)
	end
	return false, "NO_ATTACHMENT"
end

return AOMFarmWork
