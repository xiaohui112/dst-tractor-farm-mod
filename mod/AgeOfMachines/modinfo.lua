--[[
	拖拉机（Tractor）
	拖拉机挂件式农场机械化 Mod

	设计铁律：拖拉机只做"原版农场工具的自动化"。
	不新增农业机制、不篡改任何农业数值。每个挂件 = 对一格地皮执行一个原版 Action。
]]

local chinese = locale == nil or locale == "zh" or locale == "zhr" or locale == "zht"
name = chinese and "拖拉机" or "Tractor"
description = chinese and [[
	把原版农具装上拖拉机。

	- 开垦机：一次作业铺农田、清残渣杂草、整出可直接播种的 3x3 坑位
	- 播种机：对应种子播种（PLANTSEED）
	- 洒水机：按原版水壶用量按需浇满，出厂空罐
	- 施肥机：按原版肥料用量，按需补齐三类农田养分
	- 除草机：对应铲子（DIG 杂草与残渣）
	- 收割机：对应收获（HARVEST）

	不加速、不改数值、不自动锤巨大化作物。
	产量与原版完全一致，只把重复操作交给机器。
]] or [[
Mount original farming tools on a tractor.

- Land Clearer: lays farm soil, clears debris and prepares a 3x3 planting grid.
- Seeder: plants seeds in empty farm soil.
- Irrigator: starts empty and waters soil as needed using watering-can quantities.
- Fertilizer Spreader: replenishes all three soil nutrients using original fertilizer quantities.
- Weeder: digs up weeds and garden detritus, preserving their original drops.
- Harvester: harvests ripe crops without smashing giant crops.

Original farming rates and yields are preserved; the tractor automates repeated actions.
]]
author = "Tractor Team"
version = "0.1.5"
api_version = 10
priority = 0

dst_compatible = true
dont_starve_compatible = false
reign_of_giants_compatible = false

all_clients_require_mod = true
clients_only_mod = false

server_filter_tags = { "farm", "automation", "tractor" }

icon_atlas = "modicon.xml"
icon = "modicon.tex"

-- 只保留真正生效的选项。未实现的（驾驶速度、燧石修开垦机、普通地皮可翻、
-- 收获进背包、巨大化作物保留、调试日志）已从菜单移除，避免玩家误以为可调而实际无效。
configuration_options =
{
    {
        name = "IRRIGATOR_MUSIC",
        label = chinese and "洒水机音乐《兰花草》" or "Irrigator music: Orchid Grass",
        options = {
            { description = chinese and "开启" or "On", data = true },
            { description = chinese and "关闭" or "Off", data = false },
        },
        default = true,
    },
	{
		name = "LANGUAGE",
		label = "语言 / Language",
		options = {
			{ description = chinese and "跟随游戏" or "Follow game language", data = "auto" },
			{ description = "中文", data = "zh" },
			{ description = "English", data = "en" },
		},
		default = "auto",
	},
}
