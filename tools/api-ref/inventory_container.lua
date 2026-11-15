-- Test-only: local DST r762172 PlayerHUD.OpenContainerWidget and Inv.Rebuild row retention.
return function(ContainerWidget,Widget)
local function OpenContainerWidget(self, container, side)
    local containerwidget = ContainerWidget(self.owner)
	local parent
	if side then
		parent = self.controls.containerroot_side
	else
		local _container = container.replica.container
		local _type = _container and (_container.typefn and _container.typefn(container, self.owner) or _container.type)
		parent =
			(_type == "inv" and self.controls.inv.toprow_inv) or
			(_type == "hand_inv" and self.controls.inv.hand_inv) or
			(_type == "side_inv" and self.controls.secondary_status.side_inv) or
			(_type == "side_inv_behind" and self.controls.containerroot_side_behind) or
			(_type == "top_rack" and self.controls.containerroot_under) or
			(_type == "chest_addon" and self.controls.containerroot_over) or
			self.controls.containerroot
	end

	parent:AddChild(containerwidget)

    --self.controls[side and "containerroot_side" or "containerroot"]:AddChild(containerwidget)
    --self.controls.bottom_root:AddChild(containerwidget)
    --self.controls.inv.hand_inv:AddChild(containerwidget)

	containerwidget:MoveToBack()
    containerwidget:Open(container, self.owner)
    self.controls.containers[container] = containerwidget
	self.controls.inv:OnNewContainerWidget(containerwidget)

	if parent == self.controls.containerroot then
		self:CloseSpellWheel()
	end
end


local function RebuildRows(self)
    if self.toprow ~= nil then
		if self.toprow_inv then
			self.toprow:RemoveChild(self.toprow_inv)
		end
        self.toprow:Kill()
		self.inspectcontrol = nil
    end

    if self.bottomrow ~= nil then
        self.bottomrow:Kill()
    end

    self.toprow = self.root:AddChild(Widget("toprow"))
	if self.toprow_inv then
		self.toprow:AddChild(self.toprow_inv)
	else
		self.toprow_inv = self.toprow:AddChild(Widget("toprow_inv"))
	end

	self.bottomrow = self.root:AddChild(Widget("bottomrow"))


end
local function RefreshPosition(self)
	local container = self.container and self.container.replica.container
	local widget = container and container:GetWidget()
	if widget and widget.posfn then --only need to refresh if it's there's a .posfn
		local pos = widget.posfn(self.container, self.owner) or widget.pos
		if pos then
			self:SetPosition(pos)
		end
	end
end

return OpenContainerWidget,RebuildRows,RefreshPosition
end
