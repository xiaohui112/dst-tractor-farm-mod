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
local L = require("aom_locale").Text

local AOMDrive = {}
local AOMSeed = require("aom_seed_strategy")
local AOMBlock = require("aom_block_plan")
local AutoSeed = require("aom_auto_seeding")
local Profile = require("aom_work_profile")
local Irrigator = require("aom_irrigator")
local Fertilizer = require("aom_fertilizer")
local AttachmentAnimation = require("aom_attachment_animation")
local Mount = require("aom_attachment_mount")
local Status=require("aom_work_status")
local Result=require("aom_work_result")
local Durability=require("aom_durability")
local StopForReason

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
	local previous = GetFuel(inst)
	local fuel = math.max(0, v)
	inst._fuel:set(fuel)
	if inst.components.rideable ~= nil then
		-- 原版 MOUNT.fn 检查 canride；它的 setter 同步 rideable 标签。
		inst.components.rideable.canride = fuel>0 and not inst._destroyed
            and not (inst.components.health and inst.components.health:IsDead())
	end
	if (previous > 0) ~= (fuel > 0) then
		AOMDrive.UpdateSpeed(inst)
		if fuel == 0 and inst._rider then
			local locomotor = inst._rider.components.locomotor
			if locomotor and locomotor.Stop then locomotor:Stop() end
			StopForReason(inst,"NO_FUEL")
		end
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
    local speed=GetFuel(inst)>0 and Profile.Speed(inst._working) or 0
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
-- 播种机的"取哪颗种子"由播种策略决定（顺序 / 巨大化）
local function TakePayload(inst)
	local att = inst._attachment_type
	local store = inst.components.aom_attachment_store
	if att == AOM.TYPE.PLOW then
		return { terraformer = AOMFarmWork.GetTerraformer(inst) }, true
	elseif att == AOM.TYPE.SEEDER then
		local strategy = inst._seed_strategy or "SEQUENTIAL"
		local item

        if AOMSeed.IsGiant(strategy) then
            -- 巨大化模式由坐标分支处理，禁止回退到任意种子。
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

local function SetPlanMessage(inst,reason,force)
    AOMBlock.Sync(inst)
    if inst._planprogress_net then inst._planprogress_net:set(AOMBlock.DescribeProgress(inst)) end
    if reason and reason~="NEXT_TILE" then
        StopForReason(inst,reason,nil,force)
    else Status.Report(inst,reason,nil,nil,force) end
end
local function GiantWorkHere(inst,cx,y,cz)
    local store=inst.components.aom_attachment_store
    local trace=inst._aom_plan_trace
    local measuring=trace and trace.awaiting_first and not trace.finished and not inst._aom_preview_plan
    if measuring then trace:RunBegin();trace:Stage("pre_sow_check")end
    local targets,reason=AutoSeed.GetTargets(inst,cx,cz)
    if not targets then
        if reason=='PLANNING' or reason=='PLAN_READY' then
            local planning=reason=='PLANNING' and inst._aom_plan_trace
            if planning then
                Status.Set(inst,reason);planning:Progress()
                if inst._planprogress_net then inst._planprogress_net:set(planning:Text())end
            else
                Status.Report(inst,reason)
                if inst._planprogress_net then inst._planprogress_net:set(Status.Text(reason))end
            end
            return false,reason,true
        end
        local idle=reason=="NEXT_TILE" or reason=="NOTHING_TO_DO" or reason=="PLANNING"
        if idle then SetPlanMessage(inst,nil) else SetPlanMessage(inst,reason) end
        if measuring then
            if not trace.finished then trace:Stage("await_sow_tile")end
            trace:RunEnd()
        end
        return false,reason,idle
    end
    local target=targets[1]
    if trace and trace.awaiting_first then trace:Stage("first_seed")end
    local item=store:TakeSeedOfCrop(target.crop,AOMSeed.GetCropOfSeedItem)
    if not item then SetPlanMessage(inst,"MISSING_SEEDS");return false,"MISSING_SEEDS" end
    -- 本格最后一个计划坑成功后才结算挂件耐久；模版留空不算待播坑。
    if inst._aom_work_result then inst._aom_work_result.seed_tile_complete=#targets==1 end
    local safe,ok=pcall(AOMFarmWork.SeedAt,target,inst._rider,item,inst)
    if not safe or not ok then
        if item:IsValid() then store:ReturnSeed(item) end
        if not safe then error(ok,0) end
        SetPlanMessage(inst,"FAILED")
        return false,"FAILED"
    end
    -- 种子在 Plant 内会被 Remove，所以作物类型使用预先选定的 target；只在成功后提交。
    AOMBlock.RecordPlanted(inst,target)
    SetPlanMessage(inst,nil)
    if trace and trace.awaiting_first then trace:FirstSeed(target)end
    if measuring then trace:RunEnd()end
    return true,nil,nil,{x=target.x,z=target.z}
