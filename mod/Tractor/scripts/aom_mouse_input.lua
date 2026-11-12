-- 骑乘时车体绘制在人物实体上；只接管点自己/自己坐骑的左右键。
local M={}
local function OwnVehicle(picker,target)
    local player=picker.inst
    local rider=player.replica and player.replica.rider
    local vehicle=rider and rider:IsRiding() and rider:GetMount() or nil
    return vehicle and vehicle:IsValid() and vehicle:HasTag("aom_tractor")
        and (target==player or target==vehicle)
end

function M.WrapPicker(picker,storage_action)
    if picker._aom_mouse_wrapped then return end
    picker._aom_mouse_wrapped=true
    local left=picker.GetLeftClickActions
    local right=picker.GetRightClickActions
    picker.GetLeftClickActions=function(self,position,target,...)
        if OwnVehicle(self,target) then
            return self:SortActionList({storage_action},self.inst)
        end
        return left(self,position,target,...)
    end
    picker.GetRightClickActions=function(self,position,target,...)
        if OwnVehicle(self,target) then
            -- target 必须是骑手，原版 DISMOUNT 才会执行正常下车动画。
            return self:SortActionList({ACTIONS.DISMOUNT},self.inst)
        end
        return right(self,position,target,...)
    end
end
return M
