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
	"aom_attachment_work_fx",
    "aom_refill_hose",
}

Assets = {
	Asset("SOUNDPACKAGE", "sound/aom_tractor_sfx.fev"),
	Asset("SOUND", "sound/aom_tractor_sfx.fsb"),
	Asset("ANIM", "anim/aom_tractor_chassis.zip"),
	Asset("ANIM", "anim/aom_attachment_shared.zip"),
	Asset("ANIM", "anim/aom_attachment_symbols.zip"),
    Asset("ATLAS","images/aom_water.xml"),
    Asset("IMAGE","images/aom_water.tex"),
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
    local ok,assets=pcall(music_module.Configure,GetModConfigData("IRRIGATOR_MUSIC"),
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
local AOM=require("aom_common")
if AOM.SetLanguage then AOM.SetLanguage(GetModConfigData("LANGUAGE")) end
local L=require("aom_locale").Text

local DriverVisual=require("aom_driver_visual")
if DriverVisual.Configure(MODROOT,GLOBAL.kleifileexists) then
    table.insert(Assets,Asset("ANIM",DriverVisual.SHARED_ASSET))
    table.insert(Assets,Asset("ANIM",DriverVisual.ASSET))
end

local AOM_TAG = GLOBAL.AOM_TAG
local AOM_ATTACHMENT_TYPE = GLOBAL.AOM_ATTACHMENT_TYPE

---------------------------------------------------------------------------
-- 1) 自定义动作
---------------------------------------------------------------------------

-- 上下车直接使用原版 ACTIONS.MOUNT / DISMOUNT。
-- rideable / rider 负责提示，SGwilson / SGwilson_client 负责动作与动画。

local AOM_REFUEL = AddAction("AOM_REFUEL", L("加油"), function(act)
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

local AOM_REPAIR = AddAction("AOM_REPAIR", L("修理"), function(act)
	local target, invobject = act.target, act.invobject
	if target == nil or invobject == nil or (target.TryRepair == nil and not target:HasTag(AOM_TAG.ATTACHMENT)) then
		return false
	end
	if target:HasTag(AOM_TAG.ATTACHMENT) then
        local rider=act.doer and act.doer.components.rider
        if rider and rider:IsRiding() or require("aom_attachment_mount").Owner(target)
            or invobject.prefab~="flint" then return false end
        if act.doer:GetDistanceSqToInst(target)>16 then return false end
        if not require("aom_durability").RepairAttachment(target) then return false end
        local stack=invobject.components.stackable
        if stack and stack:StackSize()>1 then stack:Get(1):Remove() else invobject:Remove() end
        return true
    end
    if target.prefab ~= "aom_tractor_chassis" then return false end
    return target:TryRepair(act.doer, invobject)
end)
AOM_REPAIR.distance = 3
AOM_REPAIR.priority = 2
AOM_REPAIR.mount_valid = false

local Irrigator = require("aom_irrigator")

local AOM_LOAD = AddAction("AOM_LOAD", L("装料"), function(act)
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
			msg = L("已装种子（共 %d）",store:GetSeedCount())
			target:PushEvent("aom_load_changed")
			if doer and doer.components.talker then doer.components.talker:Say(msg) end
			return true
		end
		msg = L("种袋已满！")
	elseif att == AOM_ATTACHMENT_TYPE.FERTILIZER and invobject.components.fertilizer ~= nil then
		if store:LoadItem(invobject, doer) then
			msg = L("已装肥料（可施用 %d 次）",store:GetFertilizerCount())
            if doer and doer.components.talker then doer.components.talker:Say(msg) end
            return true
		end
		msg = L("肥料仓已满！")
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
AOM_LOAD.strfn=function(act)
    local net=act.target and act.target._atttype_net
    return net and net:value()==AOM_ATTACHMENT_TYPE.IRRIGATOR and "REFILL" or "GENERIC"
end
GLOBAL.STRINGS.ACTIONS=GLOBAL.STRINGS.ACTIONS or {}
GLOBAL.STRINGS.ACTIONS.AOM_LOAD={GENERIC=L("装料"),REFILL=L("补水")}

-- 驾驶时右键地面设备挂载，右键已经挂载的设备卸载。
local AOM_ATTACH=AddAction("AOM_ATTACH",L("挂载"),function(act)
    local doer=act.doer
    local rider=doer and doer.components.rider
    local vehicle=rider and rider:IsRiding() and rider:GetMount()
    local target=act.target
    if not vehicle or vehicle.prefab~="aom_tractor_chassis" or vehicle._rider~=doer
        or not target or not target:HasTag(AOM_TAG.ATTACHMENT) then return false end
    local Mount=require("aom_attachment_mount")
    if not Mount.CanReach(doer,target) then return false end
    if Mount.Owner(target)==vehicle then return vehicle:DetachAttachment(doer) end
    if vehicle:GetAttachment() then
        if doer.components.talker then doer.components.talker:Say(L("请先卸载当前配件")) end
        return false
    end
    if require("aom_durability").GetUses(target)<=0 then
        if doer.components.talker then doer.components.talker:Say(L("配件已损坏，请下车用燧石维修后挂载")) end
        return false
    end
    return vehicle:AttachAttachment(doer,target)
end)
AOM_ATTACH.distance=5
AOM_ATTACH.priority=3
AOM_ATTACH.mount_valid=true
AOM_ATTACH.strfn=function(act)
    local owner=act.target and act.target._aom_vehicle and act.target._aom_vehicle:value()
    return owner and "DETACH" or "GENERIC"
end
GLOBAL.STRINGS.ACTIONS.AOM_ATTACH={GENERIC=L("挂载"),DETACH=L("卸载")}
AddComponentAction("SCENE","inspectable",function(item,doer,actions,right)
    if not right or not item:HasTag(AOM_TAG.ATTACHMENT) then return end
    local rider=doer.replica and doer.replica.rider
    local vehicle=rider and rider:IsRiding() and rider:GetMount()
    if not vehicle or not vehicle:HasTag(AOM_TAG.TRACTOR) then return end
    local owner=item._aom_vehicle and item._aom_vehicle:value()
    if not owner or owner==vehicle then table.insert(actions,AOM_ATTACH) end
end)

-- 客户端只用 prefab/tag 和已同步挂件判断提示，执行时仍由服务端校验组件和余量。
-- 客户端拿不到容器里的挂件实体（_attachment:value() 恒为 nil），挂件类型改读同步过来的 net_string。
local function GetClientAttachmentType(target)
    local net = target ~= nil and target._atttype_net or nil
    local kind = net ~= nil and net:value() or nil
    return kind ~= "" and kind or nil
end

local AOM_POND_REFILL=AddAction("AOM_POND_REFILL",L("补满水箱"),function(act)
    local ok,msg=Irrigator.RefillFromPond(act.doer,act.target)
    if msg and act.doer and act.doer.components.talker then act.doer.components.talker:Say(msg) end
    return ok
end)
AOM_POND_REFILL.distance=Irrigator.POND_DISTANCE
AOM_POND_REFILL.priority=3
AOM_POND_REFILL.mount_valid=true

-- 右键池塘，客户端只读同步挂件及水量；不需要拿着水壶或下车。
AddComponentAction("SCENE","watersource",function(pond,doer,actions,right)
    if not right or not pond:HasTag("pond") or not pond:HasTag("watersource") then return end
    local rider=doer.replica and doer.replica.rider
    local vehicle=rider and rider:GetMount()
    if vehicle and vehicle:HasTag(AOM_TAG.TRACTOR)
        and GetClientAttachmentType(vehicle)==AOM_ATTACHMENT_TYPE.IRRIGATOR
        and vehicle._water_net and vehicle._watermax_net
        and not (vehicle._refilling_net and vehicle._refilling_net:value())
        and vehicle._water_net:value()<vehicle._watermax_net:value() then
        table.insert(actions,AOM_POND_REFILL)
    end
end)

-- 原版种子没有 farmplantable 标签，客户端只能按 prefab 名判断（与 containers.lua 同规则）。
local function IsSeedItem(item)
    return item.prefab == "seeds"
        or (type(item.prefab) == "string" and string.match(item.prefab, "_seeds") ~= nil)
end

AddComponentAction("USEITEM","inventoryitem",function(item,doer,target,actions,right)
    if not right or target==nil then return end
    if target:HasTag(AOM_TAG.ATTACHMENT) then
        if item.prefab=="flint" and not (target._aom_vehicle and target._aom_vehicle:value()) then
            table.insert(actions,AOM_REPAIR)
        end
        return
    end
    if not target:HasTag(AOM_TAG.TRACTOR) then return end
    local kind=GetClientAttachmentType(target)
    if item.HasTag ~= nil and item:HasTag(AOM_TAG.ATTACHMENT) then
        table.insert(actions,AOM_ATTACH)
    elseif item.prefab=="gears" then
        table.insert(actions,AOM_REPAIR)
    elseif kind==AOM_ATTACHMENT_TYPE.IRRIGATOR and Irrigator.IsSource(item)
        or kind==AOM_ATTACHMENT_TYPE.SEEDER and IsSeedItem(item)
        or kind==AOM_ATTACHMENT_TYPE.FERTILIZER and item:HasTag("fertilizer") then
        table.insert(actions,AOM_LOAD)
    elseif item:HasTag("BURNABLE_fuel") then
        table.insert(actions,AOM_REFUEL)
    end
end)

---------------------------------------------------------------------------
-- 2) 原版上下坐骑交互
---------------------------------------------------------------------------

-- 上车无需额外注册：原版 rideable 场景动作提供 MOUNT。
-- 下车继续使用原版 DISMOUNT；下方鼠标入口避免开仓时被 RUMMAGE 抢占。

---------------------------------------------------------------------------
-- 2.5) 驾驶面板：仅允许当前骑手操作自己的拖拉机
---------------------------------------------------------------------------

local function GetDrivenTractor(player,allow_busy)
	if not GLOBAL.TheWorld.ismastersim or player == nil or not player:IsValid()
		or player:HasTag("playerghost")
		or (player.components.health ~= nil and player.components.health:IsDead())
		or (not allow_busy and player.sg ~= nil and player.sg:HasStateTag("busy")) then
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

local function PlanAction(player,rotate)
    local tractor=GetDrivenTractor(player)
    if not tractor or tractor._attachment_type~="seeder" or tractor._seed_strategy~="GIANT" then return end
    tractor:SetWorking(false)
    local block=require("aom_block_plan")
    local ok,reason
    if not rotate and tractor._block and tractor._block.confirmed==false then ok,reason=block.Confirm(tractor)
    else ok,reason=block.Preview(tractor,rotate) end
    block.Sync(tractor)
    if ok then require("aom_work_status").Set(tractor,tractor._block.confirmed==false and "PLAN_PENDING" or nil)
    else require("aom_drive").StopForReason(tractor,reason) end
end
AddModRPCHandler("aom_rpc","AOM_PLAN",function(player)PlanAction(player,false)end)
AddModRPCHandler("aom_rpc","AOM_PLAN_ROTATE",function(player)PlanAction(player,true)end)

AddModRPCHandler("aom_rpc", "AOM_DETACH", function(player,target)
	local tractor = GetDrivenTractor(player)
	if tractor==nil and player and player:IsValid() and target and target:IsValid()
        and target.prefab=="aom_tractor_chassis" and target.components.container
        and target.components.container:IsOpenedBy(player)
        and target.components.rideable:GetRider()==nil
        and player:GetDistanceSqToInst(target)<=16 then tractor=target end
	if tractor ~= nil and tractor.DetachAttachment ~= nil then
		tractor:DetachAttachment(player)
	end
end)

local function CloseTractorStorage(player,tractor)
    if player and player:IsValid() and tractor and tractor:IsValid()
        and tractor.prefab=="aom_tractor_chassis" and tractor.components.container
        and tractor.components.container:IsOpenedBy(player) then
        tractor.components.container:Close(player)
        player:PushEvent("closecontainer",{container=tractor})
    end
end

local function ToggleTractorStorage(player)
    local tractor=GetDrivenTractor(player,true)
    if not tractor then return false end
    local container=tractor.components.container
    if container:IsOpenedBy(player) then CloseTractorStorage(player,tractor)
    elseif container:CanOpen() then container:Open(player)
    else return false end
    return true
end

local AOM_STORAGE=AddAction("AOM_STORAGE",L("打开仓库"),function(act)
    return act.target==act.doer and ToggleTractorStorage(act.doer)
end)
AOM_STORAGE.instant=true
AOM_STORAGE.mount_valid=true
AOM_STORAGE.priority=3
AOM_STORAGE.strfn=function(act)
    local rider=act.doer and act.doer.replica and act.doer.replica.rider
    local vehicle=rider and rider:GetMount()
    local container=vehicle and vehicle.replica.container
    return container and container:IsOpenedBy(act.doer) and "CLOSE" or "GENERIC"
end
GLOBAL.STRINGS.ACTIONS.AOM_STORAGE={GENERIC=L("打开仓库"),CLOSE=L("关闭仓库")}
local MouseInput=require("aom_mouse_input")
AddClassPostConstruct("components/playeractionpicker",function(self)MouseInput.WrapPicker(self,AOM_STORAGE)end)

-- 图标与左键车身共用同一个仓库入口，不增加另一套仓库。
AddModRPCHandler("aom_rpc", "AOM_STORAGE", ToggleTractorStorage)

AddModRPCHandler("aom_rpc", "AOM_CLOSE_STORAGE", function(player,target)
    CloseTractorStorage(player,target or GetDrivenTractor(player,true))
end)

AddModRPCHandler("aom_rpc", "AOM_DISMOUNT", function(player)
    local tractor=GetDrivenTractor(player,true)
    if tractor then
        CloseTractorStorage(player,tractor)
        require("aom_drive").Dismount(tractor,player)
    end
end)

-- 模块（HUD、按键包装）跑在游戏主环境，拿不到 modmain 的 MOD_RPC；
-- 这里把需要发送的 RPC 句柄挂到主环境，模块只读这一份。
GLOBAL.AOM_RPC = {
    PLAN=GetModRPC("aom_rpc","AOM_PLAN"),
    PLAN_ROTATE=GetModRPC("aom_rpc","AOM_PLAN_ROTATE"),
	TOGGLE_WORK = GetModRPC("aom_rpc", "AOM_TOGGLE_WORK"),
	SEED_MODE = GetModRPC("aom_rpc", "AOM_SEED_MODE"),
	DETACH = GetModRPC("aom_rpc", "AOM_DETACH"),
	STORAGE = GetModRPC("aom_rpc", "AOM_STORAGE"),
	CLOSE_STORAGE = GetModRPC("aom_rpc", "AOM_CLOSE_STORAGE"),
	DISMOUNT = GetModRPC("aom_rpc", "AOM_DISMOUNT"),
}

-- F 只接管拖拉机驾驶员的作业开关；原版骑牛上下车操作保持原样。
local WorkInput=require("aom_work_input")
if not GLOBAL.TheNet:IsDedicated() then WorkInput.Install() end
AddClassPostConstruct("components/playercontroller",WorkInput.WrapController)
AddStategraphPostInit("wilson",require("aom_vehicle_motion").ConfigureMountSounds)
AddClassPostConstruct("widgets/hoverer",require("aom_machine_info").Install)

---------------------------------------------------------------------------
-- 3) 容器定义：拖拉机独立挂点与九格货物/物料仓
---------------------------------------------------------------------------

