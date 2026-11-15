-- 原版PlayerHUD按type=inv挂到inventorybar.toprow_inv；重建物品栏会保留该父节点。
local M={}
local function Align(self)
    local slots,position,width=require("aom_cargo").Layout(self._aom_cargo_owner)
    self:SetPosition(position)
    for i,slot in ipairs(self.inv or {}) do
        if slots[i] then slot:SetPosition(slots[i]) end
    end
    self.bgimage:ScaleToSize(width,104)
end
function M.Install(widget)
    local open=widget.Open
    local close=widget.Close
    local scale=widget.SetScale
    local refresh=widget.RefreshPosition
    widget.RefreshPosition=function(self,...)
        if self._aom_integrated_cargo then return Align(self) end
        if refresh then return refresh(self,...) end
    end
    widget.SetScale=function(self,...)
        -- 已继承物品栏缩放，避免原版控制器选中时再叠加一次容器倍率。
        if self._aom_integrated_cargo then return scale(self,1)end
        return scale(self,...)
    end
    widget.Open=function(self,container,doer)
        open(self,container,doer)
        if container and container.prefab=="aom_tractor_chassis" then
            self._aom_integrated_cargo=true
            self._aom_cargo_owner=doer
            self:SetScale(1)
            self.slotsperrow=require("aom_cargo").SLOTS
            Align(self)
            self.bgimage:SetClickable(false)
        end
    end
    widget.Close=function(self,...)
        local cargo=self._aom_integrated_cargo
        close(self,...)
        self._aom_integrated_cargo=nil
        self._aom_cargo_owner=nil
        if cargo then scale(self,.6)end
    end
end
return M