end

-- 在当前所在地皮上作业一次。整格工序返回 reason / ready，区分改动与完整完成。
local function PerformWork(inst,cx,y,cz,seed_paid)
	inst._aom_broken_attachment_reason=nil
	if inst._destroyed or (inst.components.health and inst.components.health:IsDead()) then return false,"DESTROYED",false end
	if not seed_paid and inst.components.finiteuses:GetUses()<=0 then return false,"BROKEN_CHASSIS",false end
	local att = inst._attachment_type
	if att == nil then
		return false, "NO_ATTACHMENT"
	end
    local usable,reason=Durability.CanWork(inst)
    if not usable then return false,reason,false end
    if att~=AOM.TYPE.IRRIGATOR and att~=AOM.TYPE.FERTILIZER then
        local fuel=GetFuel(inst)
        if fuel<=0 or not seed_paid and fuel<AOM.FUEL_PER_TICK then return false,"NO_FUEL",false end
    end

	local driver = inst._rider

    local worked,work_reason,ready,fxposition
    local coordinate_mode=AOMSeed.IsGiant(inst._seed_strategy) and att==AOM.TYPE.SEEDER
    if att==AOM.TYPE.PLOW then
        worked,work_reason,ready=AOMFarmWork.Plough(cx,y,cz,driver,AOMFarmWork.GetTerraformer(inst),nil,inst)
        if ready then require("aom_farm_registry").Record(TheWorld,cx,cz) end
    elseif att==AOM.TYPE.WEEDER then
        worked,work_reason,ready=AOMFarmWork.Weed(cx,y,cz,driver,inst)
    elseif att==AOM.TYPE.HARVESTER then
        worked,work_reason,ready=AOMFarmWork.Harvest(cx,y,cz,driver,inst)
    elseif att==AOM.TYPE.IRRIGATOR then
        worked,work_reason,ready=Irrigator.WaterTile(inst,cx,cz)
    elseif att==AOM.TYPE.FERTILIZER then
        worked,work_reason,ready=Fertilizer.WorkTile(inst,cx,cz)
    elseif coordinate_mode then
        local reason
        worked,reason,ready,fxposition=GiantWorkHere(inst,cx,y,cz)
        if not worked then return false,reason,ready end
    else
        if not AOMFarmWork.CanWorkAt(att,cx,y,cz) then return false,"NOTHING_TO_DO" end
        local payload,ok=TakePayload(inst)
        if not ok then return false,"EMPTY" end
        local why
        payload.vehicle=inst
        local ok
        ok,worked,why,fxposition=pcall(AOMFarmWork.DoWork,att,cx,y,cz,driver,payload)
        if not ok or not worked then ReturnPayload(inst,att,payload) end
        if not ok then error(worked,0) end
        if not worked then return false,"FAILED",false end
    end

    return worked,work_reason,ready,fxposition
end

