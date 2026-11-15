-- Test-only: local DST r762172 farm_plants and growable original excerpts.
local function call_for_reinforcements(inst, target)
    if target ~= nil and not target:HasTag("plantkin") then
        local x, y, z = inst.Transform:GetWorldPosition()
        local defenders = TheSim:FindEntities(x, y, z, TUNING.FARM_PLANT_DEFENDER_SEARCH_DIST, {"farm_plant_defender"})
        for _, defender in ipairs(defenders) do
            if defender.components.burnable == nil or not defender.components.burnable.burning then
                defender:PushEvent("defend_farm_plant", {source = inst, target = target})
                break
            end
        end
    end
end

local function dig_up(inst, worker)
    if inst.components.lootdropper ~= nil then
        inst.components.lootdropper:DropLoot()
    end

    call_for_reinforcements(inst, worker)

    if inst.components.growable ~= nil then
        local stage_data = inst.components.growable:GetCurrentStageData()
        if stage_data ~= nil and stage_data.dig_fx ~= nil then
            SpawnPrefab(stage_data.dig_fx).Transform:SetPosition(inst.Transform:GetWorldPosition())
        end
    end

    inst:Remove()
end

local function OnPicked(inst, doer)
    local x, y, z = inst.Transform:GetWorldPosition()
    if TheWorld.Map:GetTileAtPoint(x, y, z) == WORLD_TILES.FARMING_SOIL then
        local soil = SpawnPrefab("farm_soil")
        soil.Transform:SetPosition(x, y, z)
        soil:PushEvent("breaksoil")
    end

    if not inst.is_oversized and inst:HasTag("farm_plant_killjoy") and TryLuckRoll(doer, TUNING.FARMPLANT_SPAWN_FRUITFLY_ON_WEED_CHANCE, LuckFormulas.FruitFlyOnPickedWeed) then
        local fruitfly = SpawnPrefab("fruitfly")
        fruitfly.Transform:SetPosition(x, y, z)
    end

    call_for_reinforcements(inst, doer)
end

local function MakePickable(inst, enable, product)
    if not enable then
        inst:RemoveTag("fruitflyspawner")
        inst:RemoveComponent("pickable")
    else
        if inst.components.pickable == nil then
            inst:AddComponent("pickable")
            inst.components.pickable.onpickedfn = OnPicked
            inst.components.pickable.remove_when_picked = true
        end
        inst.components.pickable:SetUp(nil)
        inst.components.pickable.use_lootdropper_for_product = true
        inst.components.pickable.picksound = product == "spoiled_food" and "dontstarve/wilson/harvest_berries" or "dontstarve/wilson/pickup_plants"
        if not inst:HasTag("farm_plant_killjoy") then
            inst:AddTag("fruitflyspawner")
        else
            inst:RemoveTag("fruitflyspawner")
        end
    end
end

local function MakeRotten(inst, rotten)
    if rotten then
        inst:AddTag("farm_plant_killjoy") -- party pooper...
        inst:AddTag("pickable_harvest_str")
    else
        inst:RemoveTag("farm_plant_killjoy")
        inst:RemoveTag("pickable_harvest_str")
    end
end

local spoiled_food_loot = {"spoiled_food"}

local function SetupLoot(lootdropper)
    local inst = lootdropper.inst

    if inst:HasTag("farm_plant_killjoy") then -- if rotten
        lootdropper:SetLoot(inst.is_oversized and inst.plant_def.loot_oversized_rot or spoiled_food_loot)
    elseif inst.components.pickable ~= nil then
        local plant_stress = inst.components.farmplantstress ~= nil and inst.components.farmplantstress:GetFinalStressState() or FARM_PLANT_STRESS.HIGH

        if inst.is_oversized then
            lootdropper:SetLoot({inst.plant_def.product_oversized})
        elseif plant_stress == FARM_PLANT_STRESS.LOW or plant_stress == FARM_PLANT_STRESS.NONE then
            lootdropper:SetLoot({inst.plant_def.product, inst.plant_def.seed, inst.plant_def.seed})
        elseif plant_stress == FARM_PLANT_STRESS.MODERATE then
            lootdropper:SetLoot({inst.plant_def.product, inst.plant_def.seed})
        else -- plant_stress == FARM_PLANT_STRESS.HIGH
            lootdropper:SetLoot({inst.plant_def.product})
        end
    end
end

local Growable={}
function Growable:GetCurrentStageData()
    return self.stages[self.stage]
end

return {OnPicked=OnPicked,MakeRotten=MakeRotten,MakePickable=MakePickable,SetupLoot=SetupLoot,Dig=dig_up,GetCurrentStageData=Growable.GetCurrentStageData}
