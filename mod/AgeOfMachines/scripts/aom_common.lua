--[[
	Age of Machines · 农机时代 —— 客户端公共定义

	这里只放"客户端也要认识"的东西：
	- 挂件类型常量
	- Action 定义（客户端需要用于提示）
	- 字符串
]]

local MOD_PREFIX = "aom"

local ATTACHMENT_TYPE = {
	PLOW = "plow",
	SEEDER = "seeder",
	IRRIGATOR = "irrigator",
	FERTILIZER = "fertilizer",
	WEEDER = "weeder",
	HARVESTER = "harvester",
}

local ATTACHMENT_ORDER = {
	ATTACHMENT_TYPE.PLOW,
	ATTACHMENT_TYPE.SEEDER,
	ATTACHMENT_TYPE.IRRIGATOR,
	ATTACHMENT_TYPE.FERTILIZER,
	ATTACHMENT_TYPE.WEEDER,
	ATTACHMENT_TYPE.HARVESTER,
}

local TAG = {
	TRACTOR = "aom_tractor",
	ATTACHMENT = "aom_attachment",
}

-- 位置采样间隔；只在驶入地块时作业，采样本身不消耗燃料。
local WORK_TICK = 0.1
-- 每次成功的原版作业动作消耗的燃料
local FUEL_PER_TICK = 1
-- 一次推进的世界坐标距离（一个地皮 4 单位）
local WORK_STEP = 4

GLOBAL.AOM_ATTACHMENT_TYPE = ATTACHMENT_TYPE
GLOBAL.AOM_ATTACHMENT_ORDER = ATTACHMENT_ORDER
GLOBAL.AOM_TAG = TAG
GLOBAL.AOM_WORK_TICK = WORK_TICK
GLOBAL.AOM_FUEL_PER_TICK = FUEL_PER_TICK
GLOBAL.AOM_WORK_STEP = WORK_STEP

---------------------------------------------------------------------------
-- 字符串
---------------------------------------------------------------------------

local function MakeStrings(lang)
	if lang == "en" then
		return {
			NAMES = {
				TRACTOR_CHASSIS = "Tractor",
				AOM_LANDCLEARER = "Tractor Land Clearer",
				AOM_SEEDER = "Tractor Seeder",
				AOM_IRRIGATOR = "Tractor Irrigator",
				AOM_FERTILIZER = "Tractor Fertilizer Spreader",
				AOM_WEEDER = "Tractor Weeder",
				AOM_HARVESTER = "Tractor Harvester",
			},
			RECIPE_DESC = {
				TRACTOR_CHASSIS = "Six attachments, six tools. Drive the work.",
				AOM_LANDCLEARER = "Clears debris and prepares a ready-to-sow field.",
				AOM_SEEDER = "Plants seeds into empty farm soil.",
				AOM_IRRIGATOR = "Waters the soil ahead, like a watering can.",
				AOM_FERTILIZER = "Applies fertilizer to the soil ahead.",
				AOM_WEEDER = "Digs up weeds and garden detritus.",
				AOM_HARVESTER = "Harvests ripe crops. Does not smash giant crops.",
			},
			ACTION = {
				DRIVE = "Drive",
				ATTACH = "Attach",
				REFUEL = "Refuel",
				REPAIR = "Repair",
			},
			STATUS = {
				NO_FUEL = "Out of fuel!",
				NO_SEEDS = "No seeds loaded!",
				NO_WATER = "The tank is empty!",
				NO_FERTILIZER = "No fertilizer loaded!",
				BUSY = "Working...",
				MISSING_ATTACHMENT = "No attachment fitted.",
				NOT_DRIVING = "You must be driving the tractor.",
			},
		}
	else
		return {
			NAMES = {
				TRACTOR_CHASSIS = "拖拉机",
				AOM_LANDCLEARER = "拖拉机开垦机",
				AOM_SEEDER = "拖拉机播种机",
				AOM_IRRIGATOR = "拖拉机洒水机",
				AOM_FERTILIZER = "拖拉机施肥挂件",
				AOM_WEEDER = "拖拉机打草挂件",
				AOM_HARVESTER = "拖拉机收割台",
			},
			RECIPE_DESC = {
				TRACTOR_CHASSIS = "六种挂件，六件农具。开车干活。",
				AOM_LANDCLEARER = "一次作业：铺农田、清残渣杂草、整出可直接播种的 3x3 坑位。",
				AOM_SEEDER = "把种子种进前面的空土坑。",
				AOM_IRRIGATOR = "给车前的地补水，和洒水壶一样。",
				AOM_FERTILIZER = "给车前的地施肥，和原版肥料一样。",
				AOM_WEEDER = "铲掉杂草和园艺残渣，和铲子一样。",
				AOM_HARVESTER = "收割成熟作物，不会自动砸开巨大化作物。",
			},
			ACTION = {
				DRIVE = "驾驶",
				ATTACH = "挂载",
				REFUEL = "加油",
				REPAIR = "修理",
			},
			STATUS = {
				NO_FUEL = "没油了！",
				NO_SEEDS = "种袋空了！",
				NO_WATER = "水箱空了！",
				NO_FERTILIZER = "肥料仓空了！",
				BUSY = "作业中……",
				MISSING_ATTACHMENT = "没有安装挂件。",
				NOT_DRIVING = "需要先坐进驾驶舱。",
			},
		}
	end
end

local lang = "zh"
if GetModConfigData ~= nil then
	local v = GetModConfigData("LANGUAGE")
	if type(v) == "string" then
		lang = v
	end
end

local strings = MakeStrings(lang)
-- 旧存档 aom_plow 的展示名兼容新开垦机。
strings.NAMES.AOM_PLOW=strings.NAMES.AOM_LANDCLEARER
GLOBAL.AOM_STRINGS = strings

-- 模块表：常量 + 字符串，供 prefab 与 modmain 统一 require
local M = {
	TYPE = ATTACHMENT_TYPE,
	ORDER = ATTACHMENT_ORDER,
	TAG = TAG,
	WORK_TICK = WORK_TICK,
	WORK_STEP = WORK_STEP,
	FUEL_PER_TICK = FUEL_PER_TICK,
	NAMES = strings.NAMES,
	RECIPE_DESC = strings.RECIPE_DESC,
	ACTION = strings.ACTION,
	STATUS = strings.STATUS,
}

-- 把名字塞进 STRINGS.NAMES 和 STRINGS.RECIPE_DESC（仅在 modmain 环境里 STRINGS 可用时）
if STRINGS ~= nil then
	for k, v in pairs(strings.NAMES) do
		STRINGS.NAMES[k] = v
	end
	for k, v in pairs(strings.RECIPE_DESC) do
		STRINGS.RECIPE_DESC[k] = v
	end
end

return M
