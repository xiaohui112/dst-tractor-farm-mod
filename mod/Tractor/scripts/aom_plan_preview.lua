-- 本地预览只有动画，无网络/soil标签/组件，不参与农业与存档。
local Block=require("aom_block_plan")
local M={}
local function Clear(hud)
    for _,marker in ipairs(hud._plan_markers or {}) do if marker:IsValid() then marker:Remove() end end
    hud._plan_markers=nil;hud._plan_marker_key=nil;hud._plan_marker_vehicle=nil
end
M.Clear=Clear
function M.Refresh(hud,tractor)
    local valid=tractor and tractor:IsValid() and not hud.owner:HasTag("playerghost")
        and tractor._seedmode_net and require("aom_seed_strategy").IsGiant(tractor._seedmode_net:value())
        and tractor._atttype_net and tractor._atttype_net:value()=="seeder"
    local key=valid and tractor._plan_net and tractor._plan_net:value() or ""
    if not valid or key=="" then Clear(hud);return end
    key=tostring(tractor.GUID)..":"..key
    if key==hud._plan_marker_key then return end
    local plan=Block.Decode(tractor._plan_net:value())
    if not plan then Clear(hud);return end
    if hud._plan_marker_vehicle~=tractor then Clear(hud) end
    local previous={}
    for _,marker in ipairs(hud._plan_markers or {}) do previous[marker._aom_slot]=marker end
    hud._plan_marker_key=key;hud._plan_marker_vehicle=tractor;hud._plan_markers={}
    for _,p in ipairs(Block.WorldSlots(plan)) do
        if p.crop and not plan.completed[p.index] then
            local slot=string.format("%.4f:%.4f:%s",p.x,p.z,p.crop)
            local marker=previous[slot];previous[slot]=nil
            if not marker or not marker:IsValid() then
                marker=CreateEntity()
                marker.entity:AddTransform();marker.entity:AddAnimState()
                marker.AnimState:SetBank("farm_soil");marker.AnimState:SetBuild("farm_soil")
                marker.AnimState:PlayAnimation("till_idle",true)
                require("aom_soil_visual").Ground(marker,true)
                marker.AnimState:SetMultColour(.2,1,.35,.65)
                marker.Transform:SetPosition(p.x,0,p.z)
                marker:AddTag("FX");marker:AddTag("NOCLICK");marker:AddTag("NOBLOCK")
                marker.persists=false;marker._aom_slot=slot
            end
            hud._plan_markers[#hud._plan_markers+1]=marker
        end
    end
    for _,marker in pairs(previous) do if marker:IsValid() then marker:Remove() end end
end
return M
