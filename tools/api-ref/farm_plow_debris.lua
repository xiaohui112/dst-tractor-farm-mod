-- 原版摘录；Finished、VecUtil_DistSq 等由测试引擎提供，见 README.md。
local function IsPosWithin(x, z, positions, dist)
    dist = dist * dist
    for i, v in ipairs(positions) do
        local distance = VecUtil_DistSq(x, z, v.x, v.z)
        if distance < dist then
            return true
        end
    end
    return false
end

local function OnTerraform(inst, pt, old_tile_type, old_tile_turf_prefab)
    -- spawn some farm_soil_debris and farm_soil
    local cx, cy, cz = TheWorld.Map:GetTileCenterPoint(pt:Get())
    local TILE_EXTENTS = TILE_SCALE * 0.9
    local spawned_positions = {}
    for i = 1, math.random(TUNING.FARM_PLOW_DRILLING_DEBRIS_MIN, TUNING.FARM_PLOW_DRILLING_DEBRIS_MAX) do
        local x = cx + (math.random() * TILE_EXTENTS) - TILE_EXTENTS/2
        local z = cz + (math.random() * TILE_EXTENTS) - TILE_EXTENTS/2
        if not IsPosWithin(x, z, spawned_positions, 1) then
            table.insert(spawned_positions, {x = x, z = z})
			TheWorld.Map:CollapseSoilAtPoint(x, cy, z)
            SpawnPrefab("farm_soil_debris").Transform:SetPosition(x, cy, z)
        end
    end

	SpawnPrefab("dirt_puff").Transform:SetPosition(cx + math.random() + 1, cy, cz + math.random() + 1)
	SpawnPrefab("dirt_puff").Transform:SetPosition(cx - math.random() - 1, cy, cz + math.random() + 1)
	SpawnPrefab("dirt_puff").Transform:SetPosition(cx + math.random() + 1, cy, cz - math.random() - 1)
	SpawnPrefab("dirt_puff").Transform:SetPosition(cx - math.random() - 1, cy, cz - math.random() - 1)

	Finished(inst)
end

return OnTerraform
