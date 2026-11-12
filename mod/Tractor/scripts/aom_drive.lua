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
local Profile = require("aom_work_profile")
local Irrigator = require("aom_irrigator")
local Fertilizer = require("aom_fertilizer")
local AttachmentAnimation = require("aom_attachment_animation")
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
	local fuel = math.max(0, v)
	inst._fuel:set(fuel)
	if inst.components.rideable ~= nil then
		-- 原版 MOUNT.fn 检查 canride；它的 setter 同步 rideable 标签。
		inst.components.rideable.canride = fuel>0 and not inst._destroyed
            and not (inst.components.health and inst.components.health:IsDead())
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

local function SetPlanMessage(inst,reason)
    AOMBlock.Sync(inst)
    Status.Set(inst,reason)
    if inst._planprogress_net then inst._planprogress_net:set(AOMBlock.DescribeProgress(inst)) end
    if reason and reason~="NEXT_TILE" then
        StopForReason(inst,reason)
    end
end
local function GiantWorkHere(inst,cx,y,cz)
    local store=inst.components.aom_attachment_store
    local preparing=inst._attachment_type==AOM.TYPE.PLOW
    local counts=store:CountSeedsByCrop(AOMSeed.GetCropOfSeedItem)
    local targets,reason=AOMBlock.GetTargets(inst,TheWorld.state.season,counts,cx,cz,preparing)
    if not targets then SetPlanMessage(inst,reason);return false,reason,reason=="NEXT_TILE" end
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
    return true,nil,nil,{x=target.x,z=target.z}
end

-- 在当前所在地皮上作业一次。整格工序返回 reason / ready，区分改动与完整完成。
local function PerformWork(inst, workx, workz)
	inst._aom_broken_attachment_reason=nil
	if inst._destroyed or (inst.components.health and inst.components.health:IsDead()) then return false,"DESTROYED",false end
	if inst.components.finiteuses:GetUses()<=0 then return false,"BROKEN_CHASSIS",false end
	local att = inst._attachment_type
	if att == nil then
		return false, "NO_ATTACHMENT"
	end
    local usable,reason=Durability.CanWork(inst)
    if not usable then return false,reason,false end

	local driver = inst._rider
	local source=driver or inst
	local x, y, z = source.Transform:GetWorldPosition()
	if workx~=nil then x,y,z=workx,0,workz end
	local cx, _, cz = AOMFarmWork.GetTileCenter(x, y, z)

    local worked,work_reason,ready,fxposition
    local coordinate_mode=inst._seed_strategy=="GIANT" and (att==AOM.TYPE.SEEDER or att==AOM.TYPE.PLOW)
    if att==AOM.TYPE.PLOW then
        if coordinate_mode then worked,work_reason,ready=GiantWorkHere(inst,cx,y,cz)
        else worked,work_reason,ready=AOMFarmWork.Plough(cx,y,cz,driver,AOMFarmWork.GetTerraformer(inst),nil,inst) end
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
        if not worked then return false,reason,reason=="NEXT_TILE" end
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

-- 对外保留tuple接口；内部统一结果对象，异常也经过同一次实际进度结算。
function AOMDrive.WorkHere(inst,workx,workz)
    local item=require("aom_attachment_mount").Get(inst)
    local had_noblock=inst.HasTag and inst:HasTag("NOBLOCK")
    local result=Result.Run(inst,function()return PerformWork(inst,workx,workz)end)
    -- 原版/第三方回调异常也不能留下临时碰撞标签。
    Result.Protect(result,function()
        if not had_noblock and inst.RemoveTag then inst:RemoveTag("NOBLOCK") end
    end)
    if result.changed then
        Result.Protect(result,function()inst.components.finiteuses:Use(1)end)
        Result.Protect(result,function()Durability.UseAttachment(inst,item)end)
        Result.Protect(result,function()AttachmentAnimation.Success(inst,result.position)end)
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
    return result.changed,result.reason,result.complete
end

---------------------------------------------------------------------------
-- 行驶经过一格就完成本格工序。洒水、施肥按整格结算，播种按逐颗动作结算。
---------------------------------------------------------------------------

StopForReason=function(inst,reason,message)
    local code=message and "DETACH_BLOCKED" or reason
    local detail=reason=="EMPTY" and inst._attachment_type
        or reason=="FERTILIZER_MISSING" and inst._fertilizer_missing_channels or ""
    local announce=inst._working or Status.Read(inst)~=code
    local text=Status.Set(inst,code,detail)
    AOMDrive.SetWorking(inst,false)
    local talker=inst._rider and inst._rider.components.talker
    if talker and announce then talker:Say(text) end