-- containers 是模块不是全局：主环境里没有这个名字，strict.lua 会报变量未声明。
local params = require("containers").params

params.aom_tractor_chassis={
    widget={
        slotpos={Vector3(-75,75,0),Vector3(0,75,0),Vector3(75,75,0),
                 Vector3(-75,0,0),Vector3(0,0,0),Vector3(75,0,0),
                 Vector3(-75,-75,0),Vector3(0,-75,0),Vector3(75,-75,0)},
        animbank="ui_chest_3x3",animbuild="ui_chest_3x3",pos=Vector3(-260,120,0),side_align_tip=160,
    },
    issidewidget=false,type="chest",openlimit=1,
    itemtestfn=function(container,item,slot)
        if not item or item:HasTag(AOM_TAG.ATTACHMENT) or item:HasTag(AOM_TAG.TRACTOR) then return false end
        return not GLOBAL.TheWorld.ismastersim or item.components.inventoryitem~=nil
    end,
}
local containers=require("containers")
containers.MAXITEMSLOTS=math.max(containers.MAXITEMSLOTS or 0,9)
AddClassPostConstruct("widgets/containerwidget",function(self)
    local open=self.Open
    self.Open=function(widget,container,doer)
        open(widget,container,doer)
        if container and container.prefab=="aom_tractor_chassis" then
            if not widget.aom_storage_title then
                local Text=require("widgets/text")
                widget.aom_storage_title=widget:AddChild(Text(GLOBAL.NUMBERFONT,24,""))
                widget.aom_storage_title:SetPosition(0,225,0)
                widget.aom_storage_hint=widget:AddChild(Text(GLOBAL.NUMBERFONT,18,""))
                widget.aom_storage_hint:SetPosition(0,198,0)
            end
            widget.aom_storage_title:SetString(L("货物与物料"))
            widget.aom_storage_hint:SetString(L("9格货仓；配件使用独立挂点"))
            widget.aom_storage_title:Show();widget.aom_storage_hint:Show()
        elseif widget.aom_storage_title then
            widget.aom_storage_title:Hide();widget.aom_storage_hint:Hide()
        end
    end
end)
local RECIPE_PRODUCT={aom_tractor_chassis="aom_tractor_chassis"}
local function AddMachineRecipe(name,ingredients,tech)
    AddRecipe2(name,ingredients,tech,{product=RECIPE_PRODUCT[name] or name,placer=name.."_placer",min_spacing=2,
        atlas="images/aom_tractor_icons.xml",image=name..".tex"},{"GARDENING"})
