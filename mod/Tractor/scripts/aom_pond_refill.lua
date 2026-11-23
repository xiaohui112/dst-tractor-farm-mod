-- 池塘、海边和田边蓄水桶共用软管和可中断的补水流程。
local M={INTERVAL=.1,FRESHWATER_RATE=80}
local Durability=require("aom_durability")
local FILTER_DOSES_PER_USE=20
local function Valid(e)return e and e:IsValid()end
local function UpdateHoses(s)
    local sx,sy,sz,found=s.tool.AnimState:GetSymbolPosition("irrigator",0,-20,0)
    if not found then sx,sy,sz=s.tool.Transform:GetWorldPosition()end
    local deployment=math.clamp((GetTime()-s.started)/.35,.02,1)
    local px,pz=sx+(s.px-sx)*deployment,sz+(s.pz-sz)*deployment
    local dx,dz=px-sx,pz-sz
    local bx,bz=sx+dx*.35-dz*.08,sz+dz*.35+dx*.08
    local points={{sx,sy,sz,bx,.08,bz},{bx,.08,bz,px,.02,pz}}
    for i,fx in ipairs(s.hoses)do if Valid(fx)then fx:SetEnds(unpack(points[i]))end end
end
function M.Cancel(vehicle,notify)
    local state=vehicle._aom_pond_refill
    if not state then return end
    vehicle._aom_pond_refill=nil
    if state.task then state.task:Cancel() end
    for _,v in ipairs(state.listeners)do vehicle:RemoveEventCallback(v[1],state.cancel,v[2])end
    for _,fx in ipairs(state.hoses)do if Valid(fx)then fx:Remove()end end
    if vehicle._refilling_net then vehicle._refilling_net:set(false)end
    if notify then require("aom_feedback").Say(state.rider,require("aom_locale").Text("补水已中断，已保留补入的水量。")) end
end
local function ValidSession(vehicle,s)
    local rider,source,tool=s.rider,s.source,s.tool
    if not Valid(vehicle) or not Valid(rider) or not Valid(tool)
        or vehicle._destroyed or rider:HasTag("playerghost")
        or vehicle._rider~=rider or not rider.components.rider
        or rider.components.rider:GetMount()~=vehicle
        or require("aom_attachment_mount").Get(vehicle)~=tool then return false end
    if s.sea then
        if Durability.GetUses(tool)<=0 or not require("aom_irrigator").CanRefillAtSea(rider,s.sea) then return false end
    else
        if not Valid(source) then return false end
        if not s.barrel and (not source:HasTag("watersource") or not source.components.watersource
            or not source.components.watersource.available) then return false end
        local px,_,pz=source.Transform:GetWorldPosition()
        if (px-s.px)^2+(pz-s.pz)^2>.01 then return false end
    end
    local x,_,z=rider.Transform:GetWorldPosition()
    local turn=math.abs((rider.Transform:GetRotation()-s.rotation+180)%360-180)
    return (x-s.x)^2+(z-s.z)^2<=.01 and turn<=10
end

local function UpdateBarrel(vehicle,s)
    local allowance=math.floor((GetTime()-s.started)*M.FRESHWATER_RATE+1e-6)-s.drawn
    if allowance>0 then
        local drawn,ok=s.source:SupplyWater(s.store,allowance)
        if vehicle._aom_pond_refill~=s then return end
        if not ok then M.Cancel(vehicle,true);return end
        s.drawn=s.drawn+drawn
    end
    if s.store:GetWater()>=s.capacity then M.Cancel(vehicle)
    elseif s.source:GetStoredWater()<=0 then
        M.Cancel(vehicle)
        require("aom_feedback").Say(s.rider,require("aom_locale").Text("蓄水桶没水了。"))
    end
end

function M.Update(vehicle)
    local s=vehicle._aom_pond_refill
    if not s then return end
    if not ValidSession(vehicle,s) then M.Cancel(vehicle,true);return end
    UpdateHoses(s)
    if s.barrel then UpdateBarrel(vehicle,s);return end
    local progress=math.clamp((GetTime()-s.started)/s.duration,0,1)
    local current=s.store:GetWater()
    local target=s.initial+math.floor((s.capacity-s.initial)*progress+1e-6)
    if target>current then
        local amount=target-current
        if s.sea then
            local remainder=s.tool._aom_filter_remainder or 0
            amount=math.min(amount,Durability.GetUses(s.tool)*FILTER_DOSES_PER_USE-remainder)
            local filtered=s.store:AddWater(amount)+remainder
            s.tool._aom_filter_remainder=filtered%FILTER_DOSES_PER_USE
            local wear=math.floor(filtered/FILTER_DOSES_PER_USE)
            if wear>0 then Durability.UseAttachment(vehicle,s.tool,wear) end
        else s.store:AddWater(amount) end
    end
    if progress>=1 then M.Cancel(vehicle)end
end
function M.Start(vehicle,rider,source,tool,sea)
    if vehicle._aom_pond_refill then return false end
    vehicle:SetWorking(false)
    if rider.components.locomotor and rider.components.locomotor.Stop then rider.components.locomotor:Stop()end
    local x,_,z=rider.Transform:GetWorldPosition()
    local px,pz
    if sea then px,pz=sea.x,sea.z
    else px,_,pz=source.Transform:GetWorldPosition() end
    local rotation=math.atan2(-(pz-z),px-x)*180/math.pi+180
    rider.Transform:SetRotation(rotation) -- 车头背离水源，后置水箱朝向水面。
    local store=vehicle.components.aom_attachment_store
    local initial,capacity=store:GetWater(),store:GetWaterMax()
    local duration=sea and (capacity-initial)/40 or math.max(1,(capacity-initial)/M.FRESHWATER_RATE)
    local barrel=source and source:HasTag("aom_rain_barrel")
    local s={rider=rider,source=source,barrel=barrel,sea=sea,tool=tool,store=store,initial=initial,capacity=capacity,duration=duration,drawn=0,
        started=GetTime(),x=x,z=z,px=px,pz=pz,rotation=rotation,hoses={},listeners={}}
    vehicle._aom_pond_refill=s
    if vehicle._refilling_net then vehicle._refilling_net:set(true)end
    s.cancel=function()M.Cancel(vehicle,true)end
    local listeners={{"onremove",vehicle},{"onremove",rider},{"dismount",rider},{"death",rider},
        {"onremove",tool},{"aom_attachment_changed",vehicle}}
    if source then listeners[#listeners+1]={"onremove",source} end
    for _,v in ipairs(listeners)do
        vehicle:ListenForEvent(v[1],s.cancel,v[2]);s.listeners[#s.listeners+1]=v
    end
    local ok=not source or barrel or pcall(source.components.watersource.Use,source.components.watersource)
    if not ok or not ValidSession(vehicle,s)then M.Cancel(vehicle);return false end
    for i=1,2 do
        local fx=SpawnPrefab("aom_refill_hose")
        if fx then s.hoses[#s.hoses+1]=fx end
    end
    UpdateHoses(s)
    s.task=vehicle:DoPeriodicTask(M.INTERVAL,M.Update)
    return true
end
return M