end
AOMDrive.StopForReason=StopForReason

-- 开始、每次采样和每次成功消耗后检查，最后一份刚好完成本格也立即停工。
-- 开垦、除草和收割不需要种子/水/肥料，沿用各自耐久与燃料检查。
local MATERIAL_READERS={seeds="GetSeedCount",water="GetWater",fertilizer="GetFertilizerCount"}
local function HasMaterials(inst)
    local def=require("aom_equipment_defs")[inst._attachment_type]
    local method=def and MATERIAL_READERS[def.material]
    local store=inst.components.aom_attachment_store
    return not method or store and store[method](store)>0
end

function AOMDrive.WorkTile(inst,cx,cz)
    if not HasMaterials(inst) then StopForReason(inst,"EMPTY");return false,"EMPTY" end
    local worked_any=false
    local limit=inst._attachment_type==AOM.TYPE.SEEDER and 10 or 1
    for _=1,limit do
        if inst._attachment_type~=AOM.TYPE.IRRIGATOR and inst._attachment_type~=AOM.TYPE.FERTILIZER and GetFuel(inst)<AOM.FUEL_PER_TICK then StopForReason(inst,"NO_FUEL");return worked_any,"NO_FUEL" end
        local worked,reason,ready=AOMDrive.WorkHere(inst,cx,cz)
        local broken=inst._aom_broken_attachment_reason
        inst._aom_broken_attachment_reason=nil
        if reason=="WORK_ERROR" then
            if worked then ConsumeFuel(inst,AOM.FUEL_PER_TICK) end
            StopForReason(inst,reason)
            return worked_any or worked,reason
        end
        if broken then
            if worked then ConsumeFuel(inst,AOM.FUEL_PER_TICK) end
            return worked_any or worked,broken
        end
        if not worked then
            if ready==false or reason=="EMPTY" or reason=="FAILED" or reason=="NO_ATTACHMENT" then StopForReason(inst,reason) end
            return worked_any,reason
        end
        worked_any=true
        ConsumeFuel(inst,AOM.FUEL_PER_TICK)
        if ready==false then StopForReason(inst,reason);return true,reason end
        if inst.components.finiteuses:GetUses()<=0 then
            StopForReason(inst,"BROKEN_CHASSIS");return true,"BROKEN_CHASSIS"
        end
        local usable,broken_reason=Durability.CanWork(inst)
        if not usable then StopForReason(inst,broken_reason);return true,broken_reason end
        if not HasMaterials(inst) then
            StopForReason(inst,"EMPTY");return true,"EMPTY"
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
    if not HasMaterials(inst) then StopForReason(inst,"EMPTY");return end
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
    -- 停工状态/采样任务先提交，展示回调失败不能让停机向外抛错。
    local ok,err=pcall(AttachmentAnimation.SetWorking,inst,inst._working)
    if not ok then
        inst._aom_last_presentation_error=tostring(err)
        if print then print("[Tractor] Work animation failed: "..tostring(err)) end
    end
    inst:PushEvent("aom_work_changed")
    if not inst._working then return end
    Status.Set(inst,nil)
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
	return L(STRATEGY_NAME[inst._seed_strategy or "SEQUENTIAL"] or "顺序播种")
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
		doer.components.talker:Say(L("播种策略：%s",AOMDrive.GetSeedStrategyName(inst)))
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
	if not inst._working and inst._seed_strategy=="GIANT"
        and (inst._attachment_type==AOM.TYPE.SEEDER or inst._attachment_type==AOM.TYPE.PLOW) then
        if not inst._block then
            local ok,reason=AOMBlock.Preview(inst)
            SetPlanMessage(inst,ok and "PLAN_PENDING" or reason)
            return false
        elseif inst._block.confirmed==false then
            SetPlanMessage(inst,"PLAN_PENDING");return false
        end
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
	local rider = data and data.rider or (inst.components.rideable and inst.components.rideable:GetRider())
	inst._rider = rider
	inst._rider_net:set(rider)
	AOMDrive.SetWorking(inst,false)
	inst._stop_driver_work=function()
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
	if inst.components.container and inst.components.container.Close and inst._rider then
		inst.components.container:Close(inst._rider)
	end
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
