--[[
	Tractor —— 播种策略

	三种策略：
	  1. SEQUENTIAL 按种子顺序播种
	  2. GIANT_TEMPLATE 巨大化·模版
	  3. GIANT          巨大化·最优（保留旧存档标识）

	自动规划由 aom_auto_seeding 管理。
]]

local AOMSeedStrategy = {}

-- 作物 seed -> 作物内部名 的映射依据：
-- 原版 seeds 用 components.farmplantable.plant 存"会长成什么"，
-- 对作物种子是 "farm_plant_<作物名>"（farm_plant_defs.lua:267 data.seed = veggie.."_seeds"）
-- 所以这里不依赖种子 prefab 名，而是读 plant 字段，更稳。
local PLANT_PREFIX = "farm_plant_"

-- 从种子的 farmplantable 读出它会长成哪种作物；读不出返回 nil
function AOMSeedStrategy.Normalize(mode)
    return (mode == "GIANT" or mode == "GIANT_TEMPLATE") and mode or "SEQUENTIAL"
end

function AOMSeedStrategy.IsGiant(mode)return mode == "GIANT" or mode == "GIANT_TEMPLATE" end
local NEXT_MODE={SEQUENTIAL="GIANT_TEMPLATE",GIANT_TEMPLATE="GIANT",GIANT="SEQUENTIAL"}
function AOMSeedStrategy.Next(mode)return NEXT_MODE[AOMSeedStrategy.Normalize(mode)]end

function AOMSeedStrategy.GetCropOfSeedItem(item)
	if item == nil or item.components.farmplantable == nil then
		return nil
	end
	local plant = item.components.farmplantable.plant
	if type(plant) == "function" then
		local ok, v = pcall(plant, item)
		plant = ok and v or nil
	end
	if type(plant) ~= "string" then
		return nil
	end
	if plant == "farm_plant_randomseed" then
		return nil            -- 随机种子，不属于任何具体作物
	end
	if string.sub(plant, 1, #PLANT_PREFIX) == PLANT_PREFIX then
		return string.sub(plant, #PLANT_PREFIX + 1)
	end
	return nil
end

---------------------------------------------------------------------------
-- 策略 1：按顺序
---------------------------------------------------------------------------

-- 返回要种的那颗种子（保持仓内顺序）
function AOMSeedStrategy.PickSequential(item_list)
	for _, item in ipairs(item_list) do
		if item ~= nil and item:IsValid() then
			return item
		end
	end
	return nil
end

-- 所有配比只从坐标规划器读取，避免两份数据发生漂移。
function AOMSeedStrategy.GetSeasonCombos(season)
    return require("aom_block_plan").BLOCKS[season or "autumn"]
end
function AOMSeedStrategy.GetAllCombos()
    return require("aom_block_plan").BLOCKS
end

return AOMSeedStrategy
