--[[
	Tractor —— 拖拉机驾驶与作业

	设计（按需求）：
	1. 上下车沿用原版 MOUNT / DISMOUNT；底盘带 rideable 组件，
	   Rider:Mount 把车挂到角色并隐藏车体，角色使用 wilsonbeefalo 动画库，
	   移动速度自动继承挂载物的 locomotor.runspeed（见原版 locomotor.lua:93）。
	2. F 开关作业；驶入地块时整格作业，停车不重复消耗。
	3. 挂件必须手动装上；速度随作业类型变化，关闭作业恢复空驶速度。

	农业行为最终调用原版组件；洒水与施肥由独立模块按地块管理批次和消耗。
]]

local AOMFarmWork = require("aom_farm_work")
local AOM = require("aom_common")

local AOMDrive = {}
local AOMSeed = require("aom_seed_strategy")
local AOMBlock = require("aom_block_plan")
local Profile = require("aom_work_profile")
local LandClearer = require("aom_landclearer_tool")
local Weeder = require("aom_weeder_tool")
local Irrigator = require("aom_irrigator")
local Fertilizer = require("aom_fertilizer")

---------------------------------------------------------------------------
-- 基础：取/存状态
---------------------------------------------------------------------------

local function GetFuel(inst)
	return inst._fuel ~= nil and inst._fuel:value() or 0
end

function AOMDrive.GetFuel(inst)
	return GetFuel(inst)
end

function AOMDrive.SetFuel(inst, v)
	local fuel = math.max(0, v)
	inst._fuel:set(fuel)
	if inst.components.rideable ~= nil then
		-- 原版 MOUNT.fn 检查 canride；它的 setter 同步 rideable 标签。
		inst.components.rideable.canride = fuel > 0
	end
end

local function ConsumeFuel(inst, amount)
	local fuel = GetFuel(inst)
	if fuel < amount then
		return false
	end
	AOMDrive.SetFuel(inst, fuel - amount)
	return true
end

---------------------------------------------------------------------------
-- 挂件必须手动安装
---------------------------------------------------------------------------

function AOMDrive.GetAttachmentType(inst)
	return inst._attachment_type
end

function AOMDrive.HasAttachment(inst)
	return inst._attachment_type ~= nil
end

function AOMDrive.UpdateSpeed(inst)
    local speed=Profile.Speed(inst._attachment_type,inst._working)
    if inst.components.locomotor then
        inst.components.locomotor.runspeed=speed
        inst.components.locomotor.walkspeed=speed
    end
    if inst._speedfactor_net then inst._speedfactor_net:set(speed/Profile.BASE_SPEED) end
    -- 原版只在 SetMount 时写一次骑乘预测速度；作业切换时需同步刷新。
    local rider=inst._rider
    local replica=rider and rider.replica and rider.replica.rider
    local classified=replica and replica.classified
    if classified then classified.riderrunspeed:set(speed) end
end

---------------------------------------------------------------------------
-- 作业
---------------------------------------------------------------------------

-- 取出本次作业要消耗的材料
-- 播种机的"取哪颗种子"由播种策略决定（顺序 / 随机 / 巨大化配比）
local function TakePayload(inst)
	local att = inst._attachment_type
	local store = inst.components.aom_attachment_store
	if att == AOM.TYPE.PLOW then
		return { terraformer = AOMFarmWork.GetTerraformer(inst) }, true
	elseif att == AOM.TYPE.SEEDER then
		local strategy = inst._seed_strategy or "SEQUENTIAL"
		local item

		if strategy == "RANDOM" then
			item = AOMSeed.PickRandom(store:ListSeeds())
			if item ~= nil then
				item = store:_SplitOne(store:_GetMaterialContainer(), item)
			end
        elseif strategy == "GIANT" then
            -- 配比模式由 WorkHere 的坐标分支处理，禁止回退到任意种子。
            return {}, false
		else
			item = store:TakeSeeds()
		end

		return { seed = item }, item ~= nil
	end
	return {}, true
end

