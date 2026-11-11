--[[
	Age of Machines —— 拖拉机底盘

	形态：可骑乘的机械。上下车沿用原版骑牛的 MOUNT / DISMOUNT，
	方向键驾驶，F 开关作业，驶过地块完成工序，作业类型决定速度。
]]

local AOMFarmWork = require("aom_farm_work")
local AOM = require("aom_common")
local AOMDrive = require("aom_drive")
local AOMBlock = require("aom_block_plan")
local Profile = require("aom_work_profile")
local LandClearer = require("aom_landclearer_tool")
local Irrigator = require("aom_irrigator")
local DriverVisual = require("aom_driver_visual")
local Fertilizer = require("aom_fertilizer")

local assets =
{
	Asset("ANIM", "anim/aom_tractor_chassis.zip"),
	Asset("ANIM", "anim/aom_attachment_symbols.zip"),
	Asset("ATLAS", "images/aom_tractor_icons.xml"),
	Asset("IMAGE", "images/aom_tractor_icons.tex"),
	Asset("ATLAS", "images/aom_chassis_inventory.xml"),
	Asset("IMAGE", "images/aom_chassis_inventory.tex"),
}

-- 与农场耕地机同构：aom_tractor_chassis 是放在世界里的本体，
-- aom_tractor_item 是可放进背包、可放置的打包物品（配方产出）。

local prefabs =
{
	"farm_soil",
	"farm_soil_debris",
	"aom_landclearer",
	"aom_seeder",
	"aom_irrigator",
	"aom_fertilizer",
	"aom_weeder",
	"aom_harvester",
	"aom_exhaust_puff",
}

-- 燃料：木炭
local FUEL_PREFAB = "charcoal"
local MAX_FUEL = 800
local FUEL_PER_TICK = 1
local MAX_HEALTH = 600
local MAX_USES = 1000
local STARTING_FUEL = 400

---------------------------------------------------------------------------
-- 燃料
---------------------------------------------------------------------------

local function GetFuel(inst)
	return inst._fuel ~= nil and inst._fuel:value() or 0
end

local function SetFuel(inst, v)
	AOMDrive.SetFuel(inst, math.clamp(v, 0, MAX_FUEL))
end

---------------------------------------------------------------------------
-- 工具
---------------------------------------------------------------------------

local function GetConfigNumber(key, default)
	local v = GetModConfigData(key)
	if type(v) == "number" then
		return v
	end
	return default
end

---------------------------------------------------------------------------
-- 挂件变化
---------------------------------------------------------------------------

local function OnAttachmentChanged(inst)
	local previous=inst._watched_attachment
	local item = inst.components.container:GetItemInSlot(1)
	if item ~= nil and item.attachment_type ~= nil then
		inst._attachment_type = item.attachment_type
		inst._attachment:set(item)
	else
		inst._attachment_type = nil
		inst._attachment:set(nil)
		-- 没有挂件就不能继续作业
		AOMDrive.SetWorking(inst, false)
	end
	if previous~=item then
        if previous then inst:RemoveEventCallback("percentusedchange",Irrigator.Sync,previous) end
        inst._watched_attachment=item
        if item then inst:ListenForEvent("percentusedchange",Irrigator.Sync,item) end
        AOMDrive.SetWorking(inst,false)
    end
    Irrigator.Sync(inst)
    DriverVisual.UpdateAttachment(inst,inst._aom_driver_animstate)
    Fertilizer.Watch(inst)
	-- 收割台用车头时间轴，其余配件沿用车尾；前层在车身前面绘制。
	if inst._attachment_type==AOM.TYPE.HARVESTER then
		inst.AnimState:OverrideSymbol("attachment", "aom_attachment_symbols", "empty")
		inst.AnimState:OverrideSymbol("attachment_front", "aom_attachment_symbols", "harvester")
		inst.AnimState:ShowSymbol("attachment_front")
	else
		inst.AnimState:OverrideSymbol("attachment", "aom_attachment_symbols", inst._attachment_type or "empty")
		inst.AnimState:HideSymbol("attachment_front")
	end
	if inst._fuel_hudtask == nil then
		inst._fuel_hudtask = inst:DoPeriodicTask(2, function()
			inst:PushEvent("aom_refuel_changed", { fuel = AOMDrive.GetFuel(inst) })
		end)
	end