-- 异常也经过同一次实际进度结算。
local function WorkHere(inst,workx,workz,contact_x,contact_z)
    local item=Mount.Get(inst)
    local seeding=inst._attachment_type==AOM.TYPE.SEEDER
    local cx,y,cz,seed_paid
    local had_noblock=inst.HasTag and inst:HasTag("NOBLOCK")
    local result=Result.Run(inst,function()
        local x,z=workx,workz
        y=0
        if x==nil then x,y,z=Mount.WorkPosition(inst) end
        contact_x,contact_z=contact_x or x,contact_z or z
        cx,y,cz=AOMFarmWork.GetTileCenter(x,y,z)
        seed_paid=seeding and AOMFarmWork.SeedTilePaid(cx,y,cz)
        return PerformWork(inst,cx,y,cz,seed_paid)
    end)
    -- 原版/第三方回调异常也不能留下临时碰撞标签。
    Result.Protect(result,function()
        if not had_noblock and inst.RemoveTag then inst:RemoveTag("NOBLOCK") end
    end)
    if result.changed then
        if seeding then Result.Protect(result,function()AOMFarmWork.MarkSeedTilePaid(cx,y,cz)end) end
        if not seed_paid then
            Result.Protect(result,function()inst.components.finiteuses:Use(1)end)
            Result.Protect(result,function()ConsumeFuel(inst,AOM.FUEL_PER_TICK)end)
        end
        if item and (item.attachment_type~="seeder" or result.seed_tile_complete) then
            Result.Protect(result,function()Durability.UseAttachment(inst,item)end)
        end
        Result.Protect(result,function()
            AttachmentAnimation.Success(inst,result.position,contact_x,contact_z,cx,cz)
        end)
        Result.Protect(result,function()
            if inst.AnimState:IsCurrentAnimation("idle") then
                inst.AnimState:PlayAnimation("work");inst.AnimState:PushAnimation("idle",true)
            end
        end)
    end
    if result.error then
        inst._aom_last_work_error=result.error
        if print then print("[Tractor] Work failed: "..result.error) end
    end
    return result
end

function AOMDrive.WorkHere(inst,workx,workz)
    local result=WorkHere(inst,workx,workz)
    return result.changed,result.reason,result.complete
end

---------------------------------------------------------------------------
-- 行驶经过一格就完成本格工序，播种逐颗执行、按地皮结算。
---------------------------------------------------------------------------

StopForReason=function(inst,reason,message,force)
    if reason=="EMPTY" and inst._attachment_type==AOM.TYPE.SEEDER and AOMSeed.IsGiant(inst._seed_strategy) then
        reason="MISSING_SEEDS"
    end
    local code=message and "DETACH_BLOCKED" or reason
    local detail=reason=="EMPTY" and inst._attachment_type
        or reason=="FERTILIZER_MISSING" and inst._fertilizer_missing_channels or ""
    local active=inst._working
    AOMDrive.SetWorking(inst,false,reason)
    Status.Report(inst,code,detail,nil,force or active)
end
AOMDrive.StopForReason=StopForReason

-- 开始、每次采样和每次成功消耗后检查，最后一份刚好完成本格也立即停工。
-- 开垦、除草和收割不需要种子/水/肥料，沿用各自耐久与燃料检查。
local MATERIAL_READERS={seeds="GetSeedCount",water="GetWater"}
local function HasMaterials(inst)
    if inst._attachment_type==AOM.TYPE.FERTILIZER then return Fertilizer.HasMaterials(inst) end
    local def=require("aom_equipment_defs")[inst._attachment_type]
    local method=def and MATERIAL_READERS[def.material]
    local store=inst.components.aom_attachment_store
    return not method or store and store[method](store)>0
end

