-- 纯客户端音效，不调用农业、消耗、安抚或 RPC。每个听者最多播放一首。
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

local function Nearest(owner)
    local nearest,distance=nil,M.RADIUS*M.RADIUS
    local x,_,z=owner.Transform:GetWorldPosition()
    for _,player in ipairs(AllPlayers or {owner}) do
        local rider=player.replica and player.replica.rider
        local tractor=rider and rider:GetMount()
        if player:IsValid() and tractor and tractor:IsValid() and tractor.prefab=="aom_tractor_chassis"
            and Value(tractor,"_workstatus") and (Value(tractor,"_water_net") or 0)>0 then
            local att=Value(tractor,"_attachment")
            if att and att:IsValid() and att.attachment_type=="irrigator" then
                -- 原版骑乘会隐藏车体，声源位置使用骑手，而不是隐藏底盘。
                local px,_,pz=player.Transform:GetWorldPosition()
                local d=(px-x)^2+(pz-z)^2
                if d<distance then nearest,distance=tractor,d end
            end
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
