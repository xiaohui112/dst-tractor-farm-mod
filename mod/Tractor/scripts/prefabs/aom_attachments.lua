-- Independent world equipment; no inventoryitem and no manual carrying.
local AOM=require("aom_common")
local Irrigator=require("aom_irrigator")
local Durability=require("aom_durability")
local Mount=require("aom_attachment_mount")
local SCALE=require("aom_model_scale")
local assets={Asset("ANIM","anim/aom_attachment_shared.zip")}
local function MakeAttachment(name,kind)
    local function fn()
        local inst=CreateEntity()
        inst.entity:AddTransform();inst.entity:AddAnimState();inst.entity:AddNetwork()
        inst.Transform:SetEightFaced()
        MakeObstaclePhysics(inst,.5)
        inst.AnimState:SetBank("aom_attachment_shared")
        inst.AnimState:SetBuild("aom_attachment_shared")
        inst.AnimState:SetScale(SCALE,SCALE,SCALE)
        inst.AnimState:PlayAnimation(kind)
        inst:AddTag(AOM.TAG.ATTACHMENT);inst:AddTag("structure")
        inst.attachment_type=kind
        inst._aom_vehicle=net_entity(inst.GUID,"aom_equipment.vehicle","aomequipmentdirty")
        inst._durability_net=net_float(inst.GUID,"aom_equipment.durability","aomequipmentdirty")
        inst._aom_working=net_bool(inst.GUID,"aom_equipment.working","aomworkanimationdirty")
        if kind=="irrigator" then
            inst._aom_water_net=net_float(inst.GUID,"aom_equipment.water","aomequipmentwaterdirty")
            -- 水量借用finiteuses存储，不应被通用信息Mod标成机械耐久。
            inst:AddTag("hide_percentage")
        end
        inst.entity:SetPristine()
        inst:DoPeriodicTask(.1,Mount.UpdateVisual)
        if not TheWorld.ismastersim then return inst end
        inst:ListenForEvent("onremove",function(item)require("aom_attachment_animation").ClearEffects(item)end)
        inst:AddComponent("inspectable")
        inst.components.inspectable.getspecialdescription=function(item)
            local text=require("aom_locale").Text("机械耐久 %d/%d；损坏后用燧石维修",Durability.GetUses(item),Durability.TOOLS[kind])
            if kind=="irrigator" then
                text=text.."\n"..require("aom_locale").Text("水量 %d/%d",item.components.finiteuses:GetUses(),Irrigator.Capacity())
            end
            return text
        end
        if kind~="fertilizer" then
            inst:AddComponent("finiteuses")
            if kind=="irrigator" then Irrigator.Setup(inst)
            else
                inst.components.finiteuses:SetMaxUses(Durability.TOOLS[kind])
                inst.components.finiteuses:SetUses(Durability.TOOLS[kind])
                inst.components.finiteuses:SetOnFinished(Durability.OnAttachmentFinished)
            end
        end
        if kind=="irrigator" or kind=="fertilizer" then inst._aom_machine_uses=Durability.TOOLS[kind] end
        inst._durability_net:set(Durability.GetUses(inst))
        local save=inst.OnSave
        local load=inst.OnLoad
        inst.OnSave=function(item,data)
            if save then save(item,data) end
            data.aom_machine_uses=item._aom_machine_uses
        end
        inst.OnLoad=function(item,data)
            if load then load(item,data) end
            if data and data.aom_machine_uses~=nil then
                item._aom_machine_uses=math.max(0,math.min(Durability.TOOLS[kind],data.aom_machine_uses))
            end
            item._durability_net:set(Durability.GetUses(item))
        end
        return inst
    end
    local placer=MakePlacer(name.."_placer","aom_attachment_shared","aom_attachment_shared",kind,false,false,false,SCALE,nil,"eight")
    return Prefab(name,fn,assets,{"aom_work_soil","aom_work_seeder","aom_work_irrigator",
        "aom_work_fertilizer","aom_work_weeder","aom_work_harvester"}),placer
end
local plow,plow_placer=MakeAttachment("aom_landclearer","plow")
local legacy,legacy_placer=MakeAttachment("aom_plow","plow")
local seeder,seeder_placer=MakeAttachment("aom_seeder","seeder")
local water,water_placer=MakeAttachment("aom_irrigator","irrigator")
local fertilizer,fertilizer_placer=MakeAttachment("aom_fertilizer","fertilizer")
local weeder,weeder_placer=MakeAttachment("aom_weeder","weeder")
local harvester,harvester_placer=MakeAttachment("aom_harvester","harvester")
return plow,plow_placer,legacy,legacy_placer,seeder,seeder_placer,water,water_placer,
    fertilizer,fertilizer_placer,weeder,weeder_placer,harvester,harvester_placer
