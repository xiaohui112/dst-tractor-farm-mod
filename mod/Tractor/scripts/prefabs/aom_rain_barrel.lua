local L=require("aom_locale").Text
local NAME="aom_rain_barrel"
local CAPACITY=2000
local RAIN_RATE=10
local assets={Asset("ANIM","anim/aom_rain_barrel.zip")}

local function SetWater(inst,amount)
    inst._water=math.max(0,math.min(CAPACITY,math.floor(amount)))
    inst._barrel_water_net:set(inst._water)
end

local function StopCollecting(inst)
    if inst._rain_task then inst._rain_task:Cancel();inst._rain_task=nil end
    inst._rain_since=nil
end

local function CollectRain(inst)
    if not inst._rain_since then return end
    local now=GetTime()
    local total=inst._rain_fraction+math.max(0,now-inst._rain_since)*RAIN_RATE
    local doses=math.floor(total+1e-6)
    inst._rain_since=now
    inst._rain_fraction=math.max(0,total-doses)
    if doses>0 then SetWater(inst,inst._water+doses) end
    if inst._water>=CAPACITY then
        inst._rain_fraction=0
        StopCollecting(inst)
    end
end

local function OnRain(inst,raining)
    if raining then
        if not inst._rain_task and inst._water<CAPACITY then
            inst._rain_since=GetTime()
            inst._rain_task=inst:DoPeriodicTask(1,CollectRain)
        end
    else
        CollectRain(inst)
        StopCollecting(inst)
    end
end

local function GetStoredWater(inst)
    CollectRain(inst)
    return inst._water
end

local function SupplyWater(inst,store,amount)
    local before=store:GetWater()
    local drawn=math.min(GetStoredWater(inst),math.floor(amount),store:GetWaterMax()-before)
    if drawn<=0 then return 0,true end
    -- 同一只桶由主机串行扣水，先占用剂量，避免水箱变化事件重入时重复分配。
    SetWater(inst,inst._water-drawn)
    local ok,accepted=pcall(store.AddWater,store,drawn)
    if not ok then
        accepted=math.max(0,math.min(drawn,store:GetWater()-before))
    end
    if accepted<drawn then SetWater(inst,inst._water+drawn-accepted) end
    OnRain(inst,TheWorld.state.israining)
    return accepted,ok
end

local function Save(inst,data)
    data.water=GetStoredWater(inst)
    data.rain_fraction=inst._rain_fraction
end

local function Load(inst,data)
    StopCollecting(inst)
    local water=data and data.water
    SetWater(inst,type(water)=="number" and water==water and water or 0)
    local fraction=data and data.rain_fraction
    inst._rain_fraction=inst._water<CAPACITY and type(fraction)=="number" and fraction>=0 and fraction<1 and fraction or 0
    OnRain(inst,TheWorld.state.israining)
end

local function fn()
    local inst=CreateEntity()
    inst.entity:AddTransform()
    inst.entity:AddAnimState()
    inst.entity:AddNetwork()
    MakeObstaclePhysics(inst,.55)
    inst.AnimState:SetBank(NAME)
    inst.AnimState:SetBuild(NAME)
    inst.AnimState:PlayAnimation("idle")
    inst:AddTag("structure")
    inst:AddTag(NAME)
    inst._barrel_water_net=net_float(inst.GUID,NAME..".water")
    inst.entity:SetPristine()
    if not TheWorld.ismastersim then return inst end

    inst._water=0
    inst._rain_fraction=0
    inst.GetStoredWater=GetStoredWater
    inst.SupplyWater=SupplyWater
    inst.OnSave=Save
    inst.OnLoad=Load
    inst:WatchWorldState("israining",OnRain)
    OnRain(inst,TheWorld.state.israining)
    inst:ListenForEvent("onremove",StopCollecting)

    inst:AddComponent("inspectable")
    inst.components.inspectable.getspecialdescription=function(item)
        return L("水量 %d/%d",item:GetStoredWater(),CAPACITY)
    end
    inst:AddComponent("lootdropper")
    inst:AddComponent("workable")
    inst.components.workable:SetWorkAction(ACTIONS.HAMMER)
    inst.components.workable:SetWorkLeft(4)
    inst.components.workable:SetOnFinishCallback(function(item)
        item.components.lootdropper:DropLoot()
        item:Remove()
    end)
    return inst
end

return Prefab(NAME,fn,assets),MakePlacer(NAME.."_placer",NAME,NAME,"idle")
