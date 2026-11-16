--[[
	拖拉机（Tractor）
	拖拉机挂件式农场机械化 Mod

	设计铁律：拖拉机只做"原版农场工具的自动化"。
	不新增农业机制、不篡改任何农业数值。每个挂件 = 对一格地皮执行一个原版 Action。
]]

local chinese = locale == nil or locale == "zh" or locale == "zhr" or locale == "zht"
name = "Tractor"
description = chinese and [[
	把原版农具装上拖拉机。

	- 开垦机：一次作业铺农田、清残渣杂草、整出可直接播种的 3x3 坑位
	- 播种机：对应种子播种（PLANTSEED）
	- 洒水机：按原版水壶用量按需浇满，出厂空罐
	- 施肥机：按原版肥料用量，按需补齐三类农田养分
	- 除草机：DIG 杂草、残渣及无法采收的腐烂枯株
	- 收割机：采摘成熟或腐烂作物，并按原版锤击掉落拆开巨大作物

	不加速、不改农业数值。
	产量与原版完全一致，只把重复操作交给机器。
]] or [[
Mount original farming tools on a tractor.

- Land Clearer: lays farm soil, clears debris and prepares a 3x3 planting grid.
- Seeder: plants seeds in empty farm soil.
- Irrigator: starts empty and waters soil as needed using watering-can quantities.
- Fertilizer Spreader: replenishes all three soil nutrients using original fertilizer quantities.
- Weeder: digs up weeds, detritus and unharvestable rotten or dead crop remains.
- Harvester: harvests ripe or rotten crops and breaks giant produce using original hammering drops.

Original farming rates and yields are preserved; the tractor automates repeated actions.
]]
author = "Tractor Team"
version = "0.5.24"
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
        name = "PLAN_CPU_BUDGET_MS",
        label = chinese and "巨大化规划每帧额度" or "Giant planning budget per tick",
        hover = chinese and "前台最优/模版规划的计算软额度。越大通常等待越短，但更容易卡顿；后台预计算固定1毫秒。由房主/服务器设置，重新载入世界后生效。"
            or "Soft CPU budget for foreground optimal/template planning. Larger values usually shorten waits but may cause stutter. Background stays at 1 ms. Host/server setting; reload the world to apply.",
        options = {
            { description = chinese and "2毫秒" or "2 ms", data = 2 },
            { description = chinese and "4毫秒" or "4 ms", data = 4 },
            { description = chinese and "8毫秒" or "8 ms", data = 8 },
            { description = chinese and "12毫秒" or "12 ms", data = 12 },
            { description = chinese and "16毫秒（默认）" or "16 ms (default)", data = 16 },
            { description = chinese and "24毫秒" or "24 ms", data = 24 },
            { description = chinese and "32毫秒" or "32 ms", data = 32 },
        },
        default = 16,
    },
    {
        name = "IRRIGATOR_MUSIC",
        label = chinese and "洒水机音乐《兰花草》" or "Irrigator music: Orchid Grass",
        options = {
            { description = chinese and "开启（播放并安抚）" or "On (audio and tending)", data = "on" },
            { description = chinese and "关闭（无音乐、无安抚）" or "Off (no audio or tending)", data = "off" },
            { description = chinese and "静音（仅安抚植物）" or "Muted (tending only)", data = "mute" },
        },
        default = "on",
    },
	{
		name = "MODEL_SCALE",
		label = chinese and "模型大小（拖拉机与挂件）" or "Model scale (tractor and attachments)",
		options = {
			{ description = "75%", data = "0.75" },
			{ description = chinese and "成年牛体量（标准）" or "Adult beefalo size", data = "1" },
			{ description = "125%", data = "1.25" },
			{ description = "150%", data = "1.5" },
		},
		default = "1",
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
