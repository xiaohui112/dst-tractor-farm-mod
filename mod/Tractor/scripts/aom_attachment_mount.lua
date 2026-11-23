-- 独立世界挂点：配件始终是实体，不进入仓库或玩家背包。
local M={RANGE=5}
local PREFABS={aom_landclearer=true,aom_plow=true,aom_seeder=true,aom_irrigator=true,
    aom_fertilizer=true,aom_weeder=true,aom_harvester=true}
function M.IsRecord(record)return record and PREFABS[record.prefab]==true end
-- 读取时修复旧版留下的失效引用；先清空再通知，避免状态监听重入。
function M.Current(vehicle)
    local item=vehicle._aom_attachment
    if item and not item:IsValid() then
        if TheWorld.ismastersim then M.Sync(vehicle) end
        return nil
    end
    return item
end
function M.Get(vehicle)
    if vehicle.GetAttachment then return vehicle:GetAttachment() end
    -- 兼容旧载体/外部工具调用；新版底盘始终提供独立 GetAttachment。
    local c=vehicle.components.container
    return c and c:GetItemInSlot(1) or nil
end
function M.Owner(item)
    return item._aom_vehicle and item._aom_vehicle:value() or nil
end
function M.CanReach(doer,item)
    local distance=M.RANGE+doer:GetPhysicsRadius(0)+item:GetPhysicsRadius(0)
    return doer:GetDistanceSqToInst(item)<=distance*distance
end
local function Source(vehicle)
    return vehicle._rider or vehicle
end
function M.WorkPosition(vehicle)
    local x,_,z=Source(vehicle).Transform:GetWorldPosition()
    return x,0,z
end
-- 已挂设备使用父节点的连续变换，不以定时世界坐标重定位追赶车辆。
function M.Rotation(item)
    local parent=item._aom_visual_parent
    return parent and parent:IsValid() and parent.Transform:GetRotation() or item.Transform:GetRotation()
end
local function ClearVisualParent(item)
    local parent=item._aom_visual_parent
    if not parent then return end
    local x,y,z=item.Transform:GetWorldPosition()
    local rotation=M.Rotation(item)
    if item._aom_parent_removed then item:RemoveEventCallback("onremove",item._aom_parent_removed,parent) end
    item.entity:SetParent(nil)
    item._aom_visual_parent=nil;item._aom_parent_removed=nil;item._aom_mount_distance=nil
    item.Transform:SetPosition(x,y,z);item.Transform:SetRotation(rotation)
end
local function UnwatchRemoval(vehicle)
    if vehicle._aom_attachment_removed then
        vehicle:RemoveEventCallback("onremove",vehicle._aom_attachment_removed,vehicle._aom_removal_source)
    end
    vehicle._aom_attachment_removed=nil;vehicle._aom_removal_source=nil
end
function M.FreePosition(vehicle,item)
    local source=Source(vehicle)
    local x,y,z=source.Transform:GetWorldPosition()
    -- DST 朝向为 x=cos(a)、z=-sin(a)。收割机从车头卸载，其余配件从车尾卸载。
    local direction=(source.Transform:GetRotation()+(item.attachment_type=="harvester" and 0 or 180))*math.pi/180
    for _,radius in ipairs({3,4,5,6,8,10,14,18}) do
        for _,offset in ipairs({0,1,-1,2,-2,3,-3}) do
            local a=direction+offset*math.pi/8
            local px,pz=x+radius*math.cos(a),z-radius*math.sin(a)
            if TheWorld.Map:IsPassableAtPoint(px,0,pz) then
                local free=true
                for _,v in ipairs(TheSim:FindEntities(px,0,pz,.8,nil,{"INLIMBO","NOCLICK","FX","NOBLOCK"})) do
                    if v~=vehicle and v~=source and v~=item and v.prefab~="farm_soil"
                        and not v.components.inventoryitem then free=false;break end
                end
                if free then return Vector3(px,0,pz) end
            end
        end
    end
end
function M.Sync(vehicle)
    local item=vehicle._aom_attachment
    if item and not item:IsValid() then
        item=nil;vehicle._aom_attachment=nil
        UnwatchRemoval(vehicle)
        require("aom_drive").SetWorking(vehicle,false)
    end
    vehicle._attachment_type=item and item.attachment_type or nil
    if vehicle._attachment then vehicle._attachment:set(item) end
    if vehicle._atttype_net then vehicle._atttype_net:set(vehicle._attachment_type or "") end
    vehicle:PushEvent("aom_attachment_changed")
