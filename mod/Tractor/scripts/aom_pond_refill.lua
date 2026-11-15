-- 五秒持续吸水；保留已吸入的水，终止时回收任务、监听与软管。
local M={DURATION=5,INTERVAL=.1}
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
    local rider,pond,tool=s.rider,s.pond,s.tool
    if not Valid(vehicle) or not Valid(rider) or not Valid(pond) or not Valid(tool)
        or vehicle._destroyed or rider:HasTag("playerghost")
        or vehicle._rider~=rider or not rider.components.rider
        or rider.components.rider:GetMount()~=vehicle
        or require("aom_attachment_mount").Get(vehicle)~=tool
        or not pond:HasTag("watersource") or not pond.components.watersource
        or not pond.components.watersource.available then return false end
    local x,_,z=rider.Transform:GetWorldPosition()
    local px,_,pz=pond.Transform:GetWorldPosition()
    if (px-s.px)^2+(pz-s.pz)^2>.01 then return false end
    local turn=math.abs((rider.Transform:GetRotation()-s.rotation+180)%360-180)
    return (x-s.x)^2+(z-s.z)^2<=.01 and turn<=10
end
function M.Update(vehicle)
    local s=vehicle._aom_pond_refill
    if not s then return end
    if not ValidSession(vehicle,s) then M.Cancel(vehicle,true);return end
    UpdateHoses(s)
    local progress=math.clamp((GetTime()-s.started)/M.DURATION,0,1)
    local current=s.store:GetWater()
    local target=s.initial+math.floor((s.capacity-s.initial)*progress+1e-6)
    if target>current then s.store:AddWater(target-current)end
    if progress>=1 then M.Cancel(vehicle)end
end
function M.Start(vehicle,rider,pond,tool)
    if vehicle._aom_pond_refill then return false end
    vehicle:SetWorking(false)
    if rider.components.locomotor and rider.components.locomotor.Stop then rider.components.locomotor:Stop()end
    local x,_,z=rider.Transform:GetWorldPosition()
    local px,_,pz=pond.Transform:GetWorldPosition()
    local rotation=math.atan2(-(pz-z),px-x)*180/math.pi+180
    rider.Transform:SetRotation(rotation) -- 车头背离水源，后置水箱朝向池塘。
    local store=vehicle.components.aom_attachment_store
    local s={rider=rider,pond=pond,tool=tool,store=store,initial=store:GetWater(),capacity=store:GetWaterMax(),
        started=GetTime(),x=x,z=z,px=px,pz=pz,rotation=rotation,hoses={},listeners={}}
    vehicle._aom_pond_refill=s
    if vehicle._refilling_net then vehicle._refilling_net:set(true)end
    s.cancel=function()M.Cancel(vehicle,true)end
    for _,v in ipairs({{"onremove",vehicle},{"onremove",rider},{"dismount",rider},{"death",rider},
        {"onremove",pond},{"onremove",tool},{"aom_attachment_changed",vehicle}})do
        vehicle:ListenForEvent(v[1],s.cancel,v[2]);s.listeners[#s.listeners+1]=v
    end
    local ok=pcall(pond.components.watersource.Use,pond.components.watersource)
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