end


---------------------------------------------------------------------------
-- 燃料 / 修理
---------------------------------------------------------------------------

local function ConsumeOne(item)
	-- 从堆叠里只消耗一份；非堆叠则整件移除。
	-- 不能直接 item:Remove()，那会把整个堆叠删掉。
	if item == nil or not item:IsValid() then
		return
	end
	local stackable = item.components.stackable
	if stackable ~= nil and stackable:StackSize() > 1 then
		stackable:Get(1):Remove()
	else
		item:Remove()
	end
end

local function TryRefuel(inst, doer, item)
	-- 支持原版燃料（wood / charcoal 等 burnable）
	if item == nil or item.components.fuel == nil then
		return false
	end
	local room = MAX_FUEL - GetFuel(inst)
	if room <= 0 then
		return false
	end
	local v = item.components.fuel.fuelvalue
	-- 只按油箱实际能吸收的量结算：满了就不再消耗燃料
	local used = math.min(room, v)
	SetFuel(inst, GetFuel(inst) + used)
	if used >= v then
		ConsumeOne(item)
	end
	return true
end

local function TryRepair(inst, doer, item)
	-- 开垦机保留耗尽物品；1份燧石恢复10次，满耐久不扣材料。
	if item~=nil and item.prefab=="flint" then
		if not LandClearer.Repair(inst) then return false end
		ConsumeOne(item)
		inst.SoundEmitter:PlaySound("dontstarve/HUD/click_move")
		return true
	end
	-- 齿轮修复：1 个齿轮 +100 耐久（只消耗一份齿轮）
	if item == nil or item.prefab ~= "gears" then
		return false
	end
	local uses = inst.components.finiteuses:GetUses()
	if uses >= MAX_USES then
		return false
	end
	inst.components.finiteuses:SetUses(math.min(MAX_USES, uses + 100))
	ConsumeOne(item)
	inst.SoundEmitter:PlaySound("dontstarve/HUD/click_move")
	return true
end

---------------------------------------------------------------------------
-- 生命周期
---------------------------------------------------------------------------

local function OnSave(inst, data)
	if data == nil then return end
	data.fuel = GetFuel(inst)
	data.attachment_type = inst._attachment_type
	data.seed_strategy = inst._seed_strategy
	data.block = AOMBlock.OnSave(inst)
end

local function OnLoad(inst, data)
	if data == nil then return end
	if data.fuel ~= nil then
		SetFuel(inst, data.fuel)
	end
	if data.attachment_type ~= nil then
		inst._attachment_type = data.attachment_type
	end
	if data.seed_strategy ~= nil then
		inst._seed_strategy = data.seed_strategy
        inst._seedmode_net:set(inst._seed_strategy)
	end
	if data.block ~= nil then
		AOMBlock.OnLoad(inst, data.block)
        inst._planprogress_net:set(AOMBlock.DescribeProgress(inst))
	end
end

local function OnLoadPostPass(inst)
	OnAttachmentChanged(inst)
end

local function OnHealthDead(inst)
	if inst._rider ~= nil and inst._rider.components.rider ~= nil then
		AOMDrive.Dismount(inst, inst._rider)
	end
	AOMDrive.SetWorking(inst, false)
	inst.AnimState:PlayAnimation("death")
	inst.components.workable:SetWorkLeft(-1)  -- 死人不可拆
end

---------------------------------------------------------------------------
-- 放置 / 打包
---------------------------------------------------------------------------

local function can_place_tractor(inst, pt, mouseover, deployer)
	if not TheWorld.Map:CanPlantAtPoint(pt.x, 0, pt.z) then
		return false
	end
	local ents = TheWorld.Map:GetEntitiesOnTileAtPoint(pt.x, 0, pt.z)
	for _, ent in ipairs(ents) do
		if ent ~= inst and ent ~= deployer
			and not (ent:HasTag("NOBLOCK") or ent:HasTag("locomotor")
				or ent:HasTag("NOCLICK") or ent:HasTag("FX") or ent:HasTag("DECOR")) then
			return false
		end
	end
	return true
end

