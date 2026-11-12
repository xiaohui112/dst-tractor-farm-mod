--[[
	Tractor —— 拖拉机底盘

	形态：可骑乘的机械。上下车沿用原版骑牛的 MOUNT / DISMOUNT，
	方向键驾驶，F 开关作业，驶过地块完成工序，作业类型决定速度。
]]

local AOMFarmWork = require("aom_farm_work")
local AOM = require("aom_common")
local AOMDrive = require("aom_drive")
local AOMBlock = require("aom_block_plan")
local Profile = require("aom_work_profile")
local Durability = require("aom_durability")
local Irrigator = require("aom_irrigator")
local DriverVisual = require("aom_driver_visual")
local Fertilizer = require("aom_fertilizer")
local Mount=require("aom_attachment_mount")

-- 五视图资源按成年牛体量制作；地面、骑乘与挂件共用同一倍率。
local MODEL_SCALE = require("aom_model_scale")

local assets =
{
	Asset("ANIM", "anim/aom_tractor_chassis.zip"),
	Asset("ANIM", "anim/aom_attachment_symbols.zip"),
	Asset("ATLAS", "images/aom_tractor_icons.xml"),
	Asset("IMAGE", "images/aom_tractor_icons.tex"),
	Asset("ATLAS", "images/aom_chassis_inventory.xml"),
	Asset("IMAGE", "images/aom_chassis_inventory.tex"),
}

-- 当前配方直接生成世界本体。aom_tractor_item只作为旧存档迁移入口。

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
    "aom_refill_hose",
}

-- 燃料：木炭
local FUEL_PREFAB = "charcoal"
local MAX_FUEL = 800
local FUEL_PER_TICK = 1
local MAX_HEALTH = 600
local MAX_USES = Durability.MAX_USES
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
-- 挂件变化
---------------------------------------------------------------------------

local function OnUsesChanged(inst)
    Irrigator.Sync(inst)
    Durability.Sync(inst)
end
local function OnAttachmentChanged(inst)
	local previous=inst._watched_attachment
	local item = Mount.Get(inst)
	if item ~= nil and item.attachment_type ~= nil then
		inst._attachment_type = item.attachment_type
		inst._attachment:set(item)
	else
		inst._attachment_type = nil
		inst._attachment:set(nil)
		-- 没有挂件就不能继续作业
		AOMDrive.SetWorking(inst, false)
	end
	if inst._atttype_net ~= nil then
		inst._atttype_net:set(inst._attachment_type or "")
	end
	if previous~=item then
        -- 外部事件的首参是配件而非车辆；闭包固定刷新所属车的仪表。
        if not inst._attachment_uses_changed then inst._attachment_uses_changed=function()OnUsesChanged(inst)end end
        if previous then inst:RemoveEventCallback("percentusedchange",inst._attachment_uses_changed,previous) end
        inst._watched_attachment=item
        if item then inst:ListenForEvent("percentusedchange",inst._attachment_uses_changed,item) end
        AOMDrive.SetWorking(inst,false)
    end
    OnUsesChanged(inst)
    DriverVisual.UpdateAttachment(inst,inst._aom_driver_animstate)
    Fertilizer.Watch(inst)
    Durability.WatchSeeds(inst)
    -- Real attachment entity is independently rendered and clickable.
    inst.AnimState:OverrideSymbol("attachment","aom_attachment_symbols","empty")
    inst.AnimState:HideSymbol("attachment_front")
	if inst._fuel_hudtask == nil then
		inst._fuel_hudtask = inst:DoPeriodicTask(2, function()
			inst:PushEvent("aom_refuel_changed", { fuel = AOMDrive.GetFuel(inst) })
		end)
	end
end

local function AttachAttachment(inst,doer,item)return Mount.Attach(inst,doer,item)end
local function DetachAttachment(inst,doer)return Mount.Detach(inst,doer)end

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
	if inst._destroyed or inst.components.health:IsDead() then return false end
	-- 支持原版燃料（wood / charcoal 等 burnable）
	if item == nil or item.components.fuel == nil then
		return false
	end
	local room = MAX_FUEL - GetFuel(inst)
	if room <= 0 then
		return false
	end
	local v = item.components.fuel.fuelvalue
	if type(v)~="number" or v~=v or v<=0 or v==math.huge then return false end
	if item.components.fuel.fueltype~=nil and item.components.fuel.fueltype~=FUELTYPE.BURNABLE then return false end
	-- 燃料以整份投入，余量封顶；只要增加油量就消耗一份，满箱不消耗。
	local used = math.min(room, v)
	SetFuel(inst, GetFuel(inst) + used)
	ConsumeOne(item)
	return true
