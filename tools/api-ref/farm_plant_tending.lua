-- Native farm_plants.lua excerpt from installed game; test only.
local function on_happiness_changed(inst, stressed, doer)
    inst:DoTaskInTime(0.5 + math.random() * 0.5, function()
        local fx = SpawnPrefab(stressed and "farm_plant_unhappy" or "farm_plant_happy")
        fx.Transform:SetPosition(inst.Transform:GetWorldPosition())
    end)
end

local function ontendto(inst, doer)
    inst.components.farmplantstress:SetStressed("happiness", false, doer)

    return true
end


return {on_happiness_changed=on_happiness_changed,ontendto=ontendto}