local function item_ondeploy(inst, pt, deployer)
	local cx, cy, cz = TheWorld.Map:GetTileCenterPoint(pt:Get())
	local obj = SpawnPrefab("aom_tractor_chassis")
	obj.Transform:SetPosition(cx, cy, cz)

	-- 恢复燃料与耐久
	if inst.aom_packed_fuel ~= nil then
		obj:SetFuel(inst.aom_packed_fuel)
	end
	if inst.aom_packed_uses ~= nil then
		obj.components.finiteuses:SetUses(inst.aom_packed_uses)
	end
    if inst.aom_packed_plan then AOMBlock.OnLoad(obj,inst.aom_packed_plan) end
    if inst.aom_packed_strategy then
        obj._seed_strategy=inst.aom_packed_strategy
        obj._seedmode_net:set(obj._seed_strategy)
    end
    obj._planprogress_net:set(AOMBlock.DescribeProgress(obj))
	-- 挂件与物料倒回本体的容器
	if inst.components.container ~= nil and obj.components.container ~= nil then
		for i = 1, inst.components.container.numslots or 0 do
			local item = inst.components.container:GetItemInSlot(i)
			if item ~= nil then
				inst.components.container:RemoveItem(item, true)
				obj.components.container:GiveItem(item)
			end
		end
	end

	inst:Remove()
end

---------------------------------------------------------------------------
-- 本体
---------------------------------------------------------------------------

