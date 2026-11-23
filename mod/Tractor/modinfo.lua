--[[
	拖拉机（Tractor）
	拖拉机挂件式农场机械化 Mod

	设计铁律：拖拉机只做"原版农场工具的自动化"。
	不新增农业机制、不篡改任何农业数值。每个挂件 = 对一格地皮执行一个原版 Action。
]]

local chinese = locale == nil or locale == "zh" or locale == "zhr" or locale == "zht"
name = "Tractor"
description = chinese and [[
	0.5.28 更新

	【新增】
	- 田边蓄水桶用木板、绳子和石砖各 2 份制作，容量 2,000 剂，下雨每秒蓄 10 剂，洒水机每秒取 80 剂，仅支持取水。
	- 洒水机可在近岸每秒过滤 40 剂海水，每过滤 20 剂消耗 1 点挂件耐久。
	- 自动拾取依次存入车仓、驾驶员物品栏和已装备背包，余量留在地上。
	- 施肥机按同一顺序取用合适的肥料，播种机只从车仓取种，不想种的种子可以留在物品栏或背包里。
	- 空手左键收割机图标可切换「全部收割」和「保留巨大」，保留模式会把完整巨大作物留在田里。

	【配方优化】
	- 拖拉机现需木板 ×3、燧石 ×4、齿轮 ×2、电子元件 ×2。
	- 开垦机和除草机各需木板 ×2、燧石 ×2、绳子 ×2。
	- 播种机现需木板 ×2、绳子 ×2、普通种子 ×5。
	- 洒水机现需木板 ×2、绳子 ×2、水球 ×3。
	- 施肥机现需木板 ×2、绳子 ×2、肥料桶 ×2。
	- 收割机现需木板 ×2、燧石 ×2、齿轮 ×1。

	【作业与操作优化】
	- 六种挂件耐久从 100 提高到 200，旧挂件按比例迁移，燧石每份维修量从 10 提高到 50 点。
	- 齿轮每份修复 200 点车体生命，木板每份修复 250 点底盘耐久。
	- 锤拆拖拉机和车载挂件时，按新配方逐项减半、向下取整返还材料。
	- 默认空驶速度提高到 6、作业速度为 3 世界单位/秒，新车有 600 油，行驶每 8 世界单位耗 1 油。
	- 播种每格只扣 1 油和 1 底盘耐久，种完该格再扣 1 点播种机耐久。
	- 洒水机出厂有 100 剂水，水箱容量 400 剂，池塘每秒补 80 剂，取消水壶和冰块应急补水。
	- 六种挂件按驾驶员当前所在的地皮作业，巨大化规划起点和落种也按驾驶员所在格判断。
	- 驾驶时可放置六种挂件和田边蓄水桶，蓄水桶与洒水机接近等高，悬停显示名称和余水。
	- 「保留巨大」模式下，车辆经过完整巨大作物时暂时解除其人物碰撞，驶离后恢复。
	- 播种机和收割机图标显示当前模式，悬停看下一档，空手左键切换。
	- 侧面和斜向的旋转线条对准轮毂，正背向隐藏轮纹，烟雾从驾驶员右前方的烟筒口冒出。
	- 驾驶时屏蔽骑乘脚步声，空驶播放薇诺娜发电机的运转声，移动作业播放「驾驶室轰鸣」。
	
	0.5.24 发布版本
	拖拉机有七种配套设备，包括六种车载挂件和一座田边蓄水桶。

	- 开垦机：一次作业铺农田、清残渣杂草、整出可直接播种的 3x3 坑位
	- 播种机：对应种子播种（PLANTSEED）
	- 洒水机：按需浇水，出厂100剂，可从蓄水桶、池塘或近岸海面补水
	- 施肥机：按需补齐三类养分，可从车仓、物品栏或背包取肥
	- 除草机：DIG 杂草、残渣及无法采收的腐烂枯株
	- 收割机：采摘成熟或腐烂作物，可切换拆分或整颗保留巨大作物
	- 田边蓄水桶：固定建在地面，容量2000剂，下雨每秒蓄10剂，洒水机每秒取80剂

	不加速、不改农业数值。
	产量与原版完全一致，只把重复操作交给机器。


]] or [[
0.5.28 Update

New
- The Field Rain Barrel costs 2 Boards, 2 Rope, and 2 Cut Stone, holds 2,000 doses, and collects 10 doses of rainwater per second for the Irrigator to draw at 80 per second.
- The Irrigator filters 40 doses of coastal seawater per second, using 1 durability per 20 doses.
- Automatic pickup fills tractor cargo, the driver's inventory, and the equipped backpack in that order, leaving overflow on the ground.
- The Fertilizer Spreader looks for suitable fertilizer in the same order, while the Seeder takes seeds from tractor cargo.
- Left-click the Harvester icon with an empty cursor to toggle Harvest All or Keep Giants Whole, which leaves intact giants in the field.

Improved recipes
- The Tractor now costs 3 Boards, 4 Flint, 2 Gears, and 2 Electrical Doodads.
- The Land Clearer and Weeder each cost 2 Boards, 2 Flint, and 2 Rope.
- The Seeder now costs 2 Boards, 2 Rope, and 5 Seeds.
- The Irrigator now costs 2 Boards, 2 Rope, and 3 Water Balloons.
- The Fertilizer Spreader now costs 2 Boards, 2 Rope, and 2 Buckets-o-poop.
- The Harvester now costs 2 Boards, 2 Flint, and 1 Gear.

Work and control improvements
- Durability rises from 100 to 200 for all six attachments, existing tools keep their durability percentage, and Flint repairs 50 points instead of 10.
- Each Gear restores 200 vehicle health and each Board restores 250 chassis durability.
- Hammering the Tractor or an attachment refunds half of each new recipe ingredient, rounded down.
- Default travel and work speeds are 6 and 3 units per second, with 600 starting fuel and 1 fuel spent per 8 units traveled.
- Sowing costs 1 fuel and 1 chassis durability per tile, with 1 Seeder durability charged on completion.
- The Irrigator starts with 100 of 400 doses, refills from ponds at 80 doses per second, and no longer refills from watering cans or ice.
- All six attachments work on the tile under the driver. This also determines where giant crop planning starts and where sowing takes place.
- Place any of the six attachments or the Field Rain Barrel while driving. The barrel is about as tall as the Irrigator and shows its name and water level on hover.
- In Keep Giants Whole mode, nearby intact giant produce temporarily lets the driver pass and regains collision when the tractor moves away.
- Seeder and Harvester icons show the current mode and preview the next one on hover, with empty-cursor left click to switch.
- Wheel lines follow the hubs in side and diagonal views and are hidden from straight front and rear views. Exhaust comes from the driver's front-right pipe.
- Driving mutes riding footsteps, uses Winona's Generator loop for travel, and plays the cab engine sound during moving work.

0.5.24 release
Seven pieces of farm equipment: six tractor attachments and a stationary Field Rain Barrel.

- Land Clearer: lays farm soil, clears debris and prepares a 3x3 planting grid.
- Seeder: plants seeds in empty farm soil.
- Irrigator: starts with 100 doses, waters soil as needed, and refills at rain barrels, ponds, or the coast.
- Fertilizer Spreader: replenishes soil nutrients using fertilizer from cargo, pockets, or the equipped backpack.
- Weeder: digs up weeds, detritus and unharvestable rotten or dead crop remains.
- Harvester: harvests ripe or rotten crops, with modes to break or keep giant produce whole.
- Field Rain Barrel: holds 2,000 doses, collects 10 doses per second in the rain, and supplies an irrigator at 80 doses per second.

Original farming rates and yields are preserved; the tractor automates repeated actions.
]]
author = "Tractor Team"
version = "0.5.28"
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
            { description = chinese and "64毫秒" or "64 ms", data = 64 },
            { description = chinese and "96毫秒" or "96 ms", data = 96 },
            { description = chinese and "128毫秒" or "128 ms", data = 128 },
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
