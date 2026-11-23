-- 所有客户端按同步骑手播放声音；声源在骑手上，避免隐藏底盘的坐标造成无声。
local M={ENGINE="aom_tractor_engine"}
local ENGINE_VOLUME={idle=.45,drive=1,work=1}
local HarvestClearance=require("aom_harvest_clearance")
function M.EmitExhaust(inst)
    local rider=inst._rider
    if not rider or not rider:IsValid() then return end
    -- 两个 bank 的空前挂点标记同一根烟筒：正面画面左侧，背面画面右侧。
    local x,y,z,found=rider.AnimState:GetSymbolPosition("aom_driver_attachment_front",0,0,0)
    if not found then
        x,y,z,found=inst.AnimState:GetSymbolPosition("attachment_front",0,0,0)
    end
    if not found then return end
    local puff=SpawnPrefab("aom_exhaust_puff")
    if puff then puff.Transform:SetPosition(x,y,z) end
end

local function MuteForTractor(event)
    if event._aom_drive_sounds_muted then return end
    local original=event.fn
    event.fn=function(inst,...)
        local rider=inst.replica and inst.replica.rider or inst.components.rider
        local mount=rider and rider:GetMount()
        if mount and mount:IsValid() and mount:HasTag("aom_tractor") then return end
        return original(inst,...)
    end
    event._aom_drive_sounds_muted=true
end

-- 服务端和预测客户端的骑乘音效帧不同。仅包裹原版骑乘 Foley／脚步回调。
local DRIVE_SOUND_FRAMES={
    run_start={0,5},
    run={0,1,5,8},
}
function M.ConfigureDriveSounds(sg)
    for name,frames in pairs(DRIVE_SOUND_FRAMES) do
        local state=sg.states and sg.states[name]
        for _,event in ipairs(state and state.timeline or {}) do
            for _,frame in ipairs(frames) do
                if event.time==frame*FRAMES then MuteForTractor(event);break end
            end
        end
    end
end

-- 原版mount第14帧只播放坐骑叫声；拖拉机沿用时间线但不发牛叫。
function M.ConfigureMountSounds(sg)
    local state=sg.states and sg.states.mount
    for _,event in ipairs(state and state.timeline or {}) do
        if event.time==14*FRAMES and not event._aom_mount_voice_muted then
            local original=event.fn
            event.fn=function(inst,...)
                local rider=inst.components.rider
                local mount=rider and (rider:GetMount() or rider.target_mount)
                if mount and mount:IsValid() and mount:HasTag("aom_tractor") then return end
                return original(inst,...)
            end
            event._aom_mount_voice_muted=true
        end
    end
end
local function Stop(inst)
    HarvestClearance.Clear(inst)
    local rider=inst._aom_motion_rider
    if rider and rider:IsValid() then
        require("aom_driver_speech").Clear(rider,inst)
        if rider.SoundEmitter then
            rider.SoundEmitter:KillSound(M.ENGINE)
        end
        local replica=rider.replica and rider.replica.rider
        local mount=replica and replica:GetMount()
        if not mount then rider.Transform:SetFourFaced()
        elseif not mount:HasTag("aom_tractor") then rider.Transform:SetSixFaced() end
    end
    inst._aom_motion_rider=nil
    inst._aom_engine_event=nil
    inst._aom_motion_attachment=nil
    inst._aom_motion_x,inst._aom_motion_z=nil,nil
end
M.Stop=Stop

function M.Update(inst)
    local rider=inst._rider_net:value()
    if not rider or not rider:IsValid() then Stop(inst);return end
    require("aom_weed_defense").ClearSnares(inst,rider)
    if rider~=inst._aom_motion_rider then
        Stop(inst)
        inst._aom_motion_rider=rider
        -- Rider:Mount 在覆盖 build 后强制六向，所以必须在骑乘建立后设八向。
        rider.Transform:SetEightFaced()
    end
    require("aom_driver_speech").Update(inst,rider)
    local kind=inst._atttype_net:value()
    if kind~=inst._aom_motion_attachment then
        require("aom_driver_visual").UpdateAttachment(inst,rider.AnimState)
        inst._aom_motion_attachment=kind
    end
    local x,_,z=rider.Transform:GetWorldPosition()
    HarvestClearance.Update(inst,x,z)
    local moving=inst._aom_motion_x~=nil and (x-inst._aom_motion_x)^2+(z-inst._aom_motion_z)^2>.0001
    inst._aom_motion_x,inst._aom_motion_z=x,z
    if TheNet:IsDedicated() then return end
    local emitter=rider.SoundEmitter
    if not emitter then return end
    local music=require("aom_irrigator_music").PlaysInsteadOfTractor(inst)
    local event
    if not music and inst._fuel:value()>0 then
        if not moving then event="idle"
        elseif inst._workstatus:value() then event="work"
        else event="drive" end
    end
    local changed=event~=inst._aom_engine_event
    if changed then
        emitter:KillSound(M.ENGINE)
        inst._aom_engine_event=event
    end
    if event and (changed or emitter.PlayingSound and not emitter:PlayingSound(M.ENGINE)) then
        -- 同步骑手和本地声音可能异步就绪，丢失的循环需重新启动。
        emitter:PlaySound("aom_tractor_sfx/tractor/"..event,M.ENGINE,ENGINE_VOLUME[event],true)
    end
end

function M.Attach(inst)
    inst._aom_motion_task=inst:DoPeriodicTask(.1,M.Update)
    inst:ListenForEvent("aomriderdirty",M.Update)
    inst:ListenForEvent("onremove",Stop)
end
return M