-- 把没消耗掉的物料退回仓里（只在作业失败时调用）
local function ReturnPayload(inst, att, payload)
	local store = inst.components.aom_attachment_store
	if att == AOM.TYPE.SEEDER and payload.seed ~= nil and payload.seed:IsValid() then
		store:ReturnSeed(payload.seed)
	end
end

local PLAN_MESSAGES = {
    MISSING_SEEDS="种子不足，请补齐整套配比所需种子",
    NEED_PLOW="请换开垦机，准备好全部计划地块的坑位",
    NEXT_TILE="本格已完成，请驾驶到相邻的计划地块",
    COMPLETE="本轮配比已完成，保留空位，等待作物成熟",
    FOREIGN_CROP="计划区域已有其他作物或杂草，请先清理",
    PLANT_MISSING="计划中的作物缺失，请检查地块并重新规划",
    SEASON_CHANGED="季节已变化，请检查作物并重新选择播种策略",
    INVALID_LAND="计划区域无法耕种，请换一片连续空地",
    FAILED="播种失败，种子已退回，计划进度保持不变",
    LOW_NUTRIENTS="初始养分不足，请先给计划地块补肥",
    BLOCKED_MOUND="计划坑位被占用，请清理后重新作业",
    NO_FAMILY="实际坑位不满足同类距离，请换开垦机整理坑位",
}
local function SetPlanMessage(inst,reason)
    local text=reason and (PLAN_MESSAGES[reason] or "当前布局无法通过作物条件检查") or ""
    if inst._workreason_net then inst._workreason_net:set(text) end
    if inst._planprogress_net then inst._planprogress_net:set(AOMBlock.DescribeProgress(inst)) end
    if reason and reason~="NEXT_TILE" then
        AOMDrive.SetWorking(inst,false)
        if inst._last_plan_reason~=reason and inst._rider and inst._rider.components.talker then
            inst._rider.components.talker:Say(text)
        end
    end
    inst._last_plan_reason=reason
end
local function GiantWorkHere(inst,cx,y,cz)
    local store=inst.components.aom_attachment_store
    local preparing=inst._attachment_type==AOM.TYPE.PLOW
    local counts=store:CountSeedsByCrop(AOMSeed.GetCropOfSeedItem)
    local targets,reason=AOMBlock.GetTargets(inst,TheWorld.state.season,counts,cx,cz,preparing)
    if not targets then SetPlanMessage(inst,reason);return false,reason,false end
    if preparing then
        local changed,why,ready=AOMFarmWork.Plough(cx,y,cz,inst._rider,AOMFarmWork.GetTerraformer(inst),targets,inst)
        if not ready then SetPlanMessage(inst,why)
        elseif changed then SetPlanMessage(inst,nil)
        else SetPlanMessage(inst,"NEXT_TILE") end
        return changed,why,ready
    end
    local target=targets[1]
    local item=store:TakeSeedOfCrop(target.crop,AOMSeed.GetCropOfSeedItem)
    if not item then SetPlanMessage(inst,"MISSING_SEEDS");return false,"MISSING_SEEDS" end
    local ok=AOMFarmWork.SeedAt(target,inst._rider,item)
    if not ok then
        if item:IsValid() then store:ReturnSeed(item) end
        SetPlanMessage(inst,"FAILED")
        return false,"FAILED"
    end
    -- 种子在 Plant 内会被 Remove，所以作物类型使用预先选定的 target；只在成功后提交。
    AOMBlock.RecordPlanted(inst,target)
    SetPlanMessage(inst,nil)
    return true
end

