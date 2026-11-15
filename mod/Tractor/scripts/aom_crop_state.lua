-- 作物采收与残株清理共用判定；不把正常生长、缺水或暂时禁止交互当成死亡。
local M={}
function M.IsFarmPlant(target)
    if target.components.farmplantstress~=nil or target.plant_def~=nil then return true end
    if target.weed_def~=nil or target:HasTag("weedplantstress") then return false end
    return (type(target.prefab)=="string" and string.sub(target.prefab,1,11)=="farm_plant_")
        or target:HasTag("farm_plant")
end
local function Stage(target)
    local growable=target.components.growable
    return growable and growable.GetCurrentStageData and growable:GetCurrentStageData()
end
function M.IsRotten(target)
    if not M.IsFarmPlant(target) then return false end
    if target:HasTag("farm_plant_killjoy") then return true end
    local stage=Stage(target)
    return stage~=nil and stage.name=="rotten"
end
function M.CanHarvest(target)
    if not M.IsFarmPlant(target) then return false end
    local pickable=target.components.pickable
    return pickable~=nil and pickable:CanBePicked()
end
function M.CanClearRemains(target)
    if not M.IsFarmPlant(target) then return false end
    local pickable=target.components.pickable
    -- 可采收腐烂株留给收割机；禁用交互/被卡住也不能改走铲除绕过限制。
    if pickable and (pickable:CanBePicked() or pickable.caninteractwith==false or pickable.stuck) then return false end
    if M.IsRotten(target) or target:HasTag("deadplant") then return true end
    local stage=Stage(target)
    if stage and stage.name=="dead" then return true end
    local health=target.components.health
    return health~=nil and health:IsDead()
end
return M