end
function M.Detach(vehicle,doer,force)
    local item=M.Current(vehicle)
    if not item then return false,"NO_ATTACHMENT" end
    local pos=M.FreePosition(vehicle,item)
    if not pos and force then pos=Vector3(Source(vehicle).Transform:GetWorldPosition()) end
    if not pos then return false,"NO_DROP_SPACE" end -- 保留原挂载，不丢失物品。
    require("aom_drive").SetWorking(vehicle,false)
    ClearVisualParent(item)
    UnwatchRemoval(vehicle)
    vehicle._aom_attachment=nil
    if item._aom_vehicle then item._aom_vehicle:set(nil) end
    item.persists=true
    item:RemoveTag("NOBLOCK")
    if item.Physics then item.Physics:SetActive(true) end
    item.Transform:SetPosition(pos:Get())
    M.UpdateVisual(item)
    M.Sync(vehicle)
    return true
end
function M.Attach(vehicle,doer,item)
    local current=M.Current(vehicle)
    if vehicle._destroyed or vehicle.components.health and vehicle.components.health:IsDead() then return false,"DESTROYED" end
    if not item or not item:IsValid() or not item:HasTag("aom_attachment") then return false,"INVALID_TARGET" end
    if M.Owner(item) then return false,"IN_USE" end
    if current then return false,"OCCUPIED" end
    if require("aom_durability").GetUses(item)<=0 then return false,"BROKEN" end
    if doer then
        local rider=doer.components.rider
        if not rider or not rider:IsRiding() or rider:GetMount()~=vehicle or vehicle._rider~=doer then return false,"NOT_DRIVING" end
        if not M.CanReach(doer,item) then return false,"TOO_FAR" end
    end
    local ii=item.components.inventoryitem
    if ii and ii.owner then ii:RemoveFromOwner(true) end
    vehicle._aom_attachment=item
    vehicle._aom_removal_source=item
    vehicle._aom_attachment_removed=function()
        -- 直接删除不走卸载/安全落点流程，不能让已删除实体继续占用挂点。
        if vehicle._aom_attachment~=item then return end
        vehicle._aom_attachment=nil
        UnwatchRemoval(vehicle)
        ClearVisualParent(item)
        item._aom_vehicle:set(nil)
        require("aom_drive").StopForReason(vehicle,"NO_ATTACHMENT")
        M.Sync(vehicle)
    end
    vehicle:ListenForEvent("onremove",vehicle._aom_attachment_removed,item)
    item._aom_vehicle:set(vehicle)
    item.persists=false -- 随拖拉机的独立存档记录保存，避免世界里重复加载。
    item:AddTag("NOBLOCK")
    if item.Physics then item.Physics:SetActive(false) end
    require("aom_drive").SetWorking(vehicle,false)
    M.Sync(vehicle)
    M.UpdateVisual(item)
    return true
end
function M.UpdateVisual(item)
    if not item or not item:IsValid() then return end
    local vehicle=M.Owner(item)
    if vehicle and not vehicle:IsValid() then vehicle=nil end
    if vehicle~=item._aom_visual_vehicle then
        item._aom_visual_vehicle=vehicle
        if item.Physics then item.Physics:SetActive(vehicle==nil) end
        if TheWorld.ismastersim then
            local stopping=item.AnimState:IsCurrentAnimation(item.attachment_type.."_work_pst")
            item.AnimState:SetBank(vehicle and "aom_attachment_mounted" or "aom_attachment_shared")
            item.AnimState:PlayAnimation(item.attachment_type..(stopping and "_work_pst" or ""),not stopping)
            if stopping then item.AnimState:PushAnimation(item.attachment_type,true) end
        end
    end
    if not vehicle then
        if TheWorld.ismastersim then ClearVisualParent(item) end
        require("aom_attachment_animation").Update(item,nil)
        return
    end
    local rider=vehicle._rider_net and vehicle._rider_net:value()
    local source=rider and rider:IsValid() and rider or vehicle
    if TheWorld.ismastersim then
        -- 精确的连接位置由五视图挂载bank负责；微小位移仅保留前后深度排序。
        local distance=require("aom_model_scale")*(item.attachment_type=="harvester" and .01 or -.01)
        if item._aom_visual_parent~=source then
            ClearVisualParent(item)
            item.entity:SetParent(source.entity)
            item._aom_visual_parent=source
            item._aom_parent_removed=function()
                -- 父实体移除前保留世界坐标，避免挂件随骑手删除或丢失。
                if item:IsValid() and item._aom_visual_parent==source then ClearVisualParent(item) end
            end
            item:ListenForEvent("onremove",item._aom_parent_removed,source)
        end
        if item._aom_mount_distance~=distance then
            item._aom_mount_distance=distance
            item.Transform:SetPosition(distance,0,0)
            item.Transform:SetRotation(0) -- 朝向由父变换继承，不能重复叠加。
        end
    end
    require("aom_attachment_animation").Update(item,vehicle)
end
function M.Restore(vehicle,record)
    if not record then return end
    local item=SpawnSaveRecord(record)
    if item and not M.Attach(vehicle,nil,item) then
        local pos=M.FreePosition(vehicle,item) or Source(vehicle):GetPosition()
        item.Transform:SetPosition(pos:Get())
    end
end
return M