local function fn()
	local inst = CreateEntity()

	inst.entity:AddTransform()
	inst.entity:AddAnimState()
	inst.entity:AddSoundEmitter()
	inst.entity:AddNetwork()

	inst.AnimState:SetBank("aom_tractor_chassis")
	inst.AnimState:SetBuild("aom_tractor_chassis")
	inst.AnimState:PlayAnimation("idle")

	MakeObstaclePhysics(inst, 1.0)
	SetPhysicsAttacker(inst, 20)

	inst:AddTag("structure")
	inst:AddTag(AOM.TAG.TRACTOR)
	DriverVisual.Attach(inst)
	-- 原版 rideable 场景动作靠此标签显示 MOUNT；本体必须可点击。
	inst:AddTag("rideable")

	inst._fertilizeruses_net=net_float(inst.GUID,"aom_tractor_chassis.fertilizeruses","aomfertilizerdirty")
	inst._fertilizerstock_net=net_string(inst.GUID,"aom_tractor_chassis.fertilizerstock","aomfertilizerdirty")
	inst._water_net=net_float(inst.GUID,"aom_tractor_chassis.water","aomwaterdirty")
	inst._watermax_net=net_float(inst.GUID,"aom_tractor_chassis.watermax","aomwaterdirty")
	inst._fuel = net_float(inst.GUID, "aom_tractor_chassis.fuel", "aomfueldirty")
	inst._attachment = net_entity(inst.GUID, "aom_tractor_chassis.attachment", "aomattachmentdirty")
	-- 驾驶/作业状态同步给客户端（UI 与其它玩家可见）
	inst._rider_net = net_entity(inst.GUID, "aom_tractor_chassis.rider", "aomriderdirty")
	inst._workstatus = net_bool(inst.GUID, "aom_tractor_chassis.working", "aomworkdirty")
	inst._speedfactor_net=net_float(inst.GUID,"aom_tractor_chassis.speedfactor","aomspeeddirty")
	-- 用 net_string 同步策略名（net_uint 无法在源码中确认存在，避免踩空）
	inst._seedmode_net = net_string(inst.GUID, "aom_tractor_chassis.seedmode", "aomseedmodedirty")
    inst._workreason_net = net_string(inst.GUID, "aom_tractor_chassis.workreason", "aomworkreasondirty")
    inst._planprogress_net = net_string(inst.GUID, "aom_tractor_chassis.planprogress", "aomplanprogressdirty")

	inst.AnimState:OverrideSymbol("attachment", "aom_attachment_symbols", "empty")
	inst.AnimState:HideSymbol("attachment_front")

	inst.entity:SetPristine()

	if not TheWorld.ismastersim then
		return inst
	end

	inst:AddComponent("inspectable")

	inst:AddComponent("health")
	inst.components.health:SetMaxHealth(MAX_HEALTH)
	inst.components.health:SetVal(MAX_HEALTH, "none")
	inst:ListenForEvent("death", OnHealthDead)

	-- 移动能力：角色骑上来后，locomotor 的速度会被角色直接继承
	-- （见原版 components/locomotor.lua: ServerRunSpeed 读取 mount.runspeed）
	inst:AddComponent("locomotor")
	inst.components.locomotor.runspeed = Profile.BASE_SPEED
	inst.components.locomotor.walkspeed = inst.components.locomotor.runspeed

	-- 可骑乘：不要求驯化、不要求鞍具
	-- 不调 SetRequiredObedience：该组件在没有 domesticatable 时 TestObedience 恒为 true
	inst:AddComponent("rideable")
	inst.components.rideable:SetSaddleable(false)
	inst:RemoveTag("saddleable") -- 驾驶座代替牛鞍，不接受原版装鞍动作。
	inst.components.rideable:SetShouldSave(true)
	-- ActualDismount 会让坐骑回到 idle，底盘也必须有状态机。
	inst:SetStateGraph("SGaom_tractor")
	inst:ListenForEvent("riderchanged", function(inst, data)
		if data ~= nil and data.newrider ~= nil then
			AOMDrive.OnMounted(inst, { rider = data.newrider })
		else
			AOMDrive.OnDismounted(inst)
		end
	end)

	-- 油量用 net_float 自己记（原版 fuel 组件是给可燃烧物用的）
	SetFuel(inst, STARTING_FUEL)
	inst:ListenForEvent("aomfueldirty", function()
		inst:PushEvent("aom_refuel_changed", { fuel = GetFuel(inst) })
	end)

	inst:AddComponent("finiteuses")
	inst.components.finiteuses:SetMaxUses(MAX_USES)
	inst.components.finiteuses:SetUses(MAX_USES)

	inst:AddComponent("workable")
	inst.components.workable:SetWorkAction(ACTIONS.HAMMER)
	inst.components.workable:SetWorkLeft(4)
	inst.components.workable:SetOnFinishCallback(function()
		-- 锤子拆除 = "打包搬家"：产出打包物品，并带走燃料/耐久/挂件/物料。
		-- 不能生成本体 prefab，否则等于凭空造一台新车，状态全部重置。
		local x, _, z = inst.Transform:GetWorldPosition()
		local drop = SpawnPrefab("aom_tractor_item")
		if drop ~= nil then
			drop.Transform:SetPosition(x, 0, z)
			drop.aom_packed_fuel = GetFuel(inst)
			drop.aom_packed_uses = inst.components.finiteuses:GetUses()
            drop.aom_packed_plan = AOMBlock.OnSave(inst)
            drop.aom_packed_strategy = inst._seed_strategy
			-- 挂件与物料：连同容器内容一起转交给打包物品
			if inst.components.container ~= nil then
				local items = {}
				for i = 1, inst.components.container.numslots or 0 do
					local item = inst.components.container:GetItemInSlot(i)
					if item ~= nil then
						inst.components.container:RemoveItem(item, true)
						table.insert(items, item)
					end
				end
				-- 放进打包物品的容器（随 container 存档，读档不丢）
				if drop.components.container ~= nil then
					for _, item in ipairs(items) do
						drop.components.container:GiveItem(item)
					end
				end
			end
		end
		inst:Remove()
	end)
	-- 挂件槽：1 格，只接受带 aom_attachment tag 的物品
	-- 一个容器同时承担"挂件槽 + 物料仓"：
	--   第 1 格固定放挂件；第 2~9 格放种子/肥料等物料（普通物品，随容器存档）
	inst:AddComponent("container")
	inst.components.container:WidgetSetup("aom_tractor_chassis")
	inst.components.container.canbeopened = true
	inst:ListenForEvent("itemget", OnAttachmentChanged)
	inst:ListenForEvent("itemlose", OnAttachmentChanged)

	inst:AddComponent("aom_attachment_store")
	inst.components.aom_attachment_store:SetMaterialContainer(inst.components.container)
	inst:ListenForEvent("aom_water_changed",Irrigator.Sync)
    inst:ListenForEvent("aom_load_changed",Fertilizer.Watch)
    inst:ListenForEvent("stacksizechange",Fertilizer.Sync)

	inst._rider = nil
	inst._working = false
	inst._seed_strategy = "SEQUENTIAL"
    inst._seedmode_net:set("SEQUENTIAL")
	inst._giant_planted = {}
	inst._attachment_type = nil

	inst.TryRefuel = TryRefuel
	inst.TryRepair = TryRepair
	inst.SetFuel = SetFuel
	inst.ToggleWorking = AOMDrive.ToggleWorking
	inst.SetWorking = AOMDrive.SetWorking
	inst.CycleSeedStrategy = AOMDrive.CycleSeedStrategy
	inst.GetSeedStrategyName = AOMDrive.GetSeedStrategyName
	inst.WorkHere = AOMDrive.WorkHere

	inst.OnSave = OnSave
	inst.OnLoad = OnLoad
	inst.OnLoadPostPass = OnLoadPostPass

	-- 车被锤掉 / 被摧毁 / 消失时，强制放下骑手，避免玩家卡在骑乘态
	inst:ListenForEvent("onremove", function()
		local rider = inst._rider
		if rider ~= nil and rider:IsValid()
			and rider.components.rider ~= nil
			and rider.components.rider:IsRiding()
			and rider.components.rider:GetMount() == inst then
			rider.components.rider:ActualDismount()
		end
	end)

	return inst
