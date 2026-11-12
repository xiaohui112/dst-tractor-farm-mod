-- 原版 map.lua 挖坑破坏相邻土坑逻辑，仅供测试。
-- https://github.com/vietnd69/dst-scripts/blob/main/components/map.lua
local Map={}
local FIND_SOIL_MUST_TAGS = { "soil" }
function Map:CollapseSoilAtPoint(x, y, z)
	local till_spacing = GetFarmTillSpacing()
    for i, v in ipairs(TheSim:FindEntities(x, y, z, till_spacing, FIND_SOIL_MUST_TAGS)) do
        v:PushEvent(v:GetDistanceSqToPoint(x, y, z) < till_spacing * 0.5 and "collapsesoil" or "breaksoil")
    end
end

return Map
