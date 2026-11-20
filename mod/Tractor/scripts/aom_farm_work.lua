--[[
	Tractor —— 原版农场动作封装层

    负责原版铺地、土坑、播种、除草与收割适配。
    水肥批次分别由aom_irrigator/aom_fertilizer处理；机械规则在aom_equipment_defs。
    作业副作用通过aom_work_result观察，异常后也保留真实进度并统一结算。
]]

-- 返回值为 "ok" / nil, reason
local AOMFarmWork = {}
local Grid=require("aom_farm_grid")
local Result=require("aom_work_result")
local WeedDefense=require("aom_weed_defense")
local Cargo=require("aom_cargo")
local Crops=require("aom_crop_state")

-- 原版杂草也带 farm_plant 标签；真正作物的组件/定义优先，兼容误加 weed 标签。
local function IsFarmPlant(target)
    return Crops.IsFarmPlant(target)
end

-- 该作物是否可收获
-- 原版 farm plant 的收获走 pickable：CanBePicked / Pick
-- （核对 components/pickable.lua:382 CanBePicked、:535 Pick）
local function CanHarvestPlant(target)
    return Crops.CanHarvest(target)
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
local function IsWeedingTarget(v)
    return IsDebris(v) or Crops.CanClearRemains(v)
end

-- 找某点附近半径 r 内的杂草与园艺残渣
local function FindWeedsAndDebris(x, y, z, r, include_remains)
	local ents = TheSim:FindEntities(x, y, z, r, nil, { "NOCLICK", "INLIMBO", "player", "INV_MISC" })
	local result = {}
	for _, v in ipairs(ents) do
		-- 原版杂草 prefab：weed_forgetmelots / weed_firenettle / weed_tillweed / weed_ivy
		-- 原版残渣 prefab：farm_soil_debris（两者 workable 动作都是 DIG）
		if v:IsValid() and SameTile(v,x,z) and (IsDebris(v) or include_remains and Crops.CanClearRemains(v)) then
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

-- 记在地皮剩余的真实土坑上，换车、暂停和读档都能续播。
function AOMFarmWork.InitSeedSoil(soil)
    if not TheWorld.ismastersim then return end
    local original_save=soil.OnSave
    local original_load=soil.OnLoad
    soil.OnSave=function(inst,data)
        data.aom_sowing_paid=inst._aom_sowing_paid or nil
        if original_save then return original_save(inst,data) end
    end
    soil.OnLoad=function(inst,data,newents)
        if original_load then original_load(inst,data,newents) end
        inst._aom_sowing_paid=data and data.aom_sowing_paid==true or nil
    end
end

function AOMFarmWork.SeedTilePaid(x,y,z)
    for _,soil in ipairs(FindEmptySoil(x,y,z,FIELD_RADIUS)) do
        if soil._aom_sowing_paid then
            -- 上一轮的作物已清空时，旧计划刻意留出的坑也要重新结算。
            for _,plant in ipairs(TheSim:FindEntities(x,y,z,FIELD_RADIUS,{"farm_plant"},{"INLIMBO","NOCLICK"})) do
                if plant:IsValid() and SameTile(plant,x,z) and IsFarmPlant(plant) then return true end
            end
            break
        end
    end
    return false
end

function AOMFarmWork.MarkSeedTilePaid(x,y,z)
    for _,soil in ipairs(FindEmptySoil(x,y,z,FIELD_RADIUS)) do soil._aom_sowing_paid=true end
end
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
            -- 铺相邻新田时，原版随机杂物会破坏邻格土坑；跳过这次位置，保护已整理的地块。
            local spacing=GetFarmTillSpacing and GetFarmTillSpacing() or TUNING.FARM_TILL_SPACING or 1.25
            for _,soil in ipairs(TheSim:FindEntities(x,cy,z,spacing,{"soil"},{"NOCLICK","INLIMBO"})) do
                if not SameTile(soil,cx,cz) then near=true;break end
            end
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
    if map:GetTileAtPoint(x,0,z)~=WORLD_TILES.FARMING_SOIL or not map:CanTillSoilAtPoint(x,0,z,false) then return false end
    -- 原版占用检查忽略soil；不能因此把计划外邻格的手工土坑打坏。
    local spacing=GetFarmTillSpacing and GetFarmTillSpacing() or TUNING.FARM_TILL_SPACING or 1.25
    for _,soil in ipairs(TheSim:FindEntities(x,0,z,spacing,{"soil"},{"NOCLICK","INLIMBO"})) do
        if not SameTile(soil,x,z) then return false end
    end
    return true
