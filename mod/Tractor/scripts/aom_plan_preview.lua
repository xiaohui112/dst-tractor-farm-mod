-- 本地预览只有动画，无网络/soil标签/组件，不参与农业与存档。
local Block=require("aom_block_plan")
local M={}
local function Clear(hud)
    for _,marker in ipairs(hud._plan_markers or {}) do if marker:IsValid() then marker:Remove() end end
    hud._plan_markers=nil;hud._plan_marker_key=nil
end
M.Clear=Clear
function M.Refresh(hud,tractor)
    local valid=tractor and tractor:IsValid() and not hud.owner:HasTag("playerghost")
        and tractor._seedmode_net and tractor._seedmode_net:value()=="GIANT"
        and tractor._atttype_net and (tractor._atttype_net:value()=="seeder" or tractor._atttype_net:value()=="plow")
    local key=valid and tractor._plan_net and tractor._plan_net:value() or ""
    local plan=Block.Decode(key)
    if not plan then Clear(hud);return end
    key=tostring(tractor.GUID)..":"..key
    if key==hud._plan_marker_key then return end
    Clear(hud);hud._plan_marker_key=key;hud._plan_markers={}
    local next_tile=plan.next_x and {x=plan.next_x,z=plan.next_z} or nil
    for _,p in ipairs(Block.WorldSlots(plan)) do
        if p.crop and not plan.completed[p.index] then
            next_tile=next_tile or {x=p.cx,z=p.cz}
            if not plan.confirmed or p.cx==next_tile.x and p.cz==next_tile.z then
                local marker=CreateEntity()
                marker.entity:AddTransform();marker.entity:AddAnimState()
                marker.AnimState:SetBank("farm_soil");marker.AnimState:SetBuild("farm_soil")
                marker.AnimState:PlayAnimation("till_idle",true)
                marker.AnimState:SetMultColour(.2,1,.35,.5)
                marker.Transform:SetPosition(p.x,.02,p.z)
                marker:AddTag("FX");marker:AddTag("NOCLICK");marker:AddTag("NOBLOCK")
                marker.persists=false
                hud._plan_markers[#hud._plan_markers+1]=marker
            end
        end
    end
end
return M
