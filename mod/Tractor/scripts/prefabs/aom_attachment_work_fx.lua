-- 全部是纯显示实体：不加物理、库存、投射物、肥料或农业组件。
local SCALE=require("aom_model_scale")
local assets={
    Asset("ANIM","anim/aom_attachment_fx.zip"),
    Asset("ANIM","anim/aom_attachment_water.zip"),
    Asset("ANIM","anim/player_actions_farming.zip"),
    Asset("ANIM","anim/mole_move_fx.zip"),
}
local function Make(name,bank,build,anim,loop,scale)
    local function fn()
        local inst=CreateEntity()
        inst.entity:AddTransform()
        inst.entity:AddAnimState()
        inst.entity:AddNetwork()
        inst.Transform:SetEightFaced()
        inst.AnimState:SetBank(bank)
        inst.AnimState:SetBuild(build)
        inst.AnimState:SetScale(SCALE*scale,SCALE*scale,SCALE*scale)
        inst.AnimState:PlayAnimation(anim,loop)
        inst:AddTag("FX");inst:AddTag("NOCLICK");inst:AddTag("NOBLOCK")
        inst.persists=false
        inst.entity:SetPristine()
        if not TheWorld.ismastersim then return inst end
        -- 即使拥有者被其它 Mod 删除，短时实体也不会留在世界或存档中。
        if not loop then inst:ListenForEvent("animover",inst.Remove) end
        inst._aom_timeout=inst:DoTaskInTime(1,inst.Remove)
        return inst
    end
    return Prefab(name,fn,assets)
end
return Make("aom_work_soil","mole_fx","mole_move_fx","move",false,.35),
    Make("aom_work_seeder","aom_attachment_fx","aom_attachment_fx","seed",false,1),
    Make("aom_work_weeder","aom_attachment_fx","aom_attachment_fx","roots",false,1),
    Make("aom_work_harvester","aom_attachment_fx","aom_attachment_fx","chaff",false,1),
    Make("aom_work_fertilizer","aom_attachment_fx","aom_attachment_fx","fertilizer",true,1),
    Make("aom_work_irrigator","aom_attachment_water","player_actions_farming","spray",true,1)
