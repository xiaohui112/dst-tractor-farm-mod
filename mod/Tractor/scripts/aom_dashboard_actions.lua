-- 仪表维修/加油：服务端读取鼠标物品，只操作请求对应的当前坐骑。
local Durability=require("aom_durability")
local L=require("aom_locale").Text
local M={}
local function ConsumeOne(item)
    local stack=item.components.stackable
    if stack and stack:StackSize()>1 then stack:Get(1):Remove()else item:Remove()end
end
function M.Perform(player,vehicle,part)
    if not TheWorld.ismastersim or not player or not player:IsValid()
        or player:HasTag("playerghost") or player.components.health and player.components.health:IsDead()
        or not vehicle or not vehicle:IsValid() or vehicle.prefab~="aom_tractor_chassis" then return false,"INVALID_TARGET" end
    local rider=player.components.rider
    if not rider or not rider:IsRiding() or rider:GetMount()~=vehicle or vehicle._rider~=player
        or not vehicle.components.rideable or vehicle.components.rideable:GetRider()~=player then return false,"NOT_DRIVING" end
    if player.sg and player.sg:HasStateTag("busy") then return false,"BUSY" end
    if vehicle._destroyed or vehicle.components.health:IsDead() then return false,"DESTROYED" end
    if part~="health" and part~="chassis" and part~="fuel" and part~="tool" then return false,"GENERIC" end
    local inventory=player.components.inventory
    local item=inventory and inventory:GetActiveItem()
    if not item or not item:IsValid() then return false,"NO_ACTIVE_ITEM" end
    if part=="fuel" then
        local before=vehicle._fuel:value()
        local ok,reason=vehicle:TryRefuel(player,item)
        if not ok then return false,reason end
        return true,L("燃料 +%d",vehicle._fuel:value()-before)
    elseif part=="tool" then
        local tool=require("aom_attachment_mount").Get(vehicle)
        if not tool then return false,"NO_ATTACHMENT" end
        if item.prefab~="flint" then return false,"REPAIR_FLINT" end
        local max=require("aom_equipment_defs")[tool.attachment_type].uses
        local before=Durability.GetUses(tool)
        if before>=max then return false,"REPAIR_FULL" end
        ConsumeOne(item)
        Durability.RepairAttachment(tool)
        Durability.Sync(vehicle)
        return true,L("挂件耐久 +%d",Durability.GetUses(tool)-before)
    end
    local ok,reason,gain=vehicle:TryRepair(player,item,part)
    if not ok then return false,reason end
    return true,L(part=="health" and "生命 +%d" or "底盘耐久 +%d",gain)
end
return M