end

local function TryRepair(inst, doer, item)
	if item == nil then return false end
	local rider=doer and doer.components.rider
	if rider and rider:IsRiding() then return false end
	-- 齿轮同时修复车体血量和作业耐久；残骸原地恢复，不重置油量或货物。
	if item.prefab == "gears" then
		local health,uses=inst.components.health,inst.components.finiteuses
		if health.currenthealth>=MAX_HEALTH and uses:GetUses()>=MAX_USES then return false end
		ConsumeOne(item)
		health:SetVal(math.min(MAX_HEALTH,math.max(0,health.currenthealth)+100))
		uses:SetUses(math.min(MAX_USES,uses:GetUses()+100))
		inst._destroyed=nil
		inst._wreck_net:set(false)
		inst._health_net:set(health.currenthealth)
		inst.components.workable:SetWorkable(true)
		SetFuel(inst,GetFuel(inst))
		inst.AnimState:SetMultColour(1,1,1,1)
		inst.AnimState:PlayAnimation("idle",true)
		inst.SoundEmitter:PlaySound("dontstarve/HUD/click_move")
		return true
	end
	return false
end

---------------------------------------------------------------------------
-- 生命周期
---------------------------------------------------------------------------

local function OnSave(inst, data)
	if data == nil then return end
	data.fuel = GetFuel(inst)
    require("aom_pond_refill").Cancel(inst)
    local attachment=Mount.Current(inst)
    if attachment and attachment:IsValid() then data.aom_attachment_record=attachment:GetSaveRecord() end
	data.attachment_type = inst._attachment_type
	data.seed_strategy = inst._seed_strategy
	data.block = AOMBlock.OnSave(inst)
end

local function OnLoad(inst, data)
	if data == nil then return end
    -- 音乐以当前Mod配置为准，不恢复旧车的独立开关。
    inst._aom_attachment_record=data.aom_attachment_record
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
        AOMBlock.Sync(inst)
	end
end

local function OnHealthDead(inst)
	inst._destroyed=true
	local rider=inst._rider
	if rider ~= nil and rider.components.rider ~= nil then
		AOMDrive.Dismount(inst,rider)
		-- 立即把驾驶员放到地上，不能等骑乘状态机下一帧才释放坐骑。
		if rider.components.rider:IsRiding() and rider.components.rider:GetMount()==inst then
			rider.components.rider:ActualDismount()
			if rider.sg then rider.sg:GoToState("idle") end
		end
	end
	AOMDrive.SetWorking(inst, false)
	inst.components.rideable.canride=false
	inst.AnimState:PlayAnimation("death")
	inst.components.workable:SetWorkable(true)
	-- 保留可维修、可锤拆的残骸；挂件及货物落地，不返还制造材料。
	if inst._aom_attachment then Mount.Detach(inst,nil,true) end
	inst.components.container:DropEverything()
	inst._wreck_net:set(true)
	inst._health_net:set(0)
	inst.AnimState:SetMultColour(.45,.45,.45,1)
	inst.persists=true
	if rider and rider.components.talker then
		rider.components.talker:Say(require("aom_locale").Text("拖拉机已损毁，配件和货物已落地；用齿轮修复残骸"))
	end
end

local function OnLoadPostPass(inst)
    Mount.Restore(inst,inst._aom_attachment_record or inst._aom_legacy_attachment_record)
    inst._aom_attachment_record=nil;inst._aom_legacy_attachment_record=nil
    if inst.components.health:IsDead() then
        OnHealthDead(inst)
        -- 旧死亡存档的组件加载顺序不固定；最后再回收后来恢复的容器内容。
        inst.components.container:DropEverything()
        inst.components.rideable.canride=false
    else OnAttachmentChanged(inst) end
    inst._health_net:set(inst.components.health.currenthealth)
