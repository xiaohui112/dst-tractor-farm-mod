-- 复用原版 dirt_puff 的动画（fx.lua），改为小尺寸黑色烟团。
local assets={Asset("ANIM","anim/smoke_puff_small.zip")}
local function fn()
    local inst=CreateEntity()
    inst.entity:AddTransform()
    inst.entity:AddAnimState()
    inst.entity:AddNetwork()
    inst.AnimState:SetBank("small_puff")
    inst.AnimState:SetBuild("smoke_puff_small")
    inst.AnimState:PlayAnimation("puff")
    inst.AnimState:SetMultColour(.04,.04,.04,.8)
    inst.Transform:SetScale(.45,.45,.45)
    inst:AddTag("FX")
    inst:AddTag("NOCLICK")
    inst.entity:SetPristine()
    if not TheWorld.ismastersim then return inst end
    inst.persists=false
    inst:ListenForEvent("animover",inst.Remove)
    inst:DoPeriodicTask(.1,function()
        local x,y,z=inst.Transform:GetWorldPosition()
        inst.Transform:SetPosition(x,y+.06,z)
    end)
    inst:DoTaskInTime(2,inst.Remove)
    return inst
end
return Prefab("aom_exhaust_puff",fn,assets)
