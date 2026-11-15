-- 水箱单位始终为一次普通水壶用量；土壤水分点数只交给原版管理器处理。
local Soil=require("aom_soil_moisture")
local L=require("aom_locale").Text
local M={POND_DISTANCE=3,WATER_CAPACITY=400}
function M.Capacity() return M.WATER_CAPACITY end

function M.Setup(inst)
    local uses=inst.components.finiteuses
    uses:SetMaxUses(M.Capacity())
    uses:SetDoesNotStartFull(true) -- 满罐也必须显式保存，否则空罐构造会吞掉满罐存档
    uses:SetUses(0)
    local function SyncWater()
        if inst._aom_water_net then inst._aom_water_net:set(uses:GetUses()) end
    end
    inst:ListenForEvent("percentusedchange",SyncWater)
    SyncWater()
    inst.OnSave=function(_,data) data.aom_water_version=1 end
    -- EntityScript 先加载组件，再调用实体 OnLoad；此处迁移不会被 finiteuses 覆盖。
    inst.OnLoad=function(item,data)
        local saved=data and data.finiteuses and data.finiteuses.uses
        if not data or not data.aom_water_version then
            -- 旧版满罐100不会写 finiteuses；缺省表示旧满罐，不是新版空罐。
            if saved==nil then saved=40 end -- 保留旧版迁移语义，不随新容量凭空补水。
            if type(saved)=="number" then saved=math.min(saved,40) end
        elseif saved==nil then saved=0 end
        if type(saved)~="number" or saved~=saved then saved=0 end
        item.components.finiteuses:SetUses(math.max(0,math.min(M.Capacity(),math.floor(saved))))
    end
end

function M.IsSource(item)
    return item~=nil and (item.prefab=="ice" or item.prefab=="wateringcan" or item.prefab=="premiumwateringcan")
end

function M.Load(store,item)
    if not M.IsSource(item) then return false,L("需要水壶或冰块。") end
    local room=store:GetWaterMax()-store:GetWater()
    if room<=0 then return false,L("水箱已满。") end
    if item.prefab=="ice" then
        if store:AddWater(1)~=1 then return false,L("无法补水。") end
        local stack=item.components.stackable
        if stack and stack:StackSize()>1 then stack:Get(1):Remove() else item:Remove() end
    else
        local uses=item.components.finiteuses
        if not uses or not item.components.fillable then return false,L("需要有效的水壶。") end
        -- 普通/高级水壶原版每次均为25水分；高级壶只增加容量。
        local count=math.min(room,math.max(0,math.floor(uses:GetUses())))
        if count<=0 then return false,L("水壶已空，请先装水。") end
        local added=store:AddWater(count)
        if added<=0 then return false,L("无法补水。") end
        uses:Use(added)
    end
    return true,L("水箱：%d/%d",store:GetWater(),store:GetWaterMax())
end

-- 骑乘时直接从池塘补满；服务端重新校验骑手、真实挂件、水源状态和距离。
function M.RefillFromPond(doer,pond)
    if not doer or not doer:IsValid() or doer:HasTag("playerghost")
        or not pond or not pond:IsValid() or not pond:HasTag("pond")
        or not pond:HasTag("watersource") then return false,L("池塘现在无法取水。") end
    local source=pond.components.watersource
    if not source or not source.available then return false,L("池塘现在无法取水。") end
    local rider=doer.components.rider
    local vehicle=rider and rider:IsRiding() and rider:GetMount() or nil
    if not vehicle or not vehicle:IsValid() or vehicle.prefab~="aom_tractor_chassis"
        or vehicle._rider~=doer or vehicle._destroyed
        or vehicle.components.health and vehicle.components.health:IsDead()
        or doer.components.health and doer.components.health:IsDead() then return false,L("请先驾驶拖拉机。") end
    local store=vehicle.components.aom_attachment_store
    local tool=require("aom_attachment_mount").Get(vehicle)
    if not store or vehicle._attachment_type~="irrigator" or not tool
        or not tool:IsValid() or tool.prefab~="aom_irrigator" then return false,L("请装入当前挂件需要的物料。") end
    local distance=M.POND_DISTANCE+pond:GetPhysicsRadius(0)+doer:GetPhysicsRadius(0)
    if doer:GetDistanceSqToInst(pond)>distance*distance then return false,L("请驾驶拖拉机靠近池塘。") end
    local room=store:GetWaterMax()-store:GetWater()
    if room<=0 then return false,L("水箱已满。") end
    if require("aom_pond_refill").Start(vehicle,doer,pond,tool) then
        return true,L("正在补水（5秒）；移动或下车中止")
    end
    return false,L(vehicle._aom_pond_refill and "正在补水（5秒）；移动或下车中止" or "无法补水。")

end

function M.Sync(inst)
    local store=inst.components.aom_attachment_store
    if inst._water_net and store then inst._water_net:set(store:GetWater()) end
    if inst._watermax_net and store then inst._watermax_net:set(store:GetWaterMax()) end
end

-- 一次经过浇到原版上限；缺水保留进度并停机。燃料/底盘由驾驶层按整格结算一次。
function M.WaterTile(inst,x,z)
    local farm=require("aom_farm_work")
    if not farm.IsFarmTileAt(x,0,z) then return false,"NOTHING_TO_DO",true end
    local moisture,reason=Soil.Read(x,0,z)
    if moisture==nil then return false,reason,false end
    if moisture>=Soil.Max() then return false,"NOTHING_TO_DO",true end
    if inst._fuel:value()<require("aom_common").FUEL_PER_TICK then return false,"NO_FUEL",false end
    local store=inst.components.aom_attachment_store
    local changed=false
    -- 从 TUNING 推导上限；逐次读实际结果，也适应雨天原版的最低湿度钳制。
    local dose=Soil.Dose()
    if dose<=0 or Soil.Max()<=0 then return false,"MOISTURE_UNAVAILABLE",false end
    for _=1,math.ceil(Soil.Max()/dose)+1 do
        if not store:TakeWater() then return changed,"EMPTY",false end
        local worked,why=Soil.Apply(x,0,z)
        if not worked then store:ReturnWater();return changed,why,false end
        changed=true
        if why then return true,why,false end
        moisture,reason=Soil.Read(x,0,z)
        if moisture==nil then return true,reason,false end
        if moisture>=Soil.Max() then return true,nil,true end
    end
    return changed,"WATER_FAILED",false
end

return M
