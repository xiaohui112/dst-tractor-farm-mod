-- Test-only excerpts from local DST r762172 weed_defs.lua, weed_plants.lua and ivy_snare.lua.
local WEED_DEFS={weed_ivy={}}
local function KillOffSnares(inst)
	local snares = inst.snares
	if snares ~= nil then
		inst.snares = nil

		for _, v in ipairs(snares) do
			if v:IsValid() then
				v.owner = nil
				v:KillOff()
			end
		end
	end

	inst.AnimState:PlayAnimation("crop_full", true)
end

local function onsnaredeath(snare)
	local inst = (snare.owner ~= nil and snare.owner:IsValid()) and snare.owner or nil
	if inst ~= nil then
		KillOffSnares(inst)
	end
end

local function dosnaredamage(inst, target)
	if target:IsValid() and target.components.health ~= nil and not target.components.health:IsDead() and target.components.combat ~= nil then
		target.components.combat:GetAttacked(inst, TUNING.WEED_IVY_SNARE_DAMAGE)
		target:PushEvent("snared", { attacker = inst, announce = "ANNOUNCE_SNARED_IVY" })
	end
end

local function SpawnSnare(inst, x, z, r, num, target)
    local count = 0
    local dtheta = TWOPI / num
    local delaytoggle = 0
    local map = TheWorld.Map
    for theta = math.random() * dtheta, TWOPI, dtheta do
        local x1 = x + r * math.cos(theta)
        local z1 = z + r * math.sin(theta)
        if map:IsPassableAtPoint(x1, 0, z1, false, true) and not map:IsPointNearHole(Vector3(x1, 0, z1)) then
            local snare = SpawnPrefab("ivy_snare")
            snare.Transform:SetPosition(x1, 0, z1)

            local delay = delaytoggle == 0 and 0 or .2 + delaytoggle * math.random() * .2
            delaytoggle = delaytoggle == 1 and -1 or 1

			snare.owner = inst
			snare.target = target
			snare.target_max_dist = r + 1.0
            snare:RestartSnare(delay)

			table.insert(inst.snares, snare)
			inst:ListenForEvent("death", onsnaredeath, snare)
            count = count + 1
        end
    end

	return count > 0
end

local function ivy_defend_plant(inst, data)
    local target = data.target
    if target ~= nil and target:IsValid() and not target:HasTag("plantkin") then
		if inst.snares ~= nil and #inst.snares > 0 then
			for _, snare in ipairs(inst.snares) do
				if snare:IsValid() and snare.components.health ~= nil and not snare.components.health:IsDead() then
					snare.components.health:Kill()
				end
			end
		end
		inst.snares = {}

        local x, y, z = target.Transform:GetWorldPosition()
        local islarge = target:HasTag("largecreature")
        local r = target:GetPhysicsRadius(0) + (islarge and 1.4 or .4)
        local num = islarge and 12 or 6
		if SpawnSnare(inst, x, z, r, num, target) then
			inst:DoTaskInTime(0.25, dosnaredamage, target)

			inst.AnimState:PlayAnimation("full_atk", true)
		end
	end
end

WEED_DEFS.weed_ivy.OnMakeFullFn = function(inst, isfull)
	local has_tag = inst:HasTag("farm_plant_defender")
	if isfull and not has_tag then
		inst:AddTag("farm_plant_defender")
	elseif not isfull and has_tag then
		inst:Remove("farm_plant_defender")
	end
end

WEED_DEFS.weed_ivy.masterpostinit = function(inst)
	inst:ListenForEvent("defend_farm_plant", ivy_defend_plant)
	inst:ListenForEvent("onremove", KillOffSnares)
end


local function DoKillOff(inst)
	if inst.components.health ~= nil and not inst.components.health:IsDead() then
		inst.components.health:Kill()
	end
end

local function KillOff(inst)
	inst:RemoveTag("groundspike")
	if inst.validate_task ~= nil then
		inst.validate_task:Cancel()
		inst.validate_task = nil
	end
	inst:DoTaskInTime(0.2 + math.random() * 0.5, DoKillOff)
end

local function OnDeath(inst)
	inst.AnimState:PlayAnimation("spike_pst")
	inst:RemoveTag("groundspike")
    inst:AddTag("NOCLICK")
    inst.Physics:SetActive(false)
	if inst.validate_task ~= nil then
		inst.validate_task:Cancel()
		inst.validate_task = nil
	end
    inst:DoTaskInTime(1.5, inst.Remove)
end


local function call_for_reinforcements(inst, target)
	inst:RemoveTag("farm_plant_defender")

	local x, y, z = inst.Transform:GetWorldPosition()
	local defenders = TheSim:FindEntities(x, y, z, TUNING.FARM_PLANT_DEFENDER_SEARCH_DIST, {"farm_plant_defender"})
	for _, defender in ipairs(defenders) do
		if defender.components.burnable == nil or not defender.components.burnable.burning then
			defender:PushEvent("defend_farm_plant", {source = inst, target = target})
			break
		end
	end
end

local function UpdateResearchStage(inst, stage)
	if stage == 1 and inst.mature then	-- stage 3 + mature = picked state
		stage = #inst.weed_def.plantregistryinfo
	end

	inst._research_stage:set(stage - 1) -- to make it a 0 a based range
end

local function GetResearchStage(inst)
	return inst._research_stage:value() + 1	-- +1 to make it 1 a based rage
end

local function GetPlantRegistryKey(inst)
	return inst.plantregistrykey
end

local function ConsumeNutrients(inst)
	if TheWorld.components.farming_manager ~= nil then
		local x, y, z = inst.Transform:GetWorldPosition()
		TheWorld.components.farming_manager:CycleNutrientsAtPoint(x, y, z, inst.weed_def.nutrient_consumption, nil)
	end
end

local function TryGrowResume(inst)
	if inst.components.growable ~= nil and (inst.components.burnable == nil or not inst.components.burnable:IsBurning()) then
		inst.components.growable:Resume()
	end
end


return {Ivy=WEED_DEFS.weed_ivy,KillOff=KillOff,OnDeath=OnDeath,Broadcast=call_for_reinforcements}