function AOMDrive.WorkTile(inst,cx,cz,contact_x,contact_z)
    if not HasMaterials(inst) then StopForReason(inst,"EMPTY");return false,"EMPTY" end
    local worked_any=false
    local limit=inst._attachment_type==AOM.TYPE.SEEDER and 10 or 1
    for _=1,limit do
        local result=WorkHere(inst,cx,cz,contact_x,contact_z)
        local worked,reason,ready=result.changed,result.reason,result.complete
        local seed_pending=inst._attachment_type==AOM.TYPE.SEEDER and not result.seed_tile_complete
        local skip=inst._attachment_type==AOM.TYPE.PLOW and AOMFarmWork.IsPloughSkip(reason)
        local broken=inst._aom_broken_attachment_reason
        inst._aom_broken_attachment_reason=nil
        if reason=="WORK_ERROR" then
            StopForReason(inst,reason)
            return worked_any or worked,reason
        end
        if broken then
            return worked_any or worked,broken
        end
        if not worked then
            if not skip and (ready==false or reason=="EMPTY" or reason=="FAILED" or reason=="NO_ATTACHMENT") then StopForReason(inst,reason) end
            return worked_any,reason
        end
        worked_any=true
        if ready==false and not skip then StopForReason(inst,reason);return true,reason end
        if inst.components.finiteuses:GetUses()<=0 and not seed_pending then
            StopForReason(inst,"BROKEN_CHASSIS");return true,"BROKEN_CHASSIS"
        end
        local usable,broken_reason=Durability.CanWork(inst)
        if not usable then StopForReason(inst,broken_reason);return true,broken_reason end
        if not HasMaterials(inst) then
            StopForReason(inst,"EMPTY");return true,"EMPTY"
        end
        local fuel=GetFuel(inst)
        if fuel<=0 or not seed_pending and fuel<AOM.FUEL_PER_TICK then
            StopForReason(inst,"NO_FUEL");return worked_any,"NO_FUEL"
        end
        if skip then return true,reason end
    end
    return worked_any
end

local function TravelPosition(inst)
    return (inst._rider or inst).Transform:GetWorldPosition()
end

-- 独立于F作业任务：空驶、无挂件、缺料停工仍耗油；停在原地不扣。
-- 仅主模拟端的骑乘事件创建任务，按骑手位置计量（骑乘时车体是隐藏子实体）。
function AOMDrive.TrackTravel(inst)
    if not inst._rider then return end
    require("aom_dynamic_farm").PrepareNearby(inst)
    local x,_,z=TravelPosition(inst)
    AOMBlock.RefreshNearby(inst)
    local ox,oz=inst._last_drive_x or x,inst._last_drive_z or z
    inst._last_drive_x,inst._last_drive_z=x,z
    local distance=math.sqrt((x-ox)^2+(z-oz)^2)
    -- 传送只重置采样起点，不按瞬移的整段距离扣油。
    if distance>0 and distance<=Profile.MAX_SWEEP_DISTANCE and GetFuel(inst)>0 then
        AOMDrive.SetFuel(inst,GetFuel(inst)-distance*Profile.DRIVE_FUEL_PER_UNIT)
    end
end

local function StopTravel(inst)
    AOMDrive.TrackTravel(inst) -- 下车前结算最后不足一个采样周期的行程。
    if inst._drivetask then inst._drivetask:Cancel();inst._drivetask=nil end
    inst._last_drive_x,inst._last_drive_z=nil,nil
end

function AOMDrive.TrackMovement(inst)
    if not inst._working or not inst._rider then AOMDrive.SetWorking(inst,false);return end
    if not HasMaterials(inst) then StopForReason(inst,"EMPTY");return end
    local x,_,z,_,driver_x,driver_z=Mount.WorkPosition(inst)
    local ox,oz=inst._last_work_x or x,inst._last_work_z or z
    local old_driver_x=inst._last_work_driver_x or driver_x
    local old_driver_z=inst._last_work_driver_z or driver_z
    local travel_sq=(driver_x-old_driver_x)^2+(driver_z-old_driver_z)^2
    local moved=travel_sq>.0001
    -- 换朝向会把作业点切到另一侧。此时只处理目标格，避免扫过中间未作业的格。
    if math.abs((x-driver_x)-(ox-old_driver_x))>.01 or math.abs((z-driver_z)-(oz-old_driver_z))>.01
        or travel_sq>Profile.MAX_SWEEP_DISTANCE^2 then ox,oz=x,z end
    local tiles=Profile.TraceTiles(TheWorld.Map,ox,oz,x,z)
    inst._last_work_x,inst._last_work_z=x,z
    inst._last_work_driver_x,inst._last_work_driver_z=driver_x,driver_z
    for _,p in ipairs(tiles) do
        local key=p.x..":"..p.z
        if key~=inst._last_work_tile then
            inst._last_work_tile=key
            local worked=AOMDrive.WorkTile(inst,p.x,p.z,p.contact_x,p.contact_z)
            inst._plough_loaded=inst._attachment_type==AOM.TYPE.PLOW and worked
            if not inst._working then return end
        end
    end
    if moved then
        inst._smoke_elapsed=(inst._smoke_elapsed or 0)+Profile.SAMPLE_INTERVAL
        if inst._smoke_elapsed>=.3 then
            inst._smoke_elapsed=0
            require("aom_vehicle_motion").EmitExhaust(inst)
        end
    else inst._smoke_elapsed=0 end
