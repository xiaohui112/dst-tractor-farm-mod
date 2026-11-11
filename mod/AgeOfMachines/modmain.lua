--[[
	拖拉机（Tractor） —— 装配层

	原则：这里只"接线"，不"发明"。
	所有农业行为最终落在 scripts/aom_farm_work.lua 里对原版函数的调用上。
]]

-- modmain 运行在官方受限环境（scripts/mods.lua 的 CreateEnvironment）里，只暴露
-- pairs/ipairs/print/math/table/type/string/tostring/require/Class/TUNING/GLOBAL 等。
-- 这里显式从 GLOBAL 取常用函数，避免 "attempt to call global 'xxx' (a nil value)"。
local Ingredient = GLOBAL.Ingredient
local TECH = GLOBAL.TECH
local TUNING = GLOBAL.TUNING
local Vector3 = GLOBAL.Vector3
local ActionHandler = GLOBAL.ActionHandler
local pcall = GLOBAL.pcall

PrefabFiles = {
	"aom_tractor_chassis",
	"aom_attachments",
	"aom_exhaust_puff",
}

Assets = {
	Asset("ANIM", "anim/aom_tractor_chassis.zip"),
	Asset("ANIM", "anim/aom_attachment_shared.zip"),
	Asset("ANIM", "anim/aom_attachment_symbols.zip"),
	Asset("ATLAS", "images/aom_chassis_inventory.xml"),
	Asset("IMAGE", "images/aom_chassis_inventory.tex"),
	Asset("ATLAS", "images/aom_attachment_inventory.xml"),
	Asset("IMAGE", "images/aom_attachment_inventory.tex"),
	Asset("ATLAS", "images/aom_tractor_icons.xml"),
	Asset("IMAGE", "images/aom_tractor_icons.tex"),

}

-- 音乐可选接入：模块、资源、播放任一失败都不会进入洒水作业调用链。
local Music
local music_ok,music_module=pcall(require,"aom_irrigator_music")
if music_ok then
    local ok,assets=pcall(music_module.Configure,GetModConfigData("IRRIGATOR_MUSIC")~=false,
        MODROOT,GLOBAL.kleifileexists,Asset)
    if ok then
        Music=music_module
        for _,asset in ipairs(assets) do table.insert(Assets,asset) end
    end
end

-- 模块在游戏主环境执行，读不到本环境的 GetModConfigData（那个函数要求显式传 modname），
-- 所以选项在这里一次性传给模块。
GLOBAL.AOM_CONFIG = {
	LANGUAGE = GetModConfigData("LANGUAGE"),
	MODEL_SCALE = GetModConfigData("MODEL_SCALE"),
}
require("aom_common")

local DriverVisual=require("aom_driver_visual")
if DriverVisual.Configure(MODROOT,GLOBAL.kleifileexists) then
    table.insert(Assets,Asset("ANIM",DriverVisual.ASSET))
end

local AOM_TAG = GLOBAL.AOM_TAG
local AOM_ATTACHMENT_TYPE = GLOBAL.AOM_ATTACHMENT_TYPE

---------------------------------------------------------------------------
-- 1) 自定义动作
---------------------------------------------------------------------------

-- 上下车直接使用原版 ACTIONS.MOUNT / DISMOUNT。
-- rideable / rider 负责提示，SGwilson / SGwilson_client 负责动作与动画。

local AOM_REFUEL = AddAction("AOM_REFUEL", "加油", function(act)
	local target, invobject = act.target, act.invobject
	if target == nil or invobject == nil or target.TryRefuel == nil then
		return false
	end
	if target.prefab ~= "aom_tractor_chassis" then
		return false
	end
	return target:TryRefuel(act.doer, invobject)
end)
AOM_REFUEL.distance = 3
AOM_REFUEL.priority = 1
AOM_REFUEL.mount_valid = false

local AOM_REPAIR = AddAction("AOM_REPAIR", "修理", function(act)
	local target, invobject = act.target, act.invobject
	if target == nil or invobject == nil or target.TryRepair == nil then
		return false
	end
	if target.prefab ~= "aom_tractor_chassis" then
		return false
	end
	return target:TryRepair(act.doer, invobject)
end)
AOM_REPAIR.distance = 3
AOM_REPAIR.priority = 2
AOM_REPAIR.mount_valid = false

local Irrigator = require("aom_irrigator")