end

-- 放置预览（与 farm_plow_item_placer 同构）
local placer = MakePlacer(
	"aom_tractor_placer",
	"aom_tractor_chassis",
	"aom_tractor_chassis",
	"idle",
	true,    -- onground
	false,   -- snap
	false,   -- metersnap
	1,       -- scale
	nil,     -- fixedcameraoffset
	nil,     -- facing
	nil,     -- postinit
	Vector3(0, 0, 0),
	can_place_tractor
)

-- 打包物品：可放背包，放置后生成本体
local function item_fn()
	local inst = CreateEntity()

	inst.entity:AddTransform()
	inst.entity:AddAnimState()
	inst.entity:AddNetwork()

	MakeInventoryPhysics(inst)

	inst.AnimState:SetBank("aom_tractor_chassis")
	inst.AnimState:SetBuild("aom_tractor_chassis")
	-- 打包物品用木箱形态（美术包 idle_packed 帧）
	inst.AnimState:PlayAnimation("idle_packed")

	inst:AddTag("usedeploystring")

	MakeInventoryFloatable(inst, "med", 0.1, 1, true)

	inst._custom_candeploy_fn = can_place_tractor

	inst.entity:SetPristine()

	if not TheWorld.ismastersim then
		return inst
	end

	inst:AddComponent("inspectable")
	inst:AddComponent("inventoryitem")
	inst.components.inventoryitem.atlasname = "images/aom_chassis_inventory.xml"
	inst.components.inventoryitem.imagename = "aom_tractor_item"

	-- 打包物品自带一个 9 格容器，用于保存挂件与物料（container 组件自带存档）
	inst:AddComponent("container")
	inst.components.container:WidgetSetup("aom_tractor_chassis")
	inst.components.container.canbeopened = false
	inst.components.container.skipclosesnd = true
	inst.components.container.skipopensnd = true

	inst:AddComponent("deployable")
	inst.components.deployable.ondeploy = item_ondeploy
	inst.components.deployable.placer = "aom_tractor_placer"

    inst.OnSave=function(item,data)
        data.aom_packed_fuel=item.aom_packed_fuel
        data.aom_packed_uses=item.aom_packed_uses
        data.aom_packed_plan=item.aom_packed_plan
        data.aom_packed_strategy=item.aom_packed_strategy
    end
    inst.OnLoad=function(item,data)
        if not data then return end
        item.aom_packed_fuel=data.aom_packed_fuel
        item.aom_packed_uses=data.aom_packed_uses
        item.aom_packed_plan=data.aom_packed_plan
        item.aom_packed_strategy=data.aom_packed_strategy
    end
	MakeHauntableLaunch(inst)

	return inst
end

return Prefab("aom_tractor_chassis", fn, assets, prefabs),
	Prefab("aom_tractor_item", item_fn, assets, prefabs),
	placer