-- 在当前所在地皮上作业一次。整格工序返回 reason / ready，区分改动与完整完成。
function AOMDrive.WorkHere(inst, workx, workz)
	local att = inst._attachment_type
	if att == nil then
		return false, "NO_ATTACHMENT"
	end

	local driver = inst._rider
	local source=driver or inst
	local x, y, z = source.Transform:GetWorldPosition()
	if workx~=nil then x,y,z=workx,0,workz end
	local cx, _, cz = AOMFarmWork.GetTileCenter(x, y, z)

    local worked,work_reason,ready
    local coordinate_mode=inst._seed_strategy=="GIANT" and (att==AOM.TYPE.SEEDER or att==AOM.TYPE.PLOW)
    if att==AOM.TYPE.PLOW then
        local usable,reason=LandClearer.CanWork(inst)
        if not usable then return false,reason,false end
        if coordinate_mode then worked,work_reason,ready=GiantWorkHere(inst,cx,y,cz)
        else worked,work_reason,ready=AOMFarmWork.Plough(cx,y,cz,driver,AOMFarmWork.GetTerraformer(inst),nil,inst) end
    elseif att==AOM.TYPE.WEEDER then
        local usable,reason=Weeder.CanWork(inst)
        if not usable then return false,reason,false end
        worked,work_reason,ready=AOMFarmWork.Weed(cx,y,cz,driver)
    elseif att==AOM.TYPE.IRRIGATOR then
        worked,work_reason,ready=Irrigator.WaterTile(inst,cx,cz)
    elseif att==AOM.TYPE.FERTILIZER then
        worked,work_reason,ready=Fertilizer.WorkTile(inst,cx,cz)
    elseif coordinate_mode then
        local reason
        worked,reason=GiantWorkHere(inst,cx,y,cz)
        if not worked then return false,reason end
    else
        if not AOMFarmWork.CanWorkAt(att,cx,y,cz) then return false,"NOTHING_TO_DO" end
        local payload,ok=TakePayload(inst)
        if not ok then return false,"EMPTY" end
        worked=AOMFarmWork.DoWork(att,cx,y,cz,driver,payload)
        if not worked then ReturnPayload(inst,att,payload);return false,"FAILED" end
    end

	if worked then
		inst.components.finiteuses:Use(1)
		if att==AOM.TYPE.PLOW then LandClearer.Use(inst) end
		if att==AOM.TYPE.WEEDER then Weeder.Use(inst) end
		if inst.AnimState:IsCurrentAnimation("idle") then
			inst.AnimState:PlayAnimation("work")
			inst.AnimState:PushAnimation("idle", true)
		end
	end
	if att==AOM.TYPE.PLOW or att==AOM.TYPE.WEEDER or att==AOM.TYPE.IRRIGATOR or att==AOM.TYPE.FERTILIZER then return worked,work_reason,ready end
	return worked
end

---------------------------------------------------------------------------
-- 行驶经过一格就完成本格工序。洒水、施肥按整格结算，播种按逐颗动作结算。
---------------------------------------------------------------------------

local WORK_MESSAGES={
    NO_FUEL="燃料不足，请加油后按 F 继续作业",
    FAILED="本格作业未完成，请检查地块后按 F 重试",
    NO_ATTACHMENT="请先安装挂件",
    BROKEN_ATTACHMENT="开垦机耐久已耗尽，请下车用燧石修理后按 F 继续",
    BROKEN_WEEDER="除草机耐久已耗尽，请下车用燧石修理后按 F 继续",
    UNCLEARABLE_WEED="本格有无法用铲子清理的杂草或残渣，已暂停除草",
    WEEDING_INCOMPLETE="本格除草尚未完成，已保留实际进度，请检查后按 F 重试",
    PROTECTED_CROP="本格有作物，已保留原状；收获后再开垦",
    BLOCKED_MOUND="地块或坑位被占用，本格未完成，请清理后按 F 重试",
    UNCLEARABLE_DEBRIS="本格有无法用铲子清理的杂物，已停止开垦",
    CLEARING_INCOMPLETE="杂物尚未清理干净，保留坑位并停止开垦",
    CANNOT_PLOW="这块地无法铺成农田，请换可开垦地块",
    NO_WORKER="需要驾驶员执行杂物铲除",
    MOISTURE_UNAVAILABLE="无法读取原版土壤水分，已暂停洒水，请检查版本兼容",
    NUTRIENTS_UNAVAILABLE="无法读取原版农田养分，已暂停施肥",
    FERTILIZER_FAILED="本格施肥未完成，已保留实际进度，请检查后按 F 重试",
    WATER_FAILED="本格补水未能完成，已保留实际浇水进度，请检查后按 F 重试",
}
local EMPTY_MESSAGES={seeder="种子不足，请补充后按 F 继续作业",
    irrigator="水箱已空，请补水后按 F 继续作业",
    fertilizer="肥料不足，请补充后按 F 继续作业"}
