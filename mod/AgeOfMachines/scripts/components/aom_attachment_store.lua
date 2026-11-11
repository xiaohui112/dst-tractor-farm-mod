--[[
	Tractor —— 挂件物料仓

	设计原则（按评审意见重写）：
	- 不再用"隐藏实体"存物品。隐藏实体不会恢复显示、读档会丢状态，是错误做法。
	- 种子 / 肥料：用原版 container 组件真实持有，容器自带 OnSave/OnLoad，
	  物品始终是正常实体，读档、换挂件、死亡都安全。
	- 水：属于**洒水机自身**的状态（像洒水壶的剩余次数），存在挂件的
	  finiteuses 上，换挂件、读档都不会丢。

	所以本组件只做一个薄壳：持有容器引用 + 提供取料接口。
]]

local AttachmentStore = Class(function(self, inst)
	self.inst = inst
	-- 由底盘在初始化时塞进来的"物料容器"（另一个 container 实例）
	self.container = nil
end)

---------------------------------------------------------------------------
-- 水：存在挂件自身的 finiteuses 上
---------------------------------------------------------------------------

local function WaterUses(self)
    local item=self:_GetAttachment()
    return item and item.attachment_type==AOM_ATTACHMENT_TYPE.IRRIGATOR and item.components.finiteuses or nil
end

function AttachmentStore:GetWater()
    local uses=WaterUses(self)
    return uses and math.max(0,math.min(uses.total,math.floor(uses:GetUses()))) or 0
end

function AttachmentStore:GetWaterMax()
    local uses=WaterUses(self)
    return uses and uses.total or 0
end

function AttachmentStore:AddWater(amount)
    local uses=WaterUses(self)
    if not uses or type(amount)~="number" or amount~=amount then return 0 end
    local add=math.max(0,math.min(math.floor(amount),self:GetWaterMax()-self:GetWater()))
    if add>0 then
        uses:SetUses(self:GetWater()+add)
        self.inst:PushEvent("aom_water_changed")
    end
    return add
end

function AttachmentStore:TakeWater()
    local uses=WaterUses(self)
    if not uses or self:GetWater()<1 then return false end
    uses:Use(1)
    self.inst:PushEvent("aom_water_changed")
    return true
end

function AttachmentStore:ReturnWater()
    return self:AddWater(1)
end

---------------------------------------------------------------------------
-- 获取当前挂件物品
---------------------------------------------------------------------------

function AttachmentStore:_GetAttachment()
	if self.inst.components.container == nil then
		return nil
	end
	return self.inst.components.container:GetItemInSlot(1)
end

function AttachmentStore:_GetMaterialContainer()
	return self.container
end

function AttachmentStore:SetMaterialContainer(container)
	self.container = container
end

---------------------------------------------------------------------------
-- 种子
---------------------------------------------------------------------------

function AttachmentStore:GetSeedCount()
	local c = self.container
	if c == nil then return 0 end
	local n = 0
	for i = 1, c.numslots or 0 do
		local item = c:GetItemInSlot(i)
		if item ~= nil and item.components.farmplantable ~= nil then
			n = n + (item.components.stackable ~= nil and item.components.stackable:StackSize() or 1)
		end
	end
	return n
end

-- 列出仓里所有种子（按槽位顺序）
function AttachmentStore:ListSeeds()
	local c = self.container
	local out = {}
	if c == nil then return out end
	for i = 1, c.numslots or 0 do
		local item = c:GetItemInSlot(i)
		if item ~= nil and item:IsValid() and item.components.farmplantable ~= nil then
			table.insert(out, item)
		end
	end
	return out
end

-- 按槽位顺序取第一颗（策略 1）
function AttachmentStore:TakeSeeds()
	local list = self:ListSeeds()
	if #list == 0 then return nil end
	return self:_SplitOne(self.container, list[1])
end

-- 按指定作物取一颗（策略 3：巨大化配比）
-- crop_name 为 nil 时等同于 TakeSeeds
function AttachmentStore:TakeSeedOfCrop(crop_name, get_crop_fn)
	local list = self:ListSeeds()
	if #list == 0 then return nil end
	if crop_name == nil then
		return self:_SplitOne(self.container, list[1])
	end
	for _, item in ipairs(list) do
		if get_crop_fn(item) == crop_name then
			return self:_SplitOne(self.container, item)
		end
	end
	return nil
