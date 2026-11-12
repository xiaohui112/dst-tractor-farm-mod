-- F 只在驾驶拖拉机时接管；阻止同一次按键触发原版攻击。
local M = {}
local function FPressed()
    return TheInput~=nil and TheInput:IsKeyDown(KEY_F)
end
local function Driving(player)
    local rider=player and player.replica and player.replica.rider
    local mount=rider and rider:IsRiding() and rider:GetMount() or nil
    return mount and mount:HasTag("aom_tractor") and mount or nil
end
local function AcceptInput(player)
    local controller=player and player.components.playercontroller
    return Driving(player) and controller and controller:IsEnabled()
        and not IsPaused() and TheFrontEnd.textProcessorWidget==nil
end
function M.Install()
    local held=false
    TheInput:AddKeyDownHandler(KEY_F,function()
        if held or not AcceptInput(ThePlayer) then return end
        held=true
        SendModRPCToServer(AOM_RPC.TOGGLE_WORK)
    end)
    TheInput:AddKeyUpHandler(KEY_F,function()held=false end)
end
function M.WrapController(controller)
    local original=controller.OnControl
    controller.OnControl=function(self,control,down,...)
        if control==CONTROL_ATTACK and ((not down and self._aom_f_captured)
            or (Driving(self.inst) and FPressed())) then
            self._aom_f_captured=down and true or nil
            return true
        end
        return original(self,control,down,...)
    end
    -- 原版 OnUpdate 会在按住攻击键时继续寻敌，不能只拦截首次 OnControl。
    local pressed=controller.IsControlPressed
    if pressed then
        controller.IsControlPressed=function(self,control,...)
            if control==CONTROL_ATTACK and Driving(self.inst) and FPressed() then return false end
            return pressed(self,control,...)
        end
    end
end
return M
