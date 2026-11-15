-- 使用原版护田触发条件做作业预检；只破除针对本车/驾驶员的根须圈。
local M={}
local function Range()return TUNING.FARM_PLANT_DEFENDER_SEARCH_DIST or 10 end
-- 固定本格原始作业目标的位置；只扩展一层，不沿刺花链无限扩大作业范围。
function M.NearWorkTargets(v,points)
    local x,_,z=v.Transform:GetWorldPosition()
    local r=Range()
    for _,p in ipairs(points)do
        if (x-p.x)^2+(z-p.z)^2<=r*r then return true end
    end
    return false
end
function M.FindNearbyIvy(points)
    local out,seen={},{}
    for _,p in ipairs(points)do
        for _,v in ipairs(TheSim:FindEntities(p.x,0,p.z,Range(),nil,{"NOCLICK","INLIMBO"}))do
            if v:IsValid() and v.prefab=="weed_ivy" and not seen[v] then
                seen[v]=true;out[#out+1]=v
            end
        end
    end
    return out
end
function M.FindIvy(target,worker)
    if worker and worker.HasTag and worker:HasTag("plantkin") then return nil end
    local x,y,z=target.Transform:GetWorldPosition()
    for _,v in ipairs(TheSim:FindEntities(x,y,z,Range(),{"farm_plant_defender"},{"INLIMBO"}))do
        if v:IsValid() and v.prefab=="weed_ivy"
            and not (v.components.burnable and v.components.burnable.burning) then return v end
    end
end
function M.Priority(v)
    return v.prefab=="weed_ivy" and (v:HasTag("farm_plant_defender") and 2 or 1) or 0
end
function M.ClearSnares(vehicle,rider)
    if not TheWorld.ismastersim or not rider or not rider:IsValid() then return 0 end
    local mounted=rider.components and rider.components.rider
    if not vehicle:IsValid() or not mounted or mounted:GetMount()~=vehicle then return 0 end
    -- 收割机只做护田风险预检，不再替除草机破除已经生成的根须。
    if vehicle._attachment_type=="harvester" then return 0 end
    local x,y,z=rider.Transform:GetWorldPosition()
    local radius=(rider.GetPhysicsRadius and rider:GetPhysicsRadius(0) or 0)+2.5
    local count=0
    for _,v in ipairs(TheSim:FindEntities(x,y,z,radius))do
        if v.prefab=="ivy_snare" and v:IsValid() and (v.target==rider or v.target==vehicle) then
            local health=v.components.health
            if health and not health:IsDead() then
                -- 原版death回调撤销碰撞并播放消退；不把根须当成可DIG杂草。
                health:Kill();count=count+1
            end
        end
    end
    return count
end
return M
