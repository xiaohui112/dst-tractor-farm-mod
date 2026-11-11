-- 原版 soil_amender 的返空瓶回调原文摘录，仅用于测试。
local function bottlereturnfn(inst, is_final_use, doer, target)
	if is_final_use then
		local x, y, z = (target ~= nil and target or inst).Transform:GetWorldPosition()
		inst:Remove()
		inst = nil
		local refund = SpawnPrefab("messagebottleempty")
		if doer ~= nil and doer.components.inventory ~= nil then
			doer.components.inventory:GiveItem(refund, nil, Vector3(x, y, z))
		else
			refund.Transform:SetPosition(x, y, z)
		end
	end
end

return bottlereturnfn
