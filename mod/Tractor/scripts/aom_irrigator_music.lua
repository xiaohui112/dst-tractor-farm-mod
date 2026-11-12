-- 客户端音效每个听者最多一首；植物安抚独立在服务端执行原版 TendTo。
local Bank=require("aom_irrigator_music_bank")
local M={ready=false,RADIUS=20,HANDLE="aom_irrigator_music"}

function M.Configure(enabled,root,exists,asset)
    M.ready=false
    if not enabled or not Bank.available or not root or type(exists)~="function" then return {} end
    for _,entry in ipairs(Bank.assets) do
        local ok,found=pcall(exists,root..entry[2])
        if not ok or not found then return {} end
    end
    local assets={}
    for _,entry in ipairs(Bank.assets) do assets[#assets+1]=asset(entry[1],entry[2]) end
    M.ready=true
    return assets
end

local function Value(inst,key)
    return inst[key] and inst[key]:value()
end

function M.IsActive(tractor)
    return tractor and tractor:IsValid() and tractor.prefab=="aom_tractor_chassis"
        and (tractor._music_enabled_net==nil or Value(tractor,"_music_enabled_net"))
        and (tractor._music_available_net==nil or Value(tractor,"_music_available_net"))
        and Value(tractor,"_workstatus") and (Value(tractor,"_water_net") or 0)>0
        and (Value(tractor,"_fuel") or 0)>0 and Value(tractor,"_atttype_net")=="irrigator"
end

-- 只改音乐/安抚，不改 F 状态、水量、燃料或农业计划；开关随车辆保存。
function M.SetEnabled(tractor,enabled)
    if not TheWorld.ismastersim or type(enabled)~="boolean" or not M.ready
        or not tractor or not tractor:IsValid() or tractor._attachment_type~="irrigator"
        or not tractor._music_enabled_net or not Value(tractor,"_music_available_net") then return false end
    if Value(tractor,"_music_enabled_net")~=enabled then
        tractor._music_enabled_net:set(enabled)
        tractor:PushEvent("aom_work_changed")
    end
    return true
end

function M.TendPlants(tractor)
    if not TheWorld.ismastersim or not M.ready or not M.IsActive(tractor) then return 0 end
    local rider=tractor._rider
    if not rider or not rider:IsValid() or rider:HasTag("playerghost")
        or not rider.components.rider or rider.components.rider:GetMount()~=tractor then return 0 end
    local x,y,z=rider.Transform:GetWorldPosition()
    local count=0
    -- 与原版留声机同范围、同周期，调用植物自己的对话/开心特效回调。
    for _,plant in ipairs(TheSim:FindEntities(x,y,z,TUNING.PHONOGRAPH_TEND_RANGE or 8,
        {"tendable_farmplant"},{"INLIMBO","NOCLICK","FX"})) do
        local tendable=plant.components.farmplanttendable
        if plant:IsValid() and tendable then
            local ok,tended=pcall(tendable.TendTo,tendable,rider)
            if ok and tended then count=count+1 end
        end
    end
    return count
end

function M.AttachTending(tractor)
    if not TheWorld.ismastersim then return end
    tractor._aom_music_tend_task=tractor:DoPeriodicTask(1,M.TendPlants)
    tractor:ListenForEvent("aom_work_changed",M.TendPlants)
end

local function Nearest(owner)
    local nearest,distance=nil,M.RADIUS*M.RADIUS
    local x,_,z=owner.Transform:GetWorldPosition()
    for _,player in ipairs(AllPlayers or {owner}) do
        local rider=player.replica and player.replica.rider
        local tractor=rider and rider:GetMount()
        if player:IsValid() and M.IsActive(tractor) then
                -- 原版骑乘会隐藏车体，声源位置使用骑手，而不是隐藏底盘。
                local px,_,pz=player.Transform:GetWorldPosition()
                local d=(px-x)^2+(pz-z)^2
                if d<distance then nearest,distance=tractor,d end
        end
    end
    return nearest,distance
end

function M.New(owner)
    local self={owner=owner,playing=false,failed=false}
    function self:Stop()
        if self.playing and self.owner.SoundEmitter then
            pcall(self.owner.SoundEmitter.KillSound,self.owner.SoundEmitter,M.HANDLE)
        end
        self.playing=false
    end
    function self:Update()
        local ok=pcall(function()
            if not M.ready or self.failed or not owner:IsValid() or owner:HasTag("playerghost") then self:Stop();return end
            local tractor,distance=Nearest(owner)
            local emitter=owner.SoundEmitter
            if not tractor or not emitter then self:Stop();return end
            local volume=.35*(1-math.sqrt(distance)/M.RADIUS)
            if not self.playing then
                -- 先记状态，PlaySound 抛错也会执行 KillSound 清理。
                self.playing=true
                emitter:PlaySound(Bank.event,M.HANDLE,volume)
                if emitter.PlayingSound and not emitter:PlayingSound(M.HANDLE) then error("music event unavailable") end
            elseif emitter.SetVolume then emitter:SetVolume(M.HANDLE,volume) end
        end)
        if not ok then self:Stop();self.failed=true end
    end
    return self
end

return M
