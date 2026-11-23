-- 完整巨大产物是原版重物。车辆经过时仅临时撤掉它们对人物的物理阻挡。
local M={}
local shared=setmetatable({},{__mode="k"})
local TAGS={"oversized_veggie"}
local EXCLUDE={"INLIMBO","NOCLICK"}
local RANGE=2

local function IsObstacle(item)
    return item:IsValid() and item.Physics and item.Physics:GetCollisionGroup()==COLLISION.OBSTACLES
end

local function Release(item)
    local state=shared[item]
    state.users=state.users-1
    if state.users==0 then
        if state.restore and IsObstacle(item) then item.Physics:CollidesWith(COLLISION.CHARACTERS) end
        shared[item]=nil
    end
end

function M.Clear(vehicle)
    for item in pairs(vehicle._aom_harvest_clearance or {}) do Release(item) end
    vehicle._aom_harvest_clearance=nil
end

function M.Update(vehicle,x,z)
    if vehicle._atttype_net:value()~="harvester" or not vehicle._keep_oversized_net:value() then
        M.Clear(vehicle)
        return
    end
    local previous=vehicle._aom_harvest_clearance or {}
    local nearby={}
    for _,item in ipairs(TheSim:FindEntities(x,0,z,RANGE,TAGS,EXCLUDE)) do
        local name=item.prefab
        if type(name)=="string" and (name:match("_oversized$") or name:match("_oversized_rotten$")) and IsObstacle(item) then
            nearby[item]=true
            local state=shared[item]
            if not state then
                state={users=0,restore=false}
                shared[item]=state
            end
            if not previous[item] then state.users=state.users+1 end
            if bit.band(item.Physics:GetCollisionMask(),COLLISION.CHARACTERS)~=0 then
                item.Physics:ClearCollidesWith(COLLISION.CHARACTERS)
                state.restore=true
            end
        end
    end
    for item in pairs(previous) do if not nearby[item] then Release(item) end end
    vehicle._aom_harvest_clearance=nearby
end

return M
