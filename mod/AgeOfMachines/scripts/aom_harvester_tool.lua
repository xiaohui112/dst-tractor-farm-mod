-- 收割机按实际作业地块扣耐久；普通采摘与巨大产物拆分共用一次结算。
local M={MAX_USES=40,REPAIR_USES=10}
function M.Get(inst)
    local c=inst.components.container
    local item=c and c:GetItemInSlot(1) or nil
    return item and item.attachment_type=="harvester" and item or nil
end
function M.CanWork(inst)
    local item=M.Get(inst)
    if not item or not item.components.finiteuses then return false,"NO_ATTACHMENT" end
    if item.components.finiteuses:GetUses()<=0 then return false,"BROKEN_HARVESTER" end
    return true
end
function M.Use(inst)
    local item=M.Get(inst)
    if item then item.components.finiteuses:Use(1) end
end
function M.Repair(inst)
    local item=M.Get(inst)
    local uses=item and item.components.finiteuses
    if not uses or uses:GetUses()>=M.MAX_USES then return false end
    uses:SetUses(math.min(M.MAX_USES,uses:GetUses()+M.REPAIR_USES))
    return true
end
return M
