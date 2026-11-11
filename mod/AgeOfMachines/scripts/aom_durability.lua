-- 只同步耐久工具；洒水机 finiteuses 是水量，不能显示成工具耐久。
local M={MAX_USES=1000}
local TOOLS={plow=60,seeder=100,weeder=50,harvester=40}
function M.Sync(inst)
    local uses=inst.components.finiteuses
    if inst._uses_net then inst._uses_net:set(uses and uses:GetUses() or 0) end
    local c=inst.components.container
    local item=c and c:GetItemInSlot(1)
    local max=item and TOOLS[item.attachment_type] or 0
    local tool=item and item.components.finiteuses
    if inst._tooluses_net then inst._tooluses_net:set(max>0 and tool and tool:GetUses() or 0) end
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
