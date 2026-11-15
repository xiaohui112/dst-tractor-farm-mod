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
function M.HasEmptySlot(c)
    for i=1,Slots(c)do if not c:GetItemInSlot(i) then return true end end
    return false
end
function M.HasSpace(vehicle)
    local c=Container(vehicle)
    if not c then return true end
    if c.readonlycontainer then return false end
    if M.HasEmptySlot(c) then return true end
    for i=1,Slots(c)do
        local item=c:GetItemInSlot(i)
        local stack=item and item:IsValid() and item.components.stackable
        if stack and stack.RoomLeft and stack:RoomLeft()>0 then return true end
    end
    return false
end
local function Product(v)
    if Crops.IsRotten(v) or string.match(v.prefab,"_oversized_rotten$") then return "spoiled_food" end
    local crop=string.match(v.prefab,"^farm_plant_(.+)$") or string.match(v.prefab,"^(.+)_oversized$")
    local def=v.plant_def or crop and require("prefabs/farm_plant_defs").PLANT_DEFS[crop]
    return def and def.product or crop
end
function M.CanHarvest(v,vehicle)
    local c=Container(vehicle)
    if not c then return true end
    if c.readonlycontainer then return false end
    if M.HasEmptySlot(c) then return true end
    local product=Product(v)
    if not product then return false end
    for i=1,Slots(c)do
        local item=c:GetItemInSlot(i)
        local stack=item and item:IsValid() and item.components.stackable
        -- 原版新产物不带皮肤；自定义叠堆规则无法无副作用预判时保守跳过。
        if item and item.prefab==product and item.skinname==nil and not item.stackable_CanStackWithFn
            and stack and stack.RoomLeft and stack:RoomLeft()>0 then return true end
    end
    return false
end
return M
