-- 原版摘录，仅供回归测试；来源见 README.md。
local scene = {
        rideable = function(inst, doer, actions, right)
            if right and inst:HasTag("rideable") and
				not inst:HasTag("hitched") and
				(not inst:HasTag("dogrider_only") or doer:HasTag("dogrider"))
			then
				if inst:HasTag("woby") then
					local inventory = doer.replica.inventory
					if not (inventory and inventory:IsHeavyLifting()) then
						--No MOUNT action for woby since this is done through command wheel now.
						--Except when heavylifting, during which command wheel is disabled.
						return
					end
				end
                local rider = doer.replica.rider
                if rider ~= nil and not rider:IsRiding() then
                    table.insert(actions, ACTIONS.MOUNT)
                end
            end
        end,

        rider = function(inst, doer, actions)
			if inst == doer then
				local mount = inst.replica.rider:GetMount()
				if mount then
					local container = mount.replica.container
					if container and container:IsOpenedBy(doer) then
						table.insert(actions, ACTIONS.RUMMAGE)
					else
						table.insert(actions, ACTIONS.DISMOUNT)
					end
				end
            end
        end,

}
ACTIONS.MOUNT.fn = function(act)
    if act.target.components.combat ~= nil and act.target.components.combat:HasTarget()
            and (act.target.components.rideable == nil
                or act.target.components.rideable.saddle == nil
                or not act.target.components.rideable.saddle:HasTag("combatmount")) then
        return false, "TARGETINCOMBAT"
    elseif act.target.components.rideable == nil
        or not act.target.components.rideable.canride
        or (act.target.components.health ~= nil and
            act.target.components.health:IsDead())
        or (act.target.components.freezable and
            act.target.components.freezable:IsFrozen())
        or (act.target.components.hitchable ~= nil and
            act.target.components.hitchable:GetHitch() ~= nil)
        or (act.target.hitchingspot ~= nil) then
        return false
    elseif act.target.components.rideable:IsBeingRidden() then
        return false, "INUSE"
    elseif act.target:HasTag("dogrider_only") and act.doer:HasTag("dogrider") and act.target._playerlink ~= act.doer then
        return false
    end

    act.doer.components.rider:Mount(act.target)
    return true
end

ACTIONS.DISMOUNT.fn = function(act)
    if act.doer == act.target and act.doer.components.rider ~= nil and act.doer.components.rider:IsRiding() then
        act.doer.components.rider:Dismount()
        return true
    end
end


return scene
