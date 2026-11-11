-- 除草机按实际作业地块扣耐久，耗尽保留物品，燧石维修沿用开垦机交互。
local M={MAX_USES=50,REPAIR_USES=10}
function M.Get(inst)
    local c=inst.components.container
    local item=c and c:GetItemInSlot(1) or nil
    return item and item.attachment_type=="weeder" and item or nil
end
function M.CanWork(inst)
    local item=M.Get(inst)
    if not item or not item.components.finiteuses then return false,"NO_ATTACHMENT" end
    if item.components.finiteuses:GetUses()<=0 then return false,"BROKEN_WEEDER" end
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
