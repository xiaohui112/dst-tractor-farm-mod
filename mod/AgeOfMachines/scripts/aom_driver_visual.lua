-- 人物沿用原版角色 build/皮肤，只切换复用原版骑牛时间线的驾驶 bank。
-- 驾驶室后层、人物、车窗/车身前层在同一个 AnimState 内排序，转向不拆散。
local Bank=require("aom_driver_visual_bank")
local M={ASSET="anim/aom_tractor_driver.zip",ready=false}

-- 骑乘时原版会隐藏车体，只画角色 AnimState 里的驾驶室；这里按底盘同一比例放大，
-- 否则坐进驾驶室后整个模型会比停在地上时小一圈。
local AOM_CONFIG=rawget(_G,"AOM_CONFIG")
M.SCALE=type(AOM_CONFIG)=="table" and tonumber(AOM_CONFIG.MODEL_SCALE) or 3

function M.Configure(root,exists)
    M.ready=false
    if Bank.available and root and type(exists)=="function" then
        local ok,found=pcall(exists,root..M.ASSET)
        M.ready=ok and found and true or false
    end
    return M.ready
end

function M.UpdateAttachment(inst,animstate)
    if not M.ready or not animstate then return end
    local kind=inst._attachment_type
    animstate:OverrideSymbol("aom_driver_attachment_rear","aom_attachment_symbols",
        kind and kind~="harvester" and kind or "empty")
    animstate:OverrideSymbol("aom_driver_attachment_front","aom_attachment_symbols",
        kind=="harvester" and "harvester" or "empty")
end

function M.Apply(inst,animstate)
    if not M.ready or not animstate or animstate==inst.AnimState then return end
    -- 不调用 SetBuild：角色、皮肤、帽子、衣服等覆盖符号继续由原版维护。
    animstate:AddOverrideBuild(Bank.build)
    animstate:SetBank(Bank.bank)
    animstate:SetScale(M.SCALE,M.SCALE,M.SCALE)
    inst._aom_driver_animstate=animstate
    M.UpdateAttachment(inst,animstate)
end

function M.Clear(inst,animstate)
    if not animstate or inst._aom_driver_animstate~=animstate then return end
    animstate:ClearOverrideBuild(Bank.build)
    animstate:ClearOverrideSymbol("aom_driver_attachment_rear")
    animstate:ClearOverrideSymbol("aom_driver_attachment_front")
    animstate:SetScale(1,1,1)
    inst._aom_driver_animstate=nil
    -- 原版 ActualDismount 已恢复 wilson bank，不改角色自己的 build 或皮肤。
end

function M.Attach(inst)
    inst.ApplyBuildOverrides=M.Apply
    inst.ClearBuildOverrides=M.Clear
end

return M
