-- 容量、真实剩余堆叠空间与满格收割筛选共用规则。
local M={SLOTS=15}
local Crops=require("aom_crop_state")
-- 容器缩容后先恢复仍有效的格子，再合并/安置旧第16格；放不下由原版安全落地。
function M.Load(container,data,newents,load)
    if not data or not data.items then return load(container,data,newents) end
    local items={}
    local overflow={}
    for slot,record in pairs(data.items) do
        if type(slot)=="number" and slot>=1 and slot<=M.SLOTS then items[slot]=record
        else overflow[#overflow+1]=record end
    end
    load(container,{items=items},newents)
    for _,record in ipairs(overflow) do
        local item=SpawnSaveRecord(record,newents)
        if item then container:GiveItem(item) end
    end
end
function M.Layout(doer)
    local inv=doer and doer.HUD and doer.HUD.controls and doer.HUD.controls.inv
    local slots=inv and inv.inv
    -- 原版W=68、SEP=12、INTERSEP=28；每5格的分组间距比普通间距多16。
    local span=(M.SLOTS-1)*80+math.floor((M.SLOTS-1)/5)*16
    local first=slots and slots[1]
    local left=first and first:GetPosition().x or -span/2
    local positions={}
    for i=1,M.SLOTS do
        local slot=slots and slots[i]
        positions[i]=slot and slot:GetPosition().x or left+(i-1)*80+math.floor((i-1)/5)*16
    end
    -- 优先逐格读取真实人物栏，兼容背包/控制器布局重建及其他Mod改变分组。
    local center=(positions[1]+positions[M.SLOTS])/2
    local out={}
    for i,x in ipairs(positions) do out[i]=Vector3(x-center,0,0) end
    return out,Vector3(center,80,0),positions[M.SLOTS]-positions[1]+128
end
function M.Position(container,doer)
    local slots,position=M.Layout(doer)
    return position
end
function M.SlotPositions(container,doer)
    local slots=M.Layout(doer)
    return slots
end
local function Container(vehicle)return vehicle and vehicle.components.container end
local function Slots(c)return c.GetNumSlots and c:GetNumSlots() or c.numslots or 0 end
function M.DriverStorage(driver)
    local inventory=driver and driver:IsValid() and driver.components.inventory
    local backpack=inventory and inventory.GetOverflowContainer and inventory:GetOverflowContainer()
    return inventory,backpack
end
local function Destinations(vehicle)
    local inventory,backpack=M.DriverStorage(vehicle and vehicle._rider)
    return Container(vehicle),inventory,backpack
end

local function PutInContainer(container,item,picker,pos)
    if not container or container.inst==item or container.readonlycontainer or not container:CanTakeItemInSlot(item) then return end
    local stack=item.components.stackable
    local size=stack and stack:StackSize() or 1
    local count=math.min(size,container:CanAcceptCount(item))
    if count<=0 then return end
    local part=count<size and stack:Get(count) or item
    part.Transform:SetPosition(pos:Get())
    local consumed=part.components.inventoryitem:OnPickup(picker,pos)
    if not consumed and part:IsValid() and not part.components.inventoryitem.owner then
        container:GiveItem(part,nil,pos,false)
    end
    -- 堆栈只转走了一部分时，原地的余量继续尝试后面的库存。
    if part==item then return not item:IsValid() or item.components.inventoryitem.owner~=nil or consumed end
    return false
end

local function PutInPockets(inventory,item,pos)
    if not inventory or inventory.readonlycontainer then return end
    local overflow,full=inventory.ignoreoverflow,inventory.ignorefull
    -- 逐格指定投放位置，避免原版优先投到某些背包、装备槽或鼠标手上。
    inventory.ignoreoverflow=true;inventory.ignorefull=true
    local ok,err=pcall(function()
        for pass=1,2 do
            for slot=1,Slots(inventory) do
                if not item:IsValid() or item.components.inventoryitem.owner then return end
                local existing=inventory:GetItemInSlot(slot)
                if inventory:CanTakeItemInSlot(item,slot) then
                    local stack=existing and existing.components.stackable
                    if pass==1 and stack and stack:CanStackWith(item) and stack:RoomLeft()>0 then
                        local source=item.components.stackable
                        if source then
                            local amount=math.min(stack:RoomLeft(),source:StackSize())
                            local part=amount<source:StackSize() and source:Get(amount) or item
                            part.Transform:SetPosition(pos:Get())
                            inventory:GiveItem(part,slot,pos)
                        end
                    elseif pass==2 and existing==nil then
                        inventory:GiveItem(item,slot,pos)
                    end
                end
            end
        end
    end)
    inventory.ignoreoverflow=overflow;inventory.ignorefull=full
    if not ok then error(err,0) end
end

function M.Collect(vehicle,item)
    local cargo,inventory,backpack=Destinations(vehicle)
    local pos=Vector3(item.Transform:GetWorldPosition())
    if PutInContainer(cargo,item,vehicle,pos) then return true end
    PutInPockets(inventory,item,pos)
    if not item:IsValid() or item.components.inventoryitem.owner then return true end
    return PutInContainer(backpack,item,vehicle._rider,pos) or false
end

function M.HasEmptySlot(c)
    for i=1,Slots(c)do if not c:GetItemInSlot(i) then return true end end
    return false
end
local function HasSpace(c,product)
    if not c or c.readonlycontainer then return false end
    if M.HasEmptySlot(c) then return true end
    for i=1,Slots(c)do
        local item=c:GetItemInSlot(i)
        local stack=item and item:IsValid() and item.components.stackable
        if stack and stack.RoomLeft and stack:RoomLeft()>0
            and (product==nil or item.prefab==product and item.skinname==nil and not item.stackable_CanStackWithFn) then
            return true
        end
    end
    return false
end
function M.HasSpace(vehicle)
    local cargo,inventory,backpack=Destinations(vehicle)
    return not cargo or HasSpace(cargo) or HasSpace(inventory) or HasSpace(backpack)
end
local function Product(v)
    if Crops.IsRotten(v) or string.match(v.prefab,"_oversized_rotten$") then return "spoiled_food" end
    local crop=string.match(v.prefab,"^farm_plant_(.+)$") or string.match(v.prefab,"^(.+)_oversized$")
    local def=v.plant_def or crop and require("prefabs/farm_plant_defs").PLANT_DEFS[crop]
    return def and def.product or crop
end
function M.CanHarvest(v,vehicle)
    local cargo,inventory,backpack=Destinations(vehicle)
    if not cargo then return true end
    local product=Product(v) or false
    return HasSpace(cargo,product) or HasSpace(inventory,product) or HasSpace(backpack,product)
end
return M
