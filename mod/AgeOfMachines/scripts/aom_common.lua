--[[
	拖拉机（Tractor） —— 客户端公共定义

	这里只放"客户端也要认识"的东西：
	- 挂件类型常量
	- Action 定义（客户端需要用于提示）
	- 字符串
]]

-- require 模块运行在Lua全局环境；GLOBAL别名通常只存在于Mod入口环境。
local GLOBAL=rawget(_G,"GLOBAL") or _G

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
				AOM_LANDCLEARER = "Land Clearer",
				AOM_SEEDER = "Seeder",
				AOM_IRRIGATOR = "Irrigator",
				AOM_FERTILIZER = "Fertilizer Spreader",
				AOM_WEEDER = "Weeder",
				AOM_HARVESTER = "Harvester",
			},
			RECIPE_DESC = {
				TRACTOR_CHASSIS = "Six attachments, six tools. Drive the work.",
				AOM_LANDCLEARER = "Clears debris and prepares a ready-to-sow field.",
				AOM_SEEDER = "Plants seeds into empty farm soil.",
				AOM_IRRIGATOR = "Waters the soil ahead, like a watering can.",
				AOM_FERTILIZER = "Applies fertilizer to the soil ahead.",
				AOM_WEEDER = "Digs up weeds and garden detritus.",
				AOM_HARVESTER = "Harvests ripe crops and breaks giant produce into its original drops.",
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
				AOM_LANDCLEARER = "开垦机",
				AOM_SEEDER = "播种机",
				AOM_IRRIGATOR = "洒水机",
				AOM_FERTILIZER = "施肥机",
				AOM_WEEDER = "除草机",
				AOM_HARVESTER = "收割机",
			},
			RECIPE_DESC = {
				TRACTOR_CHASSIS = "六种挂件，六件农具。开车干活。",
				AOM_LANDCLEARER = "一次作业：铺农田、清残渣杂草、整出可直接播种的 3x3 坑位。",
				AOM_SEEDER = "把种子种进前面的空土坑。",
				AOM_IRRIGATOR = "给车前的地补水，和洒水壶一样。",
				AOM_FERTILIZER = "给车前的地施肥，和原版肥料一样。",
				AOM_WEEDER = "铲掉杂草和园艺残渣，和铲子一样。",
				AOM_HARVESTER = "收割成熟作物，并按原版掉落锤开巨大作物。",
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

local lang = "auto"
local ReadConfig=rawget(_G,"GetModConfigData")
if ReadConfig ~= nil then
	local v = ReadConfig("LANGUAGE")
	if type(v) == "string" then
		lang = v
	end
end

if lang ~= "zh" and lang ~= "en" then
	local loc = GLOBAL.LOC
	local code = loc ~= nil and loc.GetLocaleCode ~= nil and loc.GetLocaleCode() or nil
	lang = (code == nil or code == "zh" or code == "zhr" or code == "zht") and "zh" or "en"
end

local strings = MakeStrings(lang)
-- 制作配方、世界实体和打包物品都按实际 prefab 名称注册。
strings.NAMES.AOM_TRACTOR_CHASSIS = strings.NAMES.TRACTOR_CHASSIS
strings.NAMES.AOM_TRACTOR_ITEM = strings.NAMES.TRACTOR_CHASSIS
strings.RECIPE_DESC.AOM_TRACTOR_CHASSIS = strings.RECIPE_DESC.TRACTOR_CHASSIS
strings.RECIPE_DESC.AOM_TRACTOR_ITEM = strings.RECIPE_DESC.TRACTOR_CHASSIS
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
	LANGUAGE = lang,
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

-- modmain 中的配置读取器属于 Mod 环境，显式传值，避免 require 模块读不到手动语言设置。
function M.SetLanguage(value)
    if value~="zh" and value~="en" then
        local loc=GLOBAL.LOC
        local code=loc and loc.GetLocaleCode and loc.GetLocaleCode() or nil
        value=(code==nil or code=="zh" or code=="zhr" or code=="zht") and "zh" or "en"
    end
    local s=MakeStrings(value)
    s.NAMES.AOM_TRACTOR_CHASSIS=s.NAMES.TRACTOR_CHASSIS
    s.NAMES.AOM_TRACTOR_ITEM=s.NAMES.TRACTOR_CHASSIS
    s.NAMES.AOM_PLOW=s.NAMES.AOM_LANDCLEARER
    s.RECIPE_DESC.AOM_TRACTOR_CHASSIS=s.RECIPE_DESC.TRACTOR_CHASSIS
    s.RECIPE_DESC.AOM_TRACTOR_ITEM=s.RECIPE_DESC.TRACTOR_CHASSIS
    M.LANGUAGE=value;M.NAMES=s.NAMES;M.RECIPE_DESC=s.RECIPE_DESC;M.ACTION=s.ACTION;M.STATUS=s.STATUS
    GLOBAL.AOM_STRINGS=s
    if STRINGS then
        for k,v in pairs(s.NAMES)do STRINGS.NAMES[k]=v end
        for k,v in pairs(s.RECIPE_DESC)do STRINGS.RECIPE_DESC[k]=v end
    end
end

return M