local function StopForReason(inst,reason)
    if inst._workreason_net then
        inst._workreason_net:set(reason=="FERTILIZER_MISSING" and inst._fertilizer_missing_text
            or reason=="EMPTY" and EMPTY_MESSAGES[inst._attachment_type]
            or WORK_MESSAGES[reason] or PLAN_MESSAGES[reason] or "本格作业暂停，请检查面板提示")
    end
    AOMDrive.SetWorking(inst,false)
end

function AOMDrive.WorkTile(inst,cx,cz)
    local worked_any=false
    local limit=inst._attachment_type==AOM.TYPE.SEEDER and 10 or 1
    for _=1,limit do
        if inst._attachment_type~=AOM.TYPE.IRRIGATOR and inst._attachment_type~=AOM.TYPE.FERTILIZER and GetFuel(inst)<AOM.FUEL_PER_TICK then StopForReason(inst,"NO_FUEL");return worked_any,"NO_FUEL" end
        local worked,reason,ready=AOMDrive.WorkHere(inst,cx,cz)
        if not worked then
            if ready==false or reason=="EMPTY" or reason=="FAILED" or reason=="NO_ATTACHMENT" then StopForReason(inst,reason) end
            return worked_any,reason
        end
        worked_any=true
        ConsumeFuel(inst,AOM.FUEL_PER_TICK)
        if ready==false then StopForReason(inst,reason);return true,reason end
        if inst._attachment_type==AOM.TYPE.IRRIGATOR and inst.components.aom_attachment_store:GetWater()==0 then
            StopForReason(inst,"EMPTY");return true,"EMPTY"
        end
        if inst._attachment_type==AOM.TYPE.PLOW and not LandClearer.CanWork(inst) then
            StopForReason(inst,"BROKEN_ATTACHMENT");return true,"BROKEN_ATTACHMENT"
        end
        if inst._attachment_type==AOM.TYPE.WEEDER and not Weeder.CanWork(inst) then
            StopForReason(inst,"BROKEN_WEEDER");return true,"BROKEN_WEEDER"
        end
        if GetFuel(inst)<AOM.FUEL_PER_TICK then StopForReason(inst,"NO_FUEL");return worked_any,"NO_FUEL" end
    end
    return worked_any
end

local function WorkPosition(inst)
    return (inst._rider or inst).Transform:GetWorldPosition()
end

function AOMDrive.TrackMovement(inst)
    if not inst._working or not inst._rider then AOMDrive.SetWorking(inst,false);return end
    local x,_,z=WorkPosition(inst)
    local ox,oz=inst._last_work_x or x,inst._last_work_z or z
    local moved=(x-ox)^2+(z-oz)^2>.0001
    local tiles=Profile.TraceTiles(TheWorld.Map,ox,oz,x,z)
    inst._last_work_x,inst._last_work_z=x,z
    for _,p in ipairs(tiles) do
        local key=p.x..":"..p.z
        if key~=inst._last_work_tile then
            inst._last_work_tile=key
            local worked=AOMDrive.WorkTile(inst,p.x,p.z)
            inst._plough_loaded=inst._attachment_type==AOM.TYPE.PLOW and worked
            if not inst._working then return end
        end
    end
    if moved and inst._plough_loaded and inst._attachment_type==AOM.TYPE.PLOW then
        inst._smoke_elapsed=(inst._smoke_elapsed or 0)+Profile.SAMPLE_INTERVAL
        if inst._smoke_elapsed>=.3 then
            inst._smoke_elapsed=0
            local puff=SpawnPrefab("aom_exhaust_puff")
            if puff then
                local angle=inst._rider.Transform:GetRotation()*math.pi/180
                puff.Transform:SetPosition(x+.45*math.cos(angle),1.4,z-.45*math.sin(angle))
            end
        end
    else inst._smoke_elapsed=0 end
end

