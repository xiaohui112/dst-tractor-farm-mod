-- 世界偏移仍会乘驾驶模型倍率：零偏移跟随头部，间距只在屏幕坐标计算。
local M={SYMBOL="headbase",HEAD_OFFSET=Vector3(0,0,0),SCREEN_GAP=56}
local function RestoreWidget(state)
    local w=state.widget
    if w and (not w.inst or w.inst:IsValid()) and w.GetScreenOffset and w.SetScreenOffset then
        local x,y=w:GetScreenOffset()
        if x==state.screen_x and y==state.screen_y+M.SCREEN_GAP then
            w:SetScreenOffset(state.screen_x,state.screen_y)
        end
    end
    state.widget=nil
end
function M.Refresh(rider)
    local talker=rider and rider.components and rider.components.talker
    local widget=talker and talker.widget
    if widget and rider:IsValid() then
        local state=rider._aom_driver_speech
        if state and state.widget~=widget and widget.GetScreenOffset and widget.SetScreenOffset then
            RestoreWidget(state)
            state.widget=widget
            state.screen_x,state.screen_y=widget:GetScreenOffset()
            widget:SetScreenOffset(state.screen_x,state.screen_y+M.SCREEN_GAP)
        end
        widget.symbol=talker.symbol
        widget:SetOffset(talker.offset_fn and talker.offset_fn(rider) or talker.offset or Vector3(0,-400,0))
    end
end
function M.Clear(rider,vehicle)
    local state=rider and rider._aom_driver_speech
    if state and vehicle and state.vehicle~=vehicle then return end
    if state then
        RestoreWidget(state)
        if state.on_talk then rider:RemoveEventCallback("ontalk",state.on_talk) end
        if state.talker.offset_fn==state.offset then
            state.talker.offset_fn=state.original_offset
        end
        if state.talker.symbol==M.SYMBOL then state.talker.symbol=state.original_symbol end
        rider._aom_driver_speech=nil
    end
    M.Refresh(rider)
end
function M.Update(vehicle,rider)
    local talker=rider.components and rider.components.talker
    if not talker then return end
    -- ApplyBuildOverrides只由服务端Rider调用；AnimState会复制，Lua标记不会。
    -- 远端客户端必须依据同步骑手识别驾驶姿势，否则一直沿用-700乘模型倍率。
    local client_driver=not TheWorld.ismastersim and require("aom_driver_visual").ready
        and vehicle._rider_net and vehicle._rider_net:value()==rider
    if vehicle._aom_driver_animstate~=rider.AnimState and not client_driver then
        M.Clear(rider,vehicle);return
    end
    local state=rider._aom_driver_speech
    if state and state.talker==talker and state.vehicle==vehicle then M.Refresh(rider);return end
    if state then M.Clear(rider)end
    state={vehicle=vehicle,talker=talker,original_offset=talker.offset_fn,original_symbol=talker.symbol}
    state.offset=function()return M.HEAD_OFFSET end
    rider._aom_driver_speech=state
    -- 原版sayfn创建/定位FollowText后才发ontalk；首句或重建widget也当帧定位。
    state.on_talk=function()M.Refresh(rider)end
    rider:ListenForEvent("ontalk",state.on_talk)
    talker.symbol=M.SYMBOL
    talker.offset_fn=state.offset
    M.Refresh(rider)
end
return M