local AOM_LOAD = AddAction("AOM_LOAD", "装料", function(act)
	local doer, target, invobject = act.doer, act.target, act.invobject
	if target == nil or invobject == nil then
		return false
	end
	if target.prefab ~= "aom_tractor_chassis" or target.components.aom_attachment_store == nil then
		return false
	end
	local store = target.components.aom_attachment_store
	local att = target._attachment_type
	local msg

	if att == AOM_ATTACHMENT_TYPE.SEEDER and invobject.components.farmplantable ~= nil then
		if store:LoadItem(invobject, doer) then
			msg = "已装种子（共 " .. store:GetSeedCount() .. "）"
			target:PushEvent("aom_load_changed")
			return true
		end
		msg = "种袋已满！"
	elseif att == AOM_ATTACHMENT_TYPE.FERTILIZER and invobject.components.fertilizer ~= nil then
		if store:LoadItem(invobject, doer) then
			msg = "已装肥料（可施用 " .. store:GetFertilizerCount() .. " 次）"
            if doer and doer.components.talker then doer.components.talker:Say(msg) end
            return true
		end
		msg = "肥料仓已满！"
	elseif att == AOM_ATTACHMENT_TYPE.IRRIGATOR then
        local ok
        ok,msg=Irrigator.Load(store,invobject)
        if doer and doer.components.talker then doer.components.talker:Say(msg) end
        return ok
	end

	if doer ~= nil and doer.components.talker ~= nil and msg ~= nil then
		doer.components.talker:Say(msg)
	end
	return false
end)
AOM_LOAD.distance = 3
AOM_LOAD.priority = 2
AOM_LOAD.mount_valid = false

-- 手持挂件右键拖拉机：装进第 1 格（换下来的挂件退回背包）。
local AOM_ATTACH = AddAction("AOM_ATTACH", "装挂件", function(act)
	local target, invobject = act.target, act.invobject
	if target == nil or invobject == nil or target.AttachAttachment == nil then
		return false
	end
	if target.prefab ~= "aom_tractor_chassis" then
		return false
	end
	return target:AttachAttachment(act.doer, invobject)
end)
AOM_ATTACH.distance = 3
AOM_ATTACH.priority = 2
AOM_ATTACH.mount_valid = false

-- 客户端只用 prefab/tag 和已同步挂件判断提示，执行时仍由服务端校验组件和余量。
-- 客户端拿不到容器里的挂件实体（_attachment:value() 恒为 nil），挂件类型改读同步过来的 net_string。
local function GetClientAttachmentType(target)
    local net = target ~= nil and target._atttype_net or nil
    local kind = net ~= nil and net:value() or nil
    return kind ~= "" and kind or nil
end

-- 原版种子没有 farmplantable 标签，客户端只能按 prefab 名判断（与 containers.lua 同规则）。
local function IsSeedItem(item)
    return item.prefab == "seeds"
        or (type(item.prefab) == "string" and string.match(item.prefab, "_seeds") ~= nil)
end

AddComponentAction("USEITEM","inventoryitem",function(item,doer,target,actions,right)
    if not right or target==nil or not target:HasTag(AOM_TAG.TRACTOR) then return end
    local kind=GetClientAttachmentType(target)
    if item.HasTag ~= nil and item:HasTag(AOM_TAG.ATTACHMENT) then
        table.insert(actions,AOM_ATTACH)
    elseif item.prefab=="gears" or item.prefab=="flint" and (kind==AOM_ATTACHMENT_TYPE.PLOW or kind==AOM_ATTACHMENT_TYPE.WEEDER) then
        table.insert(actions,AOM_REPAIR)
    elseif kind==AOM_ATTACHMENT_TYPE.IRRIGATOR and Irrigator.IsSource(item)
        or kind==AOM_ATTACHMENT_TYPE.SEEDER and IsSeedItem(item)
        or kind==AOM_ATTACHMENT_TYPE.FERTILIZER and item:HasTag("fertilizer") then
        table.insert(actions,AOM_LOAD)
    end
end)

---------------------------------------------------------------------------
-- 2) 原版上下坐骑交互
---------------------------------------------------------------------------

-- 上车无需额外注册：原版 rideable 场景动作提供 MOUNT。
-- 下车：无需额外注册。
-- 原版 componentactions.lua 的 "rider" 组件动作已经覆盖所有坐骑：
--   骑乘中右键自己 -> ACTIONS.DISMOUNT（target 必须等于 doer）
-- 拖拉机挂了原版 rideable 组件，rider 的 replica 会同步 mount，
-- 所以只要骑上去，原版的"右键自己下车"就自动生效。
-- （之前误挂在 playercontroller 组件上，既取不到正确的 doer，也会和原版重复。）

---------------------------------------------------------------------------
-- 2.5) 驾驶面板：仅允许当前骑手操作自己的拖拉机
---------------------------------------------------------------------------