end

---------------------------------------------------------------------------
-- 放置 / 打包
---------------------------------------------------------------------------

local function can_place_tractor(inst, pt, mouseover, deployer)
	local cx,_,cz=TheWorld.Map:GetTileCenterPoint(pt.x,0,pt.z)
	if cx==nil or not TheWorld.Map:CanPlantAtPoint(cx, 0, cz) then
		return false
	end
	local ents = TheWorld.Map:GetEntitiesOnTileAtPoint(cx, 0, cz)
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
    if inst.aom_packed_health~=nil then obj.components.health:SetVal(inst.aom_packed_health) end
    if inst.aom_packed_plan then AOMBlock.OnLoad(obj,inst.aom_packed_plan) end
    if inst.aom_packed_strategy then
        obj._seed_strategy=inst.aom_packed_strategy
        obj._seedmode_net:set(obj._seed_strategy)
    end
    obj._planprogress_net:set(AOMBlock.DescribeProgress(obj))
	-- 挂件与物料倒回本体的容器
    Mount.Restore(obj,inst._aom_legacy_attachment_record)
    inst._aom_legacy_attachment_record=nil
	if inst.components.container ~= nil and obj.components.container ~= nil then
		for i = 1, inst.components.container.numslots or 0 do
			local item = inst.components.container:GetItemInSlot(i)
			if item ~= nil then
				inst.components.container:RemoveItem(item, true)
				if item:HasTag(AOM.TAG.ATTACHMENT) then
                    if not Mount.Attach(obj,nil,item) then item.Transform:SetPosition(cx,cy,cz) end
                else obj.components.container:GiveItem(item,i,Vector3(cx,cy,cz)) end
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
	inst.Transform:SetEightFaced()

	inst.AnimState:SetBank("aom_tractor_chassis")
	inst.AnimState:SetBuild("aom_tractor_chassis")
	inst.AnimState:SetScale(MODEL_SCALE, MODEL_SCALE, MODEL_SCALE)
	inst.AnimState:PlayAnimation("idle")

	MakeObstaclePhysics(inst, 1.0)

	inst:AddTag("structure")
	inst:AddTag(AOM.TAG.TRACTOR)
	-- 空车不进入普通生物的索敌列表；承伤通过原版骑手伤害转移进入。
	inst:AddTag("notarget")
	inst:AddTag("peacefulmount")
    inst.GetAttachment=Mount.Current
	DriverVisual.Attach(inst)
	-- 原版 rideable 场景动作靠此标签显示 MOUNT；本体必须可点击。
	inst:AddTag("rideable")

	inst._fertilizeruses_net=net_float(inst.GUID,"aom_tractor_chassis.fertilizeruses","aomfertilizerdirty")
	inst._fertilizerstock_net=net_string(inst.GUID,"aom_tractor_chassis.fertilizerstock","aomfertilizerdirty")
	inst._water_net=net_float(inst.GUID,"aom_tractor_chassis.water","aomwaterdirty")
	inst._watermax_net=net_float(inst.GUID,"aom_tractor_chassis.watermax","aomwaterdirty")
	inst._cargo_used_net=net_float(inst.GUID,"aom_tractor_chassis.cargoused","aomcargodirty")
    inst._refilling_net=net_bool(inst.GUID,"aom_tractor_chassis.refilling","aomrefilldirty")
    inst._music_mode_net=net_string(inst.GUID,"aom_tractor_chassis.musicmode","aommusicdirty")
    inst._cargo_count_net=net_float(inst.GUID,"aom_tractor_chassis.cargocount","aomcargodirty")
	inst._music_enabled_net=net_bool(inst.GUID,"aom_tractor_chassis.musicenabled","aommusicdirty")
	inst._music_available_net=net_bool(inst.GUID,"aom_tractor_chassis.musicavailable","aommusicdirty")
	inst._health_net=net_float(inst.GUID,"aom_tractor_chassis.health","aomhealthdirty")
	inst._wreck_net=net_bool(inst.GUID,"aom_tractor_chassis.wreck","aomwreckdirty")
	inst:ListenForEvent("aomwreckdirty",function()
		local wreck=inst._wreck_net:value()
		inst.AnimState:SetMultColour(wreck and .45 or 1,wreck and .45 or 1,wreck and .45 or 1,1)
		inst.AnimState:PlayAnimation(wreck and "death" or "idle",not wreck)
	end)
	inst._fuel = net_float(inst.GUID, "aom_tractor_chassis.fuel", "aomfueldirty")
    inst._uses_net=net_float(inst.GUID,"aom_tractor_chassis.uses","aomusesdirty")
    inst._tooluses_net=net_float(inst.GUID,"aom_tractor_chassis.tooluses","aomusesdirty")
    inst._toolmax_net=net_float(inst.GUID,"aom_tractor_chassis.toolmax","aomusesdirty")
    inst._seedcount_net=net_float(inst.GUID,"aom_tractor_chassis.seedcount","aomseedsdirty")
	inst._attachment = net_entity(inst.GUID, "aom_tractor_chassis.attachment", "aomattachmentdirty")
	-- 客户端拿不到容器里的实体引用，挂件类型单独用 net_string 同步给 HUD。
	inst._atttype_net = net_string(inst.GUID, "aom_tractor_chassis.atttype", "aomatttypedirty")
	-- 驾驶/作业状态同步给客户端（UI 与其它玩家可见）
	inst._rider_net = net_entity(inst.GUID, "aom_tractor_chassis.rider", "aomriderdirty")
	inst._workstatus = net_bool(inst.GUID, "aom_tractor_chassis.working", "aomworkdirty")
	inst._speedfactor_net=net_float(inst.GUID,"aom_tractor_chassis.speedfactor","aomspeeddirty")
	-- 用 net_string 同步策略名（net_uint 无法在源码中确认存在，避免踩空）
	inst._seedmode_net = net_string(inst.GUID, "aom_tractor_chassis.seedmode", "aomseedmodedirty")
    -- dirty 事件表示整组失效，监听者重读整组；共享事件不承诺跨 netvar 原子快照。
    -- 原因与参数需要一致快照，因此只使用一个载荷。
    inst._workstate_net = net_string(inst.GUID, "aom_tractor_chassis.workstate", "aomworkreasondirty")
    inst._plan_net=net_string(inst.GUID,"aom_tractor_chassis.plan","aomplanprogressdirty")
    inst._planprogress_net = net_string(inst.GUID, "aom_tractor_chassis.planprogress", "aomplanprogressdirty")

	inst.AnimState:OverrideSymbol("attachment", "aom_attachment_symbols", "empty")
	inst.AnimState:HideSymbol("attachment_front")

	inst.entity:SetPristine()
	require("aom_vehicle_motion").Attach(inst)

	if not TheWorld.ismastersim then
		return inst
	end
    inst._music_mode_net:set(require("aom_irrigator_music").mode)
	inst._music_enabled_net:set(true)
	inst._music_available_net:set(require("aom_irrigator_music").ready==true)

	inst:AddComponent("inspectable")
	inst.components.inspectable.descriptionfn=function()
		if inst._destroyed then
			return require("aom_locale").Text("拖拉机残骸：手持齿轮右键修理，每个恢复100生命和100作业耐久")
		end
	end

	inst:AddComponent("health")
	inst.components.health:SetMaxHealth(MAX_HEALTH)
	inst.components.health:SetVal(MAX_HEALTH, "none")
	-- 原版 Health 默认会在死亡后腐蚀删除；残骸必须由玩家修复或锤拆。
	inst.components.health.nofadeout=true
	inst._health_net:set(MAX_HEALTH)
	inst:ListenForEvent("healthdelta",function()
		inst._health_net:set(inst.components.health.currenthealth)
	end)
	inst:ListenForEvent("death", OnHealthDead)
	-- 让原版 Rider 自动接管近战承伤，远程、电击和黑暗保留其原有例外。
	inst:AddComponent("combat")
	inst.components.combat.canattack=false

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
    inst:ListenForEvent("percentusedchange",Durability.Sync)
    Durability.Sync(inst)

	inst:AddComponent("workable")
	inst.components.workable:SetWorkAction(ACTIONS.HAMMER)
	inst.components.workable:SetWorkLeft(4)
    inst.components.workable:SetOnFinishCallback(function()
        if inst._aom_attachment and not Mount.Detach(inst,nil) then
            inst.components.workable:SetWorkLeft(4)
            return
        end
        AOMDrive.SetWorking(inst,false)
        inst.components.container:DropEverything()
        for name,count in pairs({gears=2,transistor=1,boards=3,flint=4}) do
            for _=1,count do
                local loot=SpawnPrefab(name)
                if loot then loot.Transform:SetPosition(inst.Transform:GetWorldPosition()) end
            end
        end
        inst:Remove()
    end)

	inst:AddComponent("container")
	inst.components.container:WidgetSetup("aom_tractor_chassis")
	inst.components.container.canbeopened = true
    -- 原版会在骑手没有 keep_pocket_rummage 状态时马上关仓；拖拉机允许边开车边看物料。
    local original_update=inst.components.container.OnUpdate
    inst.components.container.OnUpdate=function(container,dt)
        local rider=inst._rider
        if rider and rider:IsValid() and container:IsOpenedBy(rider)
            and rider.components.rider and rider.components.rider:GetMount()==inst then return end
        return original_update(container,dt)
    end
	local original_load=inst.components.container.OnLoad
    inst.components.container.OnLoad=function(c,data,newents)
        if data and data.items then
            local cargo={};for k,v in pairs(data.items) do
                if Mount.IsRecord(v) then
                    inst._aom_legacy_attachment_record=v
                else cargo[k]=v end
            end
            return original_load(c,{items=cargo},newents)
        end
        return original_load(c,data,newents)
    end
    inst:ListenForEvent("aom_attachment_changed",OnAttachmentChanged)
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
	inst.AttachAttachment = AttachAttachment
	inst.DetachAttachment = DetachAttachment
	inst.SetFuel = SetFuel
	inst.ToggleWorking = AOMDrive.ToggleWorking
	inst.SetWorking = AOMDrive.SetWorking
	inst.CycleSeedStrategy = AOMDrive.CycleSeedStrategy
	inst.GetSeedStrategyName = AOMDrive.GetSeedStrategyName
	inst.WorkHere = AOMDrive.WorkHere

	inst.OnSave = OnSave
	inst.OnLoad = OnLoad
	inst.OnLoadPostPass = OnLoadPostPass

    local music_ok,music=pcall(require,"aom_irrigator_music")
    if music_ok then music.AttachTending(inst) end

	-- 车被锤掉 / 被摧毁 / 消失时，强制放下骑手，避免玩家卡在骑乘态
	inst:ListenForEvent("onremove", function()
		if inst._aom_attachment then Mount.Detach(inst,nil,true) end
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

-- 车体精灵必须直立显示；贴地投影只适用于地毯、地皮等平面素材。
local function placer_postinit(inst)
    inst.components.placer.snap_to_tile=true
    inst.AnimState:OverrideSymbol("attachment","aom_attachment_symbols","empty")
    inst.AnimState:HideSymbol("attachment_front")
end
local structure_placer=MakePlacer("aom_tractor_chassis_placer","aom_tractor_chassis","aom_tractor_chassis","idle",false,false,false,MODEL_SCALE,nil,"eight",placer_postinit)
local placer = MakePlacer(
	"aom_tractor_item_placer",
	"aom_tractor_chassis",
	"aom_tractor_chassis",
	"idle",
	false,            -- onground：保持车体直立，避免被压成地面贴图
	false,            -- snap
	false,            -- metersnap
	MODEL_SCALE,      -- scale
	nil,              -- fixedcameraoffset
	"eight",          -- facing：与实际部署后的车体一致
	placer_postinit,  -- postinit_fn
	Vector3(0, 0, 0), -- offset
	nil               -- onfailedplacement，不是可放置校验回调
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
	inst.AnimState:SetScale(MODEL_SCALE, MODEL_SCALE, MODEL_SCALE)
	-- 打包物品使用 idle_packed 的缩小车体。
	inst.AnimState:PlayAnimation("idle_packed")

	inst:AddTag("usedeploystring")

	MakeInventoryFloatable(inst, "med", 0.1, 1, true)

	inst._custom_candeploy_fn = can_place_tractor
	-- 部署预览用的 placer 名默认是 "<prefab>_placer"，也就是 aom_tractor_item_placer
	-- （不存在，实机日志刷 "Can't find prefab"）；这里指向真正的 placer。
	inst.overridedeployplacername = "aom_tractor_item_placer"

	inst.entity:SetPristine()

	if not TheWorld.ismastersim then
		return inst
	end

	inst:AddComponent("inspectable")
	inst:AddComponent("inventoryitem")
	inst.components.inventoryitem.atlasname = "images/aom_chassis_inventory.xml"
	inst.components.inventoryitem.imagename = "aom_tractor_item"
    inst.components.inventoryitem.canbepickedup=false
    inst.components.inventoryitem.cangoincontainer=false

	-- 打包物品自带一个 9 格容器，用于保存挂件与物料（container 组件自带存档）
	inst:AddComponent("container")
	inst.components.container:WidgetSetup("aom_tractor_chassis")
	inst.components.container.canbeopened = false
	inst.components.container.skipclosesnd = true
	inst.components.container.skipopensnd = true
    local legacy_load=inst.components.container.OnLoad
    inst.components.container.OnLoad=function(c,data,newents)
        local cargo={}
        for slot,record in pairs(data and data.items or {}) do
            if Mount.IsRecord(record) then
                inst._aom_legacy_attachment_record=record
            else cargo[slot]=record end
        end
        return legacy_load(c,{items=cargo},newents)
    end

	inst:AddComponent("deployable")
	inst.components.deployable:SetDeployMode(DEPLOYMODE.CUSTOM)
	inst.components.deployable.ondeploy = item_ondeploy

    inst.OnSave=function(item,data)
        data.aom_packed_fuel=item.aom_packed_fuel
        data.aom_packed_uses=item.aom_packed_uses
        data.aom_packed_health=item.aom_packed_health
        data.aom_packed_plan=item.aom_packed_plan
        data.aom_packed_strategy=item.aom_packed_strategy
        data.aom_legacy_attachment_record=item._aom_legacy_attachment_record
    end
    inst.OnLoad=function(item,data)
        if not data then return end
        item.aom_packed_fuel=data.aom_packed_fuel
        item.aom_packed_uses=data.aom_packed_uses
        item.aom_packed_health=data.aom_packed_health
        item.aom_packed_plan=data.aom_packed_plan
        item.aom_packed_strategy=data.aom_packed_strategy
        item._aom_legacy_attachment_record=item._aom_legacy_attachment_record or data.aom_legacy_attachment_record
        -- 存档加载物品时原版Inventory/Container仍会检查cangoincontainer；
        -- 迁移完成前允许恢复到原库存，避免OnLoad阶段被提前抛出。
        item.components.inventoryitem.cangoincontainer=true
        -- 先找到可用位置再移出原库存；无落点时保留归属并定时重试。
        local warned=false
        local function unpack_pending()
            if not item:IsValid() then return end
            local ii=item.components.inventoryitem
            local owner=ii.owner
            local x,_,z=(owner or item).Transform:GetWorldPosition()
            for radius=0,24,4 do
                for i=0,15 do
                    local angle=i*math.pi/8
                    local cx,cy,cz=TheWorld.Map:GetTileCenterPoint(x+radius*math.cos(angle),0,z+radius*math.sin(angle))
                    if cx then
                        local point=Vector3(cx,cy,cz)
                        if can_place_tractor(item,point,nil,owner) then
                            if owner then ii:RemoveFromOwner(true) end
                            item_ondeploy(item,point,owner)
                            return
                        end
                    end
                end
            end
            if not warned and owner and owner.components.talker then
                owner.components.talker:Say(require("aom_locale").Text("旧拖拉机附近没有展开空地，已保留物品；移到空地后会自动重试"))
                warned=true
            end
            item._aom_unpack_task=item:DoTaskInTime(5,unpack_pending)
        end
        item._aom_unpack_task=item:DoTaskInTime(0,unpack_pending)
    end
	MakeHauntableLaunch(inst)

	return inst
end

return Prefab("aom_tractor_chassis", fn, assets, prefabs),
	Prefab("aom_tractor_item", item_fn, assets, prefabs),
	placer, structure_placer