function AOMDrive.SetWorking(inst, on)
    inst._working=on and true or false
    inst._workstatus:set(inst._working)
    if inst._worktask then inst._worktask:Cancel();inst._worktask=nil end
    inst._last_work_x,inst._last_work_z=nil,nil
    inst._last_work_tile=nil
    inst._plough_loaded=false
    inst._smoke_elapsed=0
    AOMDrive.UpdateSpeed(inst)
    if not inst._working then return end
    if inst._workreason_net then inst._workreason_net:set("") end
    local x,_,z=WorkPosition(inst)
    inst._last_work_x,inst._last_work_z=x,z
    inst._worktask=inst:DoPeriodicTask(Profile.SAMPLE_INTERVAL,AOMDrive.TrackMovement)
end

-- 播种策略循环切换：顺序 -> 随机 -> 巨大化配比 -> 顺序
local STRATEGY_ORDER = { "SEQUENTIAL", "RANDOM", "GIANT" }
local STRATEGY_NAME = {
	SEQUENTIAL = "顺序播种",
	RANDOM = "随机播种",
	GIANT = "巨大化配比",
}

function AOMDrive.GetSeedStrategyName(inst)
	return STRATEGY_NAME[inst._seed_strategy or "SEQUENTIAL"] or "顺序播种"
end

function AOMDrive.CycleSeedStrategy(inst, doer)
	if inst._attachment_type ~= AOM.TYPE.SEEDER then
		return false
	end
	AOMDrive.SetWorking(inst,false)
	local cur = inst._seed_strategy or "SEQUENTIAL"
	local idx = 1
	for i, v in ipairs(STRATEGY_ORDER) do
		if v == cur then idx = i end
	end
	idx = idx % #STRATEGY_ORDER + 1
	inst._seed_strategy = STRATEGY_ORDER[idx]
	AOMBlock.ResetBlock(inst)
    SetPlanMessage(inst,nil)
	-- 同步给客户端 HUD
	if inst._seedmode_net ~= nil then
		inst._seedmode_net:set(inst._seed_strategy)
	end
	if doer ~= nil and doer.components.talker ~= nil then
		doer.components.talker:Say("播种策略：" .. STRATEGY_NAME[inst._seed_strategy])
	end
	return true
end

function AOMDrive.ToggleWorking(inst, doer)
	local rider = doer ~= nil and doer.components.rider or nil
	if rider == nil or not rider:IsRiding() or rider:GetMount() ~= inst then
		return false
	end
	if not AOMDrive.HasAttachment(inst) then
		if doer ~= nil and doer.components.talker ~= nil then
			doer.components.talker:Say(AOM.STATUS.MISSING_ATTACHMENT)
		end
		return false
	end
	AOMDrive.SetWorking(inst, not inst._working)
	return true
end

---------------------------------------------------------------------------
-- 骑乘：进入/离开驾驶座
---------------------------------------------------------------------------

-- 仅供死亡等清理流程请求下车；正常交互由原版 DISMOUNT 执行。
function AOMDrive.Dismount(inst, doer)
	if doer == nil or doer.components.rider == nil then
		return false
	end
	if not doer.components.rider:IsRiding() then
		return false
	end
	if doer.components.rider:GetMount() ~= inst then
		return false
	end
	AOMDrive.SetWorking(inst, false)
	doer.components.rider:Dismount()
	return true
end

-- 被骑上/被放下时由 rideable 事件驱动
function AOMDrive.OnMounted(inst, data)
	local rider = data and data.rider or (inst.components.rideable and inst.components.rideable:GetRider())
	inst._rider = rider
	inst._rider_net:set(rider)
	AOMDrive.SetWorking(inst,false)
	inst._stop_driver_work=function()AOMDrive.SetWorking(inst,false)end
	if rider then
		inst:ListenForEvent("dismount",inst._stop_driver_work,rider)
		inst:ListenForEvent("death",inst._stop_driver_work,rider)
	end
end

function AOMDrive.OnDismounted(inst)
	if inst._rider and inst._stop_driver_work then
		inst:RemoveEventCallback("dismount",inst._stop_driver_work,inst._rider)
		inst:RemoveEventCallback("death",inst._stop_driver_work,inst._rider)
	end
	inst._stop_driver_work=nil
	inst._rider = nil
	inst._rider_net:set(nil)
	AOMDrive.SetWorking(inst, false)
end

return AOMDrive
