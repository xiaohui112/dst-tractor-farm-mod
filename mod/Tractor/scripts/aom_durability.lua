-- Mechanical durability is independent from water; exhausted tools detach for repair.
local M={MAX_USES=1000}
local Definitions=require("aom_equipment_defs")
local TOOLS,BROKEN={},{}
for kind,def in pairs(Definitions) do TOOLS[kind]=def.uses;BROKEN[kind]=def.broken end
M.TOOLS=TOOLS
function M.GetUses(item)
    if not item or not item:IsValid() then return 0 end
    if Definitions[item.attachment_type] and Definitions[item.attachment_type].separate_uses then
        return item._aom_machine_uses or TOOLS[item.attachment_type]
    end
    local uses=item.components.finiteuses
    return uses and uses:GetUses() or 0
end
function M.CanWork(inst)
    local item=require("aom_attachment_mount").Get(inst)
    if not item or not item:IsValid() or not Definitions[item.attachment_type] then return false,"NO_ATTACHMENT" end
    if M.GetUses(item)<=0 then return false,BROKEN[item.attachment_type] end
    return true
end
function M.RepairAttachment(item)
    local max=item and TOOLS[item.attachment_type]
    if not max or M.GetUses(item)>=max then return false end
    local value=math.min(max,M.GetUses(item)+Definitions[item.attachment_type].repair)
    if Definitions[item.attachment_type] and Definitions[item.attachment_type].separate_uses then item._aom_machine_uses=value
    else item.components.finiteuses:SetUses(value) end
    item._aom_spent=nil
    if item._durability_net then item._durability_net:set(value) end
    item:PushEvent("percentusedchange")
    return true
end
function M.OnAttachmentFinished(item)
    if item._aom_spent or not BROKEN[item.attachment_type] then return end
    item._aom_spent=true
    local Mount=require("aom_attachment_mount")
    local owner=item._aom_work_vehicle or Mount.Owner(item)
    local source=owner and (owner._rider or owner) or item
    local x,y,z=source.Transform:GetWorldPosition()
    if owner then
        owner._aom_broken_attachment_reason=BROKEN[item.attachment_type]
        require("aom_drive").SetWorking(owner,false)
        local detached=true
        if owner.GetAttachment then detached=Mount.Detach(owner,nil)
        else
            local c=owner.components.container
            if c then c:RemoveItem(item,true) end
            owner._attachment_type=nil
            item.Transform:SetPosition(x,y,z)
            M.Sync(owner)
        end
        require("aom_drive").StopForReason(owner,BROKEN[item.attachment_type],not detached and
            require("aom_locale").Text("配件已损坏，附近无空地；驶到空地后右键卸载并维修") or nil)
    end
    if item._durability_net then item._durability_net:set(0) end
    local fx=SpawnPrefab("dirt_puff")
    if fx then fx.Transform:SetPosition(x,y,z) end
    if owner then owner:PushEvent("toolbroke",{tool=item}) end
end

function M.UseAttachment(inst,item)
    if not item then return end
    item._aom_work_vehicle=inst
    local ok,err=pcall(function()
        if Definitions[item.attachment_type] and Definitions[item.attachment_type].separate_uses then
            item._aom_machine_uses=math.max(0,M.GetUses(item)-1)
            item:PushEvent("percentusedchange")
        else item.components.finiteuses:Use(1) end
        if item._durability_net then item._durability_net:set(M.GetUses(item)) end
        -- 同时支持旧挂件或不带 onfinished 的工具实现。
        if item:IsValid() and M.GetUses(item)<=0 then M.OnAttachmentFinished(item) end
    end)
    item._aom_work_vehicle=nil
    if not ok then error(err,0) end
end
function M.Sync(inst)
    local uses=inst.components.finiteuses
    if inst._uses_net then inst._uses_net:set(uses and uses:GetUses() or 0) end
    local c=inst.components.container
    if inst._cargo_used_net and c then
        local used=0
        for slot=1,c:GetNumSlots() do if c:GetItemInSlot(slot) then used=used+1 end end
        inst._cargo_used_net:set(used)
    end
    local item=require("aom_attachment_mount").Get(inst)
    local max=item and TOOLS[item.attachment_type] or 0
    local tool=item and item.components.finiteuses
    if inst._tooluses_net then inst._tooluses_net:set(max>0 and M.GetUses(item) or 0) end
    if inst._toolmax_net then inst._toolmax_net:set(max) end
    local store=inst.components.aom_attachment_store
    if inst._seedcount_net then inst._seedcount_net:set(store and store:GetSeedCount() or 0) end
end
function M.WatchSeeds(inst)
    for _,item in ipairs(inst._watched_seeds or {})do inst:RemoveEventCallback("stacksizechange",M.Sync,item)end
    local store=inst.components.aom_attachment_store
    inst._watched_seeds=store and store:ListSeeds() or {}
    for _,item in ipairs(inst._watched_seeds)do inst:ListenForEvent("stacksizechange",M.Sync,item)end
    M.Sync(inst)
end
return M
