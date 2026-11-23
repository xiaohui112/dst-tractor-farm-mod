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
    item._aom_effect_tile=nil
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

local function GroundEffect(item,x,z)
    local fx=Track(item,SpawnPrefab("aom_work_soil"))
    if fx then
        fx.Transform:SetPosition(x,0,z)
        fx.Transform:SetRotation(Mount.Rotation(item))
    end
end

local function WorkPointAndTile(vehicle)
    local x,_,z=Mount.WorkPosition(vehicle)
    local cx,_,cz=TheWorld.Map:GetTileCenterPoint(x,0,z)
    return x,z,cx,cz
end

local function LeaveEffectTile(item,cx,cz)
    local tile=item._aom_effect_tile
    if tile and (cx~=tile.x or cz~=tile.z) then
        if item._aom_stream and item._aom_stream:IsValid() then item._aom_stream:Remove() end
        item._aom_stream,item._aom_effect_tile=nil,nil
        item._aom_dirt_x,item._aom_dirt_z=nil,nil
    end
end

-- 只在原版农业操作确实改动了地块后调用。失败/满水/无杂草不产生结果特效。
function M.Success(vehicle,position,x,z,cx,cz)
    if not TheWorld.ismastersim or not vehicle._working then return end
    local item=Mount.Get(vehicle)
    if not item or not item:IsValid() or not item._aom_anim_working then return end
    local kind=item.attachment_type
    local work_x,work_z,work_cx,work_cz=WorkPointAndTile(vehicle)
    LeaveEffectTile(item,work_cx,work_cz)
    x,z,cx,cz=x or work_x,z or work_z,cx or work_cx,cz or work_cz
    local at_work_point=cx==work_cx and cz==work_cz
    if at_work_point then item._aom_effect_tile={x=cx,z=cz} end
    item._aom_effect_until=GetTime()+M.EFFECT_DURATION
    if item._aom_effect_task then item._aom_effect_task:Cancel() end
    item._aom_effect_task=item:DoTaskInTime(M.EFFECT_DURATION,function()ClearEffects(item)end)
    if kind=="plow" then
        GroundEffect(item,x,z)
        if at_work_point then item._aom_dirt_x,item._aom_dirt_z=x,z end
        return
    end
    local stream=kind=="irrigator" or kind=="fertilizer"
    if stream and at_work_point and item._aom_stream and item._aom_stream:IsValid() then
        local fx=item._aom_stream
        if fx._aom_timeout then fx._aom_timeout:Cancel() end
        fx._aom_timeout=fx:DoTaskInTime(1,fx.Remove)
        return
    end
    local fx=Track(item,SpawnPrefab("aom_work_"..kind))
    if not fx then return end
    fx.Transform:SetRotation(Mount.Rotation(item))
    if stream and at_work_point then
        fx.AnimState:SetBank(kind=="irrigator" and "aom_attachment_water_mounted" or "aom_attachment_fx_mounted")
        fx.AnimState:PlayAnimation(kind=="irrigator" and "spray" or "fertilizer",true)
        item._aom_stream=fx
        fx.entity:SetParent(item.entity)
        fx.Transform:SetPosition(0,0,0)
        fx.Transform:SetRotation(0) -- 子实体继承挂件方向，不能重复叠加世界角度。
    else
        if position then x,z=position.x,position.z end
        fx.Transform:SetPosition(x,0,z)
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
    if not item._aom_effect_tile then return end
    local x,z,cx,cz=WorkPointAndTile(vehicle)
    LeaveEffectTile(item,cx,cz)
    if item.attachment_type=="plow" and GetTime()<(item._aom_effect_until or 0) then
        if item._aom_dirt_x and (x-item._aom_dirt_x)^2+(z-item._aom_dirt_z)^2>.12 then
            GroundEffect(item,x,z)
            item._aom_dirt_x,item._aom_dirt_z=x,z
        end
    end
end

return M
