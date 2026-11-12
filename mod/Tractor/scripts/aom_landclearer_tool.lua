-- 开垦机耐久独立于底盘及洒水机的储水次数。
local Def=require("aom_equipment_defs").plow
local M={MAX_USES=Def.uses,REPAIR_USES=Def.repair}
function M.Get(inst)
    local c=inst.components.container
    local item=require("aom_attachment_mount").Get(inst)
    return item and item:IsValid() and item.attachment_type=="plow" and item or nil
end
function M.CanWork(inst)
    local item=M.Get(inst)
    if not item or not item.components.finiteuses then return false,"NO_ATTACHMENT" end
    if item.components.finiteuses:GetUses()<=0 then return false,"BROKEN_ATTACHMENT" end
    return true
end
function M.Use(inst)
    local item=M.Get(inst)
    require("aom_durability").UseAttachment(inst,item)
end
function M.Repair(inst)
    return require("aom_durability").RepairAttachment(M.Get(inst))
end
return M
