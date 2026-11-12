-- 所有客户端按同步骑手播放声音；声源在骑手上，避免隐藏底盘的坐标造成无声。
local M={ENGINE="aom_tractor_engine",WORK="aom_tractor_work"}
function M.EmitExhaust(inst)
    local rider=inst._rider
    if not rider or not rider:IsValid() then return end
    -- 驾驶bank的空前挂点现作为烟筒口定位符号，随视图和车身悬挂一起移动。
    local x,y,z,found=rider.AnimState:GetSymbolPosition("aom_driver_attachment_front",0,0,0)
    if not found then
        x,y,z,found=inst.AnimState:GetSymbolPosition("attachment_front",0,0,0)
    end
    if not found then return end
    local puff=SpawnPrefab("aom_exhaust_puff")
    if puff then puff.Transform:SetPosition(x,y,z) end
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
    local rider=inst._aom_motion_rider
    if rider and rider:IsValid() then
        if rider.SoundEmitter then
            rider.SoundEmitter:KillSound(M.ENGINE)
            rider.SoundEmitter:KillSound(M.WORK)
        end
        local replica=rider.replica and rider.replica.rider
        local mount=replica and replica:GetMount()
        if not mount then rider.Transform:SetFourFaced()
        elseif not mount:HasTag("aom_tractor") then rider.Transform:SetSixFaced() end
    end
    inst._aom_motion_rider=nil
    inst._aom_engine_event=nil
    inst._aom_work_sound=false
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
    local kind=inst._atttype_net:value()
    if kind~=inst._aom_motion_attachment then
        require("aom_driver_visual").UpdateAttachment(inst,rider.AnimState)
        inst._aom_motion_attachment=kind
    end
    local x,_,z=rider.Transform:GetWorldPosition()
    local moving=inst._aom_motion_x~=nil and (x-inst._aom_motion_x)^2+(z-inst._aom_motion_z)^2>.0001
    inst._aom_motion_x,inst._aom_motion_z=x,z
    if TheNet:IsDedicated() then return end
    local emitter=rider.SoundEmitter
    if not emitter then return end
    local event=inst._fuel:value()>0 and (moving and "drive" or "idle") or nil
    if event~=inst._aom_engine_event then
        emitter:KillSound(M.ENGINE)
        if event then emitter:PlaySound("aom_tractor_sfx/tractor/"..event,M.ENGINE,.45) end
        inst._aom_engine_event=event
    end
    local working=event~=nil and moving and inst._workstatus:value()
    if working and not inst._aom_work_sound then
        emitter:PlaySound("aom_tractor_sfx/tractor/work",M.WORK,.3)
    elseif not working and inst._aom_work_sound then emitter:KillSound(M.WORK) end
    inst._aom_work_sound=working
end

function M.Attach(inst)
    inst._aom_motion_task=inst:DoPeriodicTask(.1,M.Update)
    inst:ListenForEvent("onremove",Stop)
end
return M