end

AddMachineRecipe("aom_tractor_chassis", {
	Ingredient("gears", 4),
	Ingredient("transistor", 3),
	Ingredient("boards", 6),
	Ingredient("flint", 8),
}, TECH.SCIENCE_TWO)

-- 六种挂件：首次解锁均需炼金引擎
AddMachineRecipe("aom_landclearer", {
    Ingredient("boards", 6), Ingredient("rope", 4),
    Ingredient("flint", 16), Ingredient("cutstone", 4),
}, TECH.SCIENCE_TWO)

AddMachineRecipe("aom_seeder", {
    Ingredient("boards", 6), Ingredient("rope", 4),
    Ingredient("seeds", 20), Ingredient("gears", 1),
}, TECH.SCIENCE_TWO)

AddMachineRecipe("aom_irrigator", {
    Ingredient("boards", 6), Ingredient("rope", 4),
    Ingredient("waterballoon", 6), Ingredient("ice", 12),
}, TECH.SCIENCE_TWO)

AddMachineRecipe("aom_fertilizer", {
    Ingredient("boards", 6), Ingredient("rope", 4),
    Ingredient("fertilizer", 1, nil, true), Ingredient("compost", 6),
}, TECH.SCIENCE_TWO)

AddMachineRecipe("aom_weeder", {
    Ingredient("boards", 4), Ingredient("rope", 4),
    Ingredient("twigs", 16), Ingredient("flint", 12),
}, TECH.SCIENCE_TWO)

AddMachineRecipe("aom_harvester", {
    Ingredient("boards", 8), Ingredient("rope", 4),
    Ingredient("flint", 16), Ingredient("gears", 2),
}, TECH.SCIENCE_TWO)

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
	AOM_POND_REFILL,  -- 骑乘时在池塘边补满洒水机
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

		-- 使用原版物品栏的缩放根节点，避免窗口尺寸/HUD 缩放让按钮移出屏幕。
		hud.aom_hud = hud.controls.bottom_root:AddChild(AOMHud(owner))
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
            require("aom_plan_preview").Clear(hud.aom_hud)
			if hud.aom_music then hud.aom_music:Stop() end
			if hud.aom_hud_task ~= nil then
				hud.aom_hud_task:Cancel()
				hud.aom_hud_task = nil
			end
		end, owner)
	end
end)