end

function AOMDrive.SetWorking(inst, on, stop_reason)
    if on and inst._aom_pond_refill then return end
    inst._working=on and true or false
    inst._workstatus:set(inst._working)
    if inst._worktask then inst._worktask:Cancel();inst._worktask=nil end
    inst._last_work_x,inst._last_work_z=nil,nil
    inst._last_work_driver_x,inst._last_work_driver_z=nil,nil
    inst._last_work_tile=nil
    inst._plough_loaded=false
    inst._smoke_elapsed=0
    AOMDrive.UpdateSpeed(inst)
    -- 停工状态/采样任务先提交，展示回调失败不能让停机向外抛错。
    local ok,err=pcall(AttachmentAnimation.SetWorking,inst,inst._working)
    if not ok then
        inst._aom_last_presentation_error=tostring(err)
        if print then print("[Tractor] Work animation failed: "..tostring(err)) end
    end
    inst:PushEvent("aom_work_changed")
    if not inst._working then require('aom_dynamic_farm').Cancel(inst,stop_reason or 'WORK_STOPPED');inst._aom_plan_request=nil;return end
    if inst._attachment_type=='seeder' and AOMSeed.IsGiant(inst._seed_strategy)
        and (not inst._block or inst._block.dynamic and inst._block.done>=inst._block.total)then
        require('aom_plan_timing').Request(inst)
    end
    Status.Set(inst,nil)
    local x,_,z,_,driver_x,driver_z=Mount.WorkPosition(inst)
    inst._last_work_x,inst._last_work_z=x,z
    inst._last_work_driver_x,inst._last_work_driver_z=driver_x,driver_z
    inst._worktask=inst:DoPeriodicTask(Profile.SAMPLE_INTERVAL,AOMDrive.TrackMovement)
end

-- 播种策略循环切换：顺序 -> 巨大化·模版 -> 巨大化·最优 -> 顺序
local STRATEGY_NAME = {
	SEQUENTIAL = "顺序播种",
	GIANT_TEMPLATE = "巨大化·模版",
	GIANT = "巨大化·最优",
}

function AOMDrive.GetSeedStrategyName(inst)
	return L(STRATEGY_NAME[inst._seed_strategy or "SEQUENTIAL"] or "顺序播种")
end

function AOMDrive.CycleSeedStrategy(inst, doer)
	if inst._attachment_type ~= AOM.TYPE.SEEDER then
        require("aom_feedback").Say(doer,require("aom_feedback").Text("NEED_SEEDER"))
		return false
	end
	AOMDrive.SetWorking(inst,false)
	inst._seed_strategy = AOMSeed.Next(inst._seed_strategy)
	AOMBlock.ResetBlock(inst)
    SetPlanMessage(inst,nil)
	-- 同步给客户端 HUD
	if inst._seedmode_net ~= nil then
		inst._seedmode_net:set(inst._seed_strategy)
	end
	if doer ~= nil and doer.components.talker ~= nil then
		doer.components.talker:Say(L("播种策略：%s",AOMDrive.GetSeedStrategyName(inst)))
	end
	return true
end

function AOMDrive.CycleHarvestMode(inst,doer)
    local tool=require("aom_attachment_mount").Get(inst)
    if not tool or tool.attachment_type~=AOM.TYPE.HARVESTER then return false end
    AOMDrive.SetWorking(inst,false)
    inst._keep_oversized=not inst._keep_oversized
    inst._keep_oversized_net:set(inst._keep_oversized)
    require("aom_feedback").Say(doer,L("收割模式：%s",L(inst._keep_oversized and "保留巨大" or "全部收割")))
    return true