local function GetDrivenTractor(player)
	if not GLOBAL.TheWorld.ismastersim or player == nil or not player:IsValid()
		or (player.components.health ~= nil and player.components.health:IsDead())
		or (player.sg ~= nil and player.sg:HasStateTag("busy")) then
		return nil
	end
	local rider = player.components.rider
	local mount = rider ~= nil and rider:IsRiding() and rider:GetMount() or nil
	if mount ~= nil and mount:IsValid() and mount:HasTag(AOM_TAG.TRACTOR)
		and mount.components.rideable:GetRider() == player then
		return mount
	end
end

AddModRPCHandler("aom_rpc", "AOM_TOGGLE_WORK", function(player)
	local tractor = GetDrivenTractor(player)
	if tractor ~= nil then tractor:ToggleWorking(player) end
end)

AddModRPCHandler("aom_rpc", "AOM_SEED_MODE", function(player)
	local tractor = GetDrivenTractor(player)
	if tractor ~= nil then tractor:CycleSeedStrategy(player) end
end)

AddModRPCHandler("aom_rpc", "AOM_DETACH", function(player)
	local tractor = GetDrivenTractor(player)
	if tractor ~= nil and tractor.DetachAttachment ~= nil then
		tractor:DetachAttachment(player)
	end
end)

-- 模块（HUD、按键包装）跑在游戏主环境，拿不到 modmain 的 MOD_RPC；
-- 这里把需要发送的 RPC 句柄挂到主环境，模块只读这一份。
GLOBAL.AOM_RPC = {
	TOGGLE_WORK = GetModRPC("aom_rpc", "AOM_TOGGLE_WORK"),
	SEED_MODE = GetModRPC("aom_rpc", "AOM_SEED_MODE"),
	DETACH = GetModRPC("aom_rpc", "AOM_DETACH"),
}

-- F 只接管拖拉机驾驶员的作业开关；原版骑牛上下车操作保持原样。
local WorkInput=require("aom_work_input")
if not GLOBAL.TheNet:IsDedicated() then WorkInput.Install() end
AddClassPostConstruct("components/playercontroller",WorkInput.WrapController)

---------------------------------------------------------------------------
-- 3) 容器定义：拖拉机 1 格挂件槽
---------------------------------------------------------------------------

-- containers 是模块不是全局：主环境里没有这个名字，strict.lua 会报变量未声明。
local params = require("containers").params

params.aom_tractor_chassis =
{
	widget =
	{
        -- 第1格挂件，后8格物料，容纳图表中的五作物组合。
        slotpos = {
            Vector3(-75,75,0), Vector3(0,75,0), Vector3(75,75,0),
            Vector3(-75,0,0), Vector3(0,0,0), Vector3(75,0,0),
            Vector3(-75,-75,0), Vector3(0,-75,0), Vector3(75,-75,0),
        },
        animbank = "ui_chest_3x3",
        animbuild = "ui_chest_3x3",
		pos = Vector3(0, 200, 0),
		side_align_tip = 160,
	},
	issidewidget = true,
	type = "chest",
	openlimit = 1,
	itemtestfn = function(container, item, slot)
		if item == nil then
			return false
		end
		if slot == 1 then
			-- 挂件槽：只收挂件
			return item:HasTag(AOM_TAG.ATTACHMENT)
		end
        if not GLOBAL.TheWorld.ismastersim then return not item:HasTag(AOM_TAG.ATTACHMENT) end
		-- 物料槽：种子与肥料
		return item.components.farmplantable ~= nil
			or item.components.fertilizer ~= nil
	end,
}

---------------------------------------------------------------------------
-- 4) 配方
---------------------------------------------------------------------------

-- 拖拉机本体是放置物，配方产出的是打包物品（与 farm_plow / farm_plow_item 同构）
local RECIPE_PRODUCT = {
	aom_tractor_chassis = "aom_tractor_item",
}

local function AddMachineRecipe(name, ingredients, tech, filters)
	AddRecipe2(name, ingredients, tech,
		{
			product = RECIPE_PRODUCT[name] or name,
			atlas = "images/aom_tractor_icons.xml",
			image = name .. ".tex",
		},
		filters or { "TOOLS" })
end

-- 底盘：炼金引擎
AddMachineRecipe("aom_tractor_chassis", {
	Ingredient("gears", 4),
	Ingredient("transistor", 3),
	Ingredient("boards", 6),
	Ingredient("flint", 8),
}, TECH.SCIENCE_TWO, { "TOOLS" })

-- 六种挂件：科学机器
AddMachineRecipe("aom_landclearer", {
	Ingredient("flint", 10),
	Ingredient("boards", 2),
}, TECH.SCIENCE_ONE, { "TOOLS" })

