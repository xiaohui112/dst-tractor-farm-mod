-- Test-only: local DST r762172 components/inventory.lua GetActiveItem.
local Inventory={}
function Inventory:GetActiveItem()
    return self.activeitem
end
return Inventory.GetActiveItem