end

function AOMDrive.ToggleWorking(inst, doer)
	local rider = doer ~= nil and doer.components.rider or nil
	if rider == nil or not rider:IsRiding() or rider:GetMount() ~= inst then
		return false
	end
    if inst._aom_pond_refill then
        require("aom_feedback").Say(doer,require("aom_feedback").Text("REFILLING"))
        return false
    end
	if not AOMDrive.HasAttachment(inst) then
		if doer ~= nil and doer.components.talker ~= nil then
			doer.components.talker:Say(AOM.STATUS.MISSING_ATTACHMENT)
		end
		return false
	end
	AOMDrive.SetWorking(inst, not inst._working)
	-- 按 F 的当次就反馈空仓；不等待采样，也不要求先驶入可作业地块。
	if inst._working and not HasMaterials(inst) then
		StopForReason(inst,"EMPTY")
		return false
	end
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
	if inst.components.container and inst.components.container.Close then
		inst.components.container:Close(doer)
	end
	doer.components.rider:Dismount()
	return true
end

-- 被骑上/被放下时由 rideable 事件驱动
function AOMDrive.OnMounted(inst, data)
	StopTravel(inst)
	local rider = data and data.rider or (inst.components.rideable and inst.components.rideable:GetRider())
	inst._rider = rider
	inst._rider_net:set(rider)
	if rider then require("aom_driver_speech").Update(inst,rider) end
	if inst.GetAttachment then require("aom_attachment_mount").UpdateVisual(inst:GetAttachment()) end
	AOMDrive.SetWorking(inst,false)
	if rider then
		local x,_,z=TravelPosition(inst)
		inst._last_drive_x,inst._last_drive_z=x,z
		inst._drivetask=inst:DoPeriodicTask(Profile.SAMPLE_INTERVAL,AOMDrive.TrackTravel)
		-- riderchanged发生在原版将玩家移到驾驶座之前；mounted才是落座后的起点。
		inst._reset_driver_travel=function(_,event)
			if event and event.target==inst and inst._rider==rider then
				local sx,_,sz=TravelPosition(inst)
				inst._last_drive_x,inst._last_drive_z=sx,sz
			end
		end
		inst:ListenForEvent("mounted",inst._reset_driver_travel,rider)
	end
	inst._stop_driver_work=function()
        -- 下车请求可能被打断；真正脱离骑乘前仍保留行驶计费。
        AOMDrive.TrackTravel(inst)
        AOMDrive.SetWorking(inst,false)
        local container=inst.components.container
        if container and rider and container:IsOpenedBy(rider) then
            container:Close(rider)
            rider:PushEvent("closecontainer",{container=inst})
        end
    end
	if rider then
		inst:ListenForEvent("dismount",inst._stop_driver_work,rider)
		inst:ListenForEvent("death",inst._stop_driver_work,rider)
	end
end

function AOMDrive.OnDismounted(inst)
    StopTravel(inst)
    require("aom_pond_refill").Cancel(inst,true)
	if inst.components.container and inst.components.container.Close and inst._rider then
		inst.components.container:Close(inst._rider)
	end
	if inst._rider and inst._stop_driver_work then
		inst:RemoveEventCallback("dismount",inst._stop_driver_work,inst._rider)
		inst:RemoveEventCallback("death",inst._stop_driver_work,inst._rider)
	end
	if inst._rider and inst._reset_driver_travel then
		inst:RemoveEventCallback("mounted",inst._reset_driver_travel,inst._rider)
	end
	inst._reset_driver_travel=nil
	inst._stop_driver_work=nil
	inst._rider = nil
	inst._rider_net:set(nil)
	if inst.GetAttachment then require("aom_attachment_mount").UpdateVisual(inst:GetAttachment()) end
	AOMDrive.SetWorking(inst, false)
end

return AOMDrive
