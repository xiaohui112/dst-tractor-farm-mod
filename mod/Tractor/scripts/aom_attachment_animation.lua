-- 机械动作和短时特效由主模拟端创建，使用引擎的 AnimState/实体复制。
-- 客户端不根据自己的移动采样推测作业，也不重复生成网络特效。
local M={EFFECT_DURATION=.65}
local Mount=require("aom_attachment_mount")

local function ClearEffects(item)
    if item._aom_effect_task then item._aom_effect_task:Cancel();item._aom_effect_task=nil end
    for _,fx in ipairs(item._aom_work_effects or {}) do
        if fx:IsValid() then fx:Remove() end
    end
    item._aom_work_effects=nil
    item._aom_stream=nil
    item._aom_effect_until=nil
    item._aom_dirt_x,item._aom_dirt_z=nil,nil
end
M.ClearEffects=ClearEffects

function M.Stop(item,immediate)
    ClearEffects(item)
    if item._aom_working then item._aom_working:set(false) end
    if item._aom_anim_working then
        item._aom_anim_working=false
        local kind=item.attachment_type
        if immediate then item.AnimState:PlayAnimation(kind)
        else
            item.AnimState:PlayAnimation(kind.."_work_pst")
            item.AnimState:PushAnimation(kind,true)
        end
    end
end

function M.SetWorking(vehicle,on)
    if not TheWorld.ismastersim then return end
    local item=Mount.Get(vehicle)
    if not item or not item:IsValid() then return end
    if not on then M.Stop(item);return end
    if item._aom_anim_working then return end
    item._aom_anim_working=true
    item._aom_working:set(true)
    item.AnimState:PlayAnimation(item.attachment_type.."_work_pre")
    item.AnimState:PushAnimation(item.attachment_type.."_work_loop",true)
end

local function Track(item,fx)
    if not fx then return end
    local effects=item._aom_work_effects or {}
    item._aom_work_effects=effects
    for i=#effects,1,-1 do if not effects[i]:IsValid() then table.remove(effects,i) end end
    effects[#effects+1]=fx
    return fx
end

local function GroundEffect(item)
    local fx=Track(item,SpawnPrefab("aom_work_soil"))
    if fx then
        local x,_,z=item.Transform:GetWorldPosition()
        fx.Transform:SetPosition(x,0,z)
        fx.Transform:SetRotation(Mount.Rotation(item))
    end
end

-- 只在原版农业操作确实改动了地块后调用。失败/满水/无杂草不产生结果特效。
function M.Success(vehicle,position)
    if not TheWorld.ismastersim or not vehicle._working then return end
    local item=Mount.Get(vehicle)
    if not item or not item:IsValid() or not item._aom_anim_working then return end
    local kind=item.attachment_type
    item._aom_effect_until=GetTime()+M.EFFECT_DURATION
    if item._aom_effect_task then item._aom_effect_task:Cancel() end
    item._aom_effect_task=item:DoTaskInTime(M.EFFECT_DURATION,function()ClearEffects(item)end)
    if kind=="plow" then GroundEffect(item);return end
    local stream=kind=="irrigator" or kind=="fertilizer"
    if stream and item._aom_stream and item._aom_stream:IsValid() then
        local fx=item._aom_stream
        if fx._aom_timeout then fx._aom_timeout:Cancel() end
        fx._aom_timeout=fx:DoTaskInTime(1,fx.Remove)
        return
    end
    local fx=Track(item,SpawnPrefab("aom_work_"..kind))
    if not fx then return end
    fx.Transform:SetRotation(Mount.Rotation(item))
    if stream then
        fx.AnimState:SetBank(kind=="irrigator" and "aom_attachment_water_mounted" or "aom_attachment_fx_mounted")
        fx.AnimState:PlayAnimation(kind=="irrigator" and "spray" or "fertilizer",true)
        item._aom_stream=fx
        fx.entity:SetParent(item.entity)
        fx.Transform:SetPosition(0,0,0)
        fx.Transform:SetRotation(0) -- 子实体继承挂件方向，不能重复叠加世界角度。
    else
        local x,y,z=item.Transform:GetWorldPosition()
        if position then x,y,z=position.x,0,position.z end
        fx.Transform:SetPosition(x,y,z)
    end
end

-- 同一挂载更新任务还负责异常失联/换驾驶员时的停工，以及犁铲后短时土迹。
function M.Update(item,vehicle)
    if not TheWorld.ismastersim then return end
    local rider=vehicle and vehicle._rider
    if not vehicle or not vehicle._working or not rider or not rider:IsValid()
        or vehicle._destroyed then
        if item._aom_anim_working or item._aom_work_effects then M.Stop(item) end
        return
    end
    M.SetWorking(vehicle,true)
    if item.attachment_type=="plow" and item._aom_effect_until
        and GetTime()<item._aom_effect_until then
        local x,_,z=item.Transform:GetWorldPosition()
        if item._aom_dirt_x and (x-item._aom_dirt_x)^2+(z-item._aom_dirt_z)^2>.12 then
            GroundEffect(item)
        end
        item._aom_dirt_x,item._aom_dirt_z=x,z
    else item._aom_dirt_x,item._aom_dirt_z=nil,nil end
end

return M