end

-- 统计仓里每种作物各有多少颗
function AttachmentStore:CountSeedsByCrop(get_crop_fn)
	local counts = {}
	for _, item in ipairs(self:ListSeeds()) do
		local crop = get_crop_fn(item)
		if crop ~= nil then
			local n = item.components.stackable ~= nil and item.components.stackable:StackSize() or 1
			counts[crop] = (counts[crop] or 0) + n
		end
	end
	return counts
end

function AttachmentStore:ReturnSeed(item)
	local c = self.container
	if c == nil or item == nil or not item:IsValid() then
		return
	end
	c:GiveItem(item, nil, true)
end

---------------------------------------------------------------------------
-- 肥料
---------------------------------------------------------------------------

function AttachmentStore:ListFertilizers()
    local out={}
    local c=self.container
    if c then
        for i=2,c.numslots or 0 do
            local item=c:GetItemInSlot(i)
            if item and item:IsValid() and item.components.fertilizer then out[#out+1]=item end
        end
    end
    return out
end

-- 统计真实可施用次数，包含多次用量和堆叠；不把一桶肥料算作一次。
function AttachmentStore:GetFertilizerCount()
    local n=0
    local Fertilizer=require("aom_fertilizer")
    for _,item in ipairs(self:ListFertilizers()) do n=n+Fertilizer.Doses(item) end
    return n
end

---------------------------------------------------------------------------
-- 通用：往物料容器里塞一件物品（自动拆堆叠的一份）
---------------------------------------------------------------------------

function AttachmentStore:_SplitOne(container, item)
	-- 堆叠：只拆一份出来，剩下的留在原格
	if item.components.stackable ~= nil and item.components.stackable:StackSize() > 1 then
		return item.components.stackable:Get(1)
	end
	-- 非堆叠：整件从容器取出，实体保持有效（不 Remove）
	container:RemoveItem(item, true)
	return item
end

-- 把玩家手里的物品放进物料容器（用于"装料"动作）
function AttachmentStore:LoadItem(item,doer)
    local c=self.container
    if not c or not item or not item:IsValid() or not item.components.inventoryitem then return false end
    local ii=item.components.inventoryitem
    local owner=ii.owner
    if owner==self.inst then return false end
    local stack=item.components.stackable
    local size=stack and stack:StackSize() or 1
    local accepted=math.min(size,c:CanAcceptCount(item))
    if accepted<1 then return false end -- 不先拿走满仓时无法接纳的物品
    local source=owner and (owner.components.inventory or owner.components.container)
    local slot=ii.GetSlotNum and ii:GetSlotNum() or nil
    local origin=owner or doer or self.inst
    local pos=Vector3(origin.Transform:GetWorldPosition())
    local moved
    if accepted<size then
        moved=stack:Get(accepted)
        -- 原版 Stackable:Get 会继承原 owner，但拆出物不在原容器槽位中。
        if moved and moved.components.inventoryitem.owner then moved.components.inventoryitem:OnRemoved() end
    elseif owner then moved=ii:RemoveFromOwner(true)
    else moved=item end
    if not moved then return false end
    local before=moved.components.stackable and moved.components.stackable:StackSize() or 1
    local ok,result=pcall(c.GiveItem,c,moved,nil,pos,false)
    local left=0
    if moved:IsValid() and not (ok and result) and moved.components.inventoryitem.owner~=self.inst then
        left=moved.components.stackable and moved.components.stackable:StackSize() or 1
        if source then source:GiveItem(moved,slot,pos) end
        -- 来源已无法接回时，保留实体并放回来源位置，不能遗留无归属的隐藏物品。
        if moved:IsValid() and not moved.components.inventoryitem.owner then
            moved.Transform:SetPosition(pos:Get())
            moved.components.inventoryitem:OnDropped(true)
        end
    end
    local loaded=before-left
    if loaded>0 then self.inst:PushEvent("aom_load_changed") end
    return loaded>0,loaded
end

function AttachmentStore:OnSave()
	-- 物料由 container 自身保存；这里只记容器是否存在
	return self.container ~= nil and true or nil
end

function AttachmentStore:OnLoad(data)
end

return AttachmentStore