AddMachineRecipe("aom_seeder", {
	Ingredient("boards", 4),
	Ingredient("rope", 2),
	Ingredient("cutgrass", 4),
}, TECH.SCIENCE_ONE, { "FARM" })

AddMachineRecipe("aom_irrigator", {
	Ingredient("boards", 3),
	Ingredient("rope", 2),
	Ingredient("waterballoon", 2),
}, TECH.SCIENCE_ONE, { "FARM" })

AddMachineRecipe("aom_fertilizer", {
	Ingredient("boards", 3),
	Ingredient("rope", 2),
	Ingredient("cutgrass", 4),
}, TECH.SCIENCE_ONE, { "FARM" })

AddMachineRecipe("aom_weeder", {
	Ingredient("flint", 4),
	Ingredient("twigs", 6),
	Ingredient("rope", 2),
}, TECH.SCIENCE_ONE, { "FARM" })

AddMachineRecipe("aom_harvester", {
	Ingredient("flint", 8),
	Ingredient("boards", 6),
	Ingredient("rope", 4),
}, TECH.SCIENCE_ONE, { "FARM" })

-- 拆解：把打包物品拆回材料（不可逆，只回收一半）
AddDeconstructRecipe("aom_tractor_item", {
	Ingredient("gears", 2),
	Ingredient("transistor", 1),
	Ingredient("boards", 3),
	Ingredient("flint", 4),
})

---------------------------------------------------------------------------
-- 6) 状态图动作处理（P0：没有这段，动作只会显示提示但不会执行）
---------------------------------------------------------------------------

-- 原版把动作绑定到状态用 StateGraph.ActionHandler，并用 AddStategraphActionHandler 注册。
-- 注意：sg.actionhandlers 的值必须是 ActionHandler 对象（stategraph.lua:285 有 assert），
-- 直接赋 function 会在加载状态图时断言失败。
-- 参考：scripts/stategraphs/SGwilson.lua:1453 ActionHandler(ACTIONS.MOUNT, "doshortaction")

local SHORT_ACTION_ACTIONS = {
	AOM_REFUEL,       -- 加油
	AOM_REPAIR,       -- 修理
	AOM_LOAD,         -- 装料
	AOM_ATTACH,       -- 装挂件
}

-- 原版角色状态图同时负责步行和骑乘。
for _, sgname in ipairs({ "wilson", "wilson_client" }) do
	for _, action in ipairs(SHORT_ACTION_ACTIONS) do
		AddStategraphActionHandler(sgname, ActionHandler(action, "doshortaction"))
	end
end

---------------------------------------------------------------------------
-- 7) 驾驶状态面板（客户端）
---------------------------------------------------------------------------

-- 原版 HUD 通过 AddClassPostConstruct 往 playerhud 上挂子控件；
-- 当前游戏版本的类是 screens/playerhud（旧版本才在 widgets/playerhud）。
-- 注意：PlayerHud 构造时不接收玩家（PlayerHud()），随后 SetMainCharacter(inst) 才写入
-- self.owner，所以控件要挂在 SetMainCharacter 之后，不能在构造后立刻读 self.owner。
AddClassPostConstruct("screens/playerhud", function(self)
	local AOMHud = require("widgets/aom_hud")
	local base_set_main_character = self.SetMainCharacter

	self.SetMainCharacter = function(hud, owner)
		base_set_main_character(hud, owner)
		if owner == nil or hud.aom_hud ~= nil then
			return
		end

		hud.aom_hud = hud:AddChild(AOMHud(owner))
		if Music then
			local ok, controller = pcall(Music.New, owner)
			if ok then hud.aom_music = controller end
		end

		-- 每 0.25 秒刷新一次：读 netvar，开销很低
		hud.aom_hud_task = owner:DoPeriodicTask(0.25, function()
			if hud.aom_music then hud.aom_music:Update() end
			if owner == nil or not owner:IsValid() then
				return
			end
			local rider = owner.replica.rider
			if rider == nil or not rider:IsRiding() then
				hud.aom_hud:Refresh(nil)
				return
			end
			local mount = rider:GetMount()
			hud.aom_hud:Refresh(mount ~= nil and mount.prefab == "aom_tractor_chassis" and mount or nil)
		end)

		hud.inst:ListenForEvent("onremove", function()
			if hud.aom_music then hud.aom_music:Stop() end
			if hud.aom_hud_task ~= nil then
				hud.aom_hud_task:Cancel()
				hud.aom_hud_task = nil
			end
		end, owner)
	end
end)