end

local function GetMoundTargets(x,z,targets)
    if targets then return targets end
    local out={}
    -- 原版 CollapseSoilAtPoint 会打坏 1.25 范围内的邻坑；间距 1 会互相毁坑。
    -- 二进制精确偏移；同格1.3125、跨格1.375，均大于原版1.25。
    local spacing=Grid.SPACING
    for dx=-1,1 do
        for dz=-1,1 do out[#out+1]={x=x+dx*spacing,z=z+dz*spacing} end
    end
    return out
end
local function Matches(soil,p)
    local x,_,z=soil.Transform:GetWorldPosition()
    return (x-p.x)^2+(z-p.z)^2<=SOIL_MATCH_SQ
end

-- 修改地皮、铲除或删除旧坑前先保护作物和不可清理的障碍。
-- 配比模式的 targets 仅含尚未播种的位置；已记录作物由规划器核对后保留。
local function CheckProtected(x,z,doer,targets,protected_plants)
    for _,v in ipairs(TheWorld.Map:GetEntitiesOnTileAtPoint(x,0,z)) do
        if v:IsValid() and v~=doer and not (protected_plants and protected_plants[v]) then
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

AOMFarmWork.CheckProtected=CheckProtected

-- 跳过场地占用不等于完成；仍保留严格IsFieldReady供播种计划核对。
function AOMFarmWork.IsPloughSkip(reason)
    return reason=="PROTECTED_CROP" or reason=="BLOCKED_MOUND"
        or reason=="UNCLEARABLE_DEBRIS" or reason=="CANNOT_PLOW"
end
local function NearPlant(p,plants)
    local spacing=GetFarmTillSpacing and GetFarmTillSpacing() or TUNING.FARM_TILL_SPACING or 1.25
    for _,plant in ipairs(plants) do
        local x,_,z=plant.Transform:GetWorldPosition()
        if (p.x-x)^2+(p.z-z)^2<spacing^2 then return true end
    end
    return false
end
local function IsRootedPlant(v)
    return IsFarmPlant(v) or IsDebris(v) and v.prefab~="farm_soil_debris"
        or v:HasTag("plant") or v:HasTag("tree") or v:HasTag("stump") or v:HasTag("bush")
        or v.components.pickable~=nil and v.components.inventoryitem==nil
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

-- 只收本格无人持有、原版允许拾取并放入容器的物品；建筑和作物仍保留占用检查。
function AOMFarmWork.CollectWorkItems(x,y,z,vehicle,drops,selective)
    local container=vehicle and vehicle.components.container
    local items=TheWorld.Map:GetEntitiesOnTileAtPoint(x,y,z)
    local seen={};for _,item in ipairs(items) do seen[item]=true end
    -- 原版掉落会散落到格边另一侧；本次动作的真实产物也要完整收纳。
    for _,item in ipairs(drops or {}) do
        if not seen[item] then items[#items+1]=item;seen[item]=true end
    end
    for _,item in ipairs(items) do
        local ii=item.components.inventoryitem
        local burnable=item.components.burnable
        local projectile=item.components.projectile
        if item:IsValid() and ii and ii.owner==nil and ii.canbepickedup
            and not item:HasTag("INLIMBO") and not item:HasTag("FX")
            and not item:HasTag("aom_attachment")
            and not item:HasTag("oversized_veggie")
            and not (burnable and burnable:IsBurning())
            and not (projectile and projectile:IsThrown())
            and not (item.components.container and item.components.container:IsOpen())
            and container and container:CanTakeItemInSlot(item) then
            -- 开垦/除草遇到剩余物暂停；收割可继续处理仍能收纳的作物。
            if not Cargo.Collect(vehicle,item) and not selective then return false,"CARGO_FULL" end
        end
    end
    return true
end
AOMFarmWork.CollectPloughItems=AOMFarmWork.CollectWorkItems

-- 只监听本次原版动作的掉落，不扩大拾取范围，也不重新生成任何物品。
local function CaptureDrops(target,fn,on_drop)
    local dropper=target and target.components.lootdropper
    local spawn=dropper and dropper.SpawnLootPrefab
    local drops={}
    if spawn then
        dropper.SpawnLootPrefab=function(self,...)
            local item=spawn(self,...)
            if item then drops[#drops+1]=item;if on_drop then on_drop(item) end end
            return item
        end
    end
    local ok,a,b=pcall(fn)
    if spawn then dropper.SpawnLootPrefab=spawn end
    if not ok then error(a,0) end
    return a,b,drops
end

-- 返回 changed, reason, ready；占用允许继续行驶，不能伪报整格完成。
function AOMFarmWork.Plough(x,y,z,doer,tf,targets,vehicle)
    local map=TheWorld.Map
    local new_land=map:GetTileAtPoint(x,y,z)~=WORLD_TILES.FARMING_SOIL
    local plants={}
    -- 邻格作物也保护，CollapseSoilAtPoint会影响间距范围内的实体。
    for _,v in ipairs(TheSim:FindEntities(x,y,z,FIELD_RADIUS+1.25,nil,{"INLIMBO","NOCLICK"})) do
        if v:IsValid() and IsRootedPlant(v) then plants[#plants+1]=v;plants[v]=true end
        if new_land and v:IsValid() and SameTile(v,x,z)
            and IsRootedPlant(v) then
            return false,"PROTECTED_CROP",false
        end
    end
    local wanted={}
    for _,p in ipairs(GetMoundTargets(x,z,targets)) do
        if not NearPlant(p,plants) then wanted[#wanted+1]=p end
    end
    local safe,reason=CheckProtected(x,z,doer,wanted,plants)
    if not safe then return false,reason,false end
    local collected,why=AOMFarmWork.CollectPloughItems(x,y,z,vehicle)
    if not collected then return false,why,false end
    if AOMFarmWork.IsFieldReady(x,y,z,targets) then return false,"ALREADY_TILLED",true end
    local function Debris()
        local out={}
        for _,v in ipairs(FindWeedsAndDebris(x,y,z,FIELD_RADIUS)) do
            if not plants[v] then out[#out+1]=v end
        end
        return out
    end
    if doer==nil and (new_land or #Debris()>0) then
        return false,"NO_WORKER",false
    end
    local changed=false
    if new_land then
        if tf==nil then return false,"NO_TERRAFORMER",false end
        -- 成功铺农田后同步进入 onterraformfn，产生原版规则的杂物。
        local before_tile=map:GetTileAtPoint(x,y,z)
        if not Result.Observe(vehicle,function()return tf.components.terraformer:Terraform(Vector3(x,y,z),doer)end,
            function()return map:GetTileAtPoint(x,y,z)~=before_tile end) then
            return false,"CANNOT_PLOW",false
        end
        changed=true
    end

    -- 原版 WorkedBy 会触发杂物自身的掉落回调；绝不手动 Remove 杂物或代造掉落。
    for _,v in ipairs(Debris()) do
        if v:IsValid() then
            if not AOMFarmWork.IsClearableDebris(v) then return changed,"UNCLEARABLE_DEBRIS",false end
            local w=v.components.workable
            local before=w:GetWorkLeft()
            local _,_,drops=Result.Observe(vehicle,function()
                return CaptureDrops(v,function()w:WorkedBy(doer,before)end)
            end,function()return not v:IsValid() or w:GetWorkLeft()<before end)
            if not v:IsValid() or w:GetWorkLeft()<before then changed=true end
            collected,why=AOMFarmWork.CollectWorkItems(x,y,z,vehicle,drops)
            if not collected then return changed,why,false end
        end
    end
    -- 清理未完成时保留旧土坑，不能接着删坑、挖坑。
    if #Debris()>0 then return changed,"CLEARING_INCOMPLETE",false end
    -- 原版铲除回调刚生成的石头、树枝等也要收走，否则会挡住接下来的九宫格。
    collected,why=AOMFarmWork.CollectPloughItems(x,y,z,vehicle)
    if not collected then return changed,why,false end
    local still_safe,blocked=CheckProtected(x,z,doer,wanted,plants)
    if not still_safe then return changed,blocked,false end

    -- 挖坑期间让占用检查忽略拖拉机本身（NOBLOCK 在 TILLSOIL_IGNORE_TAGS 里）。
    local vehicle_had_noblock = type(vehicle) == "table" and type(vehicle.HasTag) == "function"
        and vehicle:HasTag("NOBLOCK")
    if type(vehicle) == "table" and type(vehicle.AddTag) == "function" and not vehicle_had_noblock then
        vehicle:AddTag("NOBLOCK")
    end
    local kept={}
    for _,soil in ipairs(FindEmptySoil(x,y,z,FIELD_RADIUS)) do
        local sx,_,sz=soil.Transform:GetWorldPosition()
        local keep=NearPlant({x=sx,z=sz},plants)
        for i,p in ipairs(wanted) do
            if not kept[i] and Matches(soil,p) then kept[i]=true;keep=true;break end
        end
        if not keep then soil:Remove();changed=true;Result.Mark(vehicle) end
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
            if soil then soil.Transform:SetPosition(p.x,0,p.z);changed=true;Result.Mark(vehicle) end
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
function AOMFarmWork.Seed(x,y,z,doer,seed,vehicle)
    if not seed or not seed.components.farmplantable then return false,"NO_SEED" end
    local soils=FindEmptySoil(x,y,z,FIELD_RADIUS)
    -- 中断续种继续按现场剩余坑判断；失败不结算，最后一坑的异常成功仍结算。
    if vehicle and vehicle._aom_work_result then vehicle._aom_work_result.seed_tile_complete=#soils==1 end
    for _,soil in ipairs(soils) do
        local sx,_,sz=soil.Transform:GetWorldPosition()
        if Result.Observe(vehicle,function()return seed.components.farmplantable:Plant(soil,doer)end, function()return not soil:IsValid()end) then return true,nil,{x=sx,z=sz} end
    end
    return false,"NO_SOIL"
end

-- 配比播种只操作规划器指定的那个坑，绝不挑另一个空坑凑数。
function AOMFarmWork.SeedAt(target,doer,seed,vehicle)
    if not seed or not seed:IsValid() or not seed.components.farmplantable then return false,"NO_SEED" end
    for _,soil in ipairs(TheSim:FindEntities(target.x,0,target.z,.2,{"soil"},{"NOCLICK","INLIMBO"})) do
        if soil.prefab=="farm_soil" and soil:IsValid() then
            local ok=Result.Observe(vehicle,function()return seed.components.farmplantable:Plant(soil,doer)end,function()return not soil:IsValid()end)
            return ok,nil,ok and {x=target.x,z=target.z} or nil
        end
    end
    return false,"NO_SOIL"
end

---------------------------------------------------------------------------
-- 3) 洒水兼容入口：仅转发一剂；整格补满/储水由 aom_irrigator.WaterTile 编排。
-- aom_soil_moisture 独占原版水分读取、单剂应用及结果验证。
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
-- 5) 除草机：原版DIG杂草、残渣及明确失去采收能力的腐烂/死亡农作物。
---------------------------------------------------------------------------

function AOMFarmWork.Weed(x, y, z, doer, vehicle)
    local collected,why=AOMFarmWork.CollectWorkItems(x,y,z,vehicle)
    if not collected then return false,why,false end
    local targets=FindWeedsAndDebris(x,y,z,FIELD_RADIUS,true)
    if #targets==0 then return false,"NOTHING_TO_DO",true end
    if doer==nil then return false,"NO_WORKER",false end
    local points,seen,order={},{},{}
    for i,v in ipairs(targets) do
        local px,_,pz=v.Transform:GetWorldPosition()
        points[#points+1]={x=px,z=pz};seen[v]=true;order[v]=i
    end
    for _,v in ipairs(WeedDefense.FindNearbyIvy(points)) do
        if not seen[v] and IsDebris(v) then
            targets[#targets+1]=v;seen[v]=true;order[v]=#targets
        end
    end
    table.sort(targets,function(a,b)
        local pa,pb=WeedDefense.Priority(a),WeedDefense.Priority(b)
        return pa>pb or (pa==pb and order[a]<order[b])
    end)
    -- 整批预检，遇到非 DIG 或不可工作的杂草时不先清理一部分。
    for _,v in ipairs(targets) do
        local w=v.components.workable
        if not v:IsValid() or not IsWeedingTarget(v) or not w or w:GetWorkAction()~=ACTIONS.DIG or not w:CanBeWorked() then
            return false,"UNCLEARABLE_WEED",false
        end
    end
    local changed=false
    for _,v in ipairs(targets) do
        -- 普通杂草仍限本格；只有刺花可在原始目标10距离内跨格处理。
        if v:IsValid() and IsWeedingTarget(v) and (SameTile(v,x,z)
            or (v.prefab=="weed_ivy" and WeedDefense.NearWorkTargets(v,points))) then
            local w=v.components.workable
            if not w or w:GetWorkAction()~=ACTIONS.DIG or not w:CanBeWorked() then return changed,"UNCLEARABLE_WEED",false end
            if v.prefab~="weed_ivy" and WeedDefense.FindIvy(v,doer) then
                return changed,"WEEDING_INCOMPLETE",false
            end
            local before=w:GetWorkLeft()
            local _,_,drops=Result.Observe(vehicle,function()return CaptureDrops(v,function()w:WorkedBy(doer,before)end)end, function()return not v:IsValid() or w:GetWorkLeft()<before end)
            if not v:IsValid() or w:GetWorkLeft()<before then changed=true end
            collected,why=AOMFarmWork.CollectWorkItems(x,y,z,vehicle,drops)
            if not collected then return changed,why,false end
            -- 刺花未清干净时不能继续普通除草，避免主动触发其护田反击。
            if v:IsValid() and v.prefab=="weed_ivy" and IsDebris(v)
                and WeedDefense.NearWorkTargets(v,points) then
                return changed,"WEEDING_INCOMPLETE",false
            end
        end
    end
    -- 调用不等于成功：工作量未减少不收费，部分完成/回调新生杂草均需暂停。
    if #FindWeedsAndDebris(x,y,z,FIELD_RADIUS,true)>0 then return changed,"WEEDING_INCOMPLETE",false end
    for _,v in ipairs(WeedDefense.FindNearbyIvy(points)) do
        if IsDebris(v) then return changed,"WEEDING_INCOMPLETE",false end
    end
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
local function BreakOversized(v,doer,vehicle)
    local w=v.components.workable
    if w==nil or w:GetWorkAction()~=ACTIONS.HAMMER or not w:CanBeWorked() then return false,false end
    local before=w:GetWorkLeft()
    local _,_,drops=Result.Observe(vehicle,function()return CaptureDrops(v,function()w:WorkedBy(doer,before)end)end, function()return not v:IsValid() or w:GetWorkLeft()<before end)
    local changed=not v:IsValid() or w:GetWorkLeft()<before
    return changed,not v:IsValid() or not IsOversizedProduce(v),drops
end

-- 保留真实驾驶员作为采摘者，原版产量/事件/角色回调不变。
-- 仅在同步采摘期间把新生成、尚无归属的物品留在原株位置，避免先合进玩家旧堆叠。
local function PickForCargo(p,doer,vehicle,px,py,pz)
    local inventory=vehicle and doer.components.inventory
    local give=inventory and inventory.GiveItem
    local produced=false
    local function record_drop()
        produced=true;Result.Mark(vehicle)
    end
    if inventory then
        inventory.GiveItem=function(self,item,...)
            local ii=item and item.components.inventoryitem
            if ii and ii.owner==nil then
                record_drop();item.Transform:SetPosition(px,py,pz)
                return true
            end
            return give(self,item,...)
        end
    end
    local drops
    local ok,picked,loot=pcall(function()
        local a,b,c=CaptureDrops(p.inst,function()return p:Pick(doer)end,record_drop)
        drops=c
        return a,b
    end)
    if inventory then inventory.GiveItem=give end
    if not ok then
        -- Pick在产物生成后才调用onpickedfn。回调抛错时原版尚未清除可采摘标志；
        -- 将已产出的这次采摘持久化为picked，避免重试或读档复制同一份产物。
        if produced and p.inst:IsValid() and p.inst.components.pickable==p then p.canbepicked=false end
        error(picked,0)
    end
    return picked,loot,drops
end

-- 返回 changed, reason, ready；采摘与锤开在同一格内结算一次。
function AOMFarmWork.Harvest(x, y, z, doer, vehicle)
    -- 不让装不下的旧地面物/种子阻断其他仍可叠堆的作物。
    local collected,why=AOMFarmWork.CollectWorkItems(x,y,z,vehicle,nil,true)
    if not collected then return false,why,false end
    if not Cargo.HasSpace(vehicle) then return false,"CARGO_FULL",false end
    local targets=FindMaturePlants(x,y,z,FIELD_RADIUS)
    if #targets==0 and #FindOversizedProduce(x,y,z)==0 then return false,"NOTHING_TO_DO",true end
    if doer==nil then return false,"NO_WORKER",false end
    -- 采摘会调用原版护田广播。先检查所有待采株，不能采了一半才发现危险。
    for _,v in ipairs(targets) do
        if Cargo.CanHarvest(v,vehicle) and WeedDefense.FindIvy(v,doer) then return false,"IVY_THREAT",false end
    end
    local changed=false
    for _,v in ipairs(targets) do
        if v:IsValid() and SameTile(v,x,z) and CanHarvestPlant(v) and Cargo.CanHarvest(v,vehicle) then
            if WeedDefense.FindIvy(v,doer) then return changed,"IVY_THREAT",false end
            local px,py,pz=v.Transform:GetWorldPosition()
            local p=v.components.pickable
            local _,loot,drops=Result.Observe(vehicle,function()return PickForCargo(p,doer,vehicle,px,py,pz)end, function()return not v:IsValid() or v.components.pickable~=p or not p:CanBePicked() end)
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
                    local worked,ready,giantdrops=BreakOversized(item,doer,vehicle)
                    changed=changed or worked
                    if not ready then return changed,"HARVEST_INCOMPLETE",false end
                    for _,drop in ipairs(giantdrops or {}) do drops[#drops+1]=drop end
                end
            end
            collected,why=AOMFarmWork.CollectWorkItems(x,y,z,vehicle,drops,true)
            if not collected then return changed,why,false end
        end
    end
    -- 再扫描同格地面，包含采摘回调直接落地的产物和此前已采下的巨大产物。
    for _,v in ipairs(FindOversizedProduce(x,y,z)) do
        if IsOversizedProduce(v) and SameTile(v,x,z) and Cargo.CanHarvest(v,vehicle) then
            local item=v.components.inventoryitem
            if item==nil or item.owner==nil then
                local worked,ready,drops=BreakOversized(v,doer,vehicle)
                changed=changed or worked
                if not ready then return changed,"HARVEST_INCOMPLETE",false end
                collected,why=AOMFarmWork.CollectWorkItems(x,y,z,vehicle,drops,true)
                if not collected then return changed,why,false end
            end
        end
    end
    if not Cargo.HasSpace(vehicle) then return changed,"CARGO_FULL",false end
    local remaining=FindMaturePlants(x,y,z,FIELD_RADIUS)
    for _,v in ipairs(FindOversizedProduce(x,y,z))do remaining[#remaining+1]=v end
    for _,v in ipairs(remaining)do
        if Cargo.CanHarvest(v,vehicle) then return changed,"HARVEST_INCOMPLETE",false end
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
		return #FindWeedsAndDebris(x, y, z, 2.9, true) > 0
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
		return AOMFarmWork.Plough(x, y, z, doer, payload.terraformer, payload.targets,payload.vehicle)
	elseif att_type == AOM_ATTACHMENT_TYPE.SEEDER then
		if payload.target then return AOMFarmWork.SeedAt(payload.target,doer,payload.seed,payload.vehicle) end
        return AOMFarmWork.Seed(x, y, z, doer, payload.seed,payload.vehicle)
	elseif att_type == AOM_ATTACHMENT_TYPE.IRRIGATOR then
		return AOMFarmWork.Water(x, y, z, doer)
	elseif att_type == AOM_ATTACHMENT_TYPE.FERTILIZER then
		return AOMFarmWork.Fertilize(x, y, z, doer, payload.fertilizer)
	elseif att_type == AOM_ATTACHMENT_TYPE.WEEDER then
		return AOMFarmWork.Weed(x, y, z, doer,payload.vehicle)
	elseif att_type == AOM_ATTACHMENT_TYPE.HARVESTER then
		return AOMFarmWork.Harvest(x, y, z, doer,payload.vehicle)
	end
	return false, "NO_ATTACHMENT"
end

return AOMFarmWork
