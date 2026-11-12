-- 人物沿用原版角色 build/皮肤，只切换复用原版骑牛时间线的驾驶 bank。
-- 驾驶室后层、人物、车窗/车身前层在同一个 AnimState 内排序，转向不拆散。
local Bank=require("aom_driver_visual_bank")
local M={ASSET="anim/aom_tractor_driver.zip",SHARED_ASSET="anim/aom_tractor_cabin.zip",ready=false}

-- 车体与驾驶室倍率一致；按模型设置选择逆向补偿人物大小的动画。
M.SCALE=require("aom_model_scale")
M.BANK=Bank.variants and Bank.variants[M.SCALE] or Bank.bank
M.ASSET="anim/"..M.BANK..".zip"

function M.Configure(root,exists)
    M.ready=false
    if Bank.available and root and type(exists)=="function" then
        local shared_ok,shared_found=pcall(exists,root..M.SHARED_ASSET)
        local ok,found=pcall(exists,root..M.ASSET)
        M.ready=shared_ok and shared_found and ok and found and true or false
    end
    return M.ready
end

function M.UpdateAttachment(inst,animstate)
    if not M.ready or not animstate then return end
    local kind=inst._attachment_type or (inst._atttype_net and inst._atttype_net:value())
    if kind=="" then kind=nil end
    animstate:OverrideSymbol("aom_driver_attachment_rear","aom_attachment_symbols",
        "empty")
    animstate:OverrideSymbol("aom_driver_attachment_front","aom_attachment_symbols",
        "empty")
end

function M.Apply(inst,animstate)
    if not M.ready or not animstate or animstate==inst.AnimState then return end
    -- 不调用 SetBuild：角色、皮肤、帽子、衣服等覆盖符号继续由原版维护。
    animstate:AddOverrideBuild(Bank.build)
    animstate:SetBank(M.BANK)
    if inst._rider and inst._rider.Transform then inst._rider.Transform:SetEightFaced() end
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
    if inst._rider and inst._rider.Transform then inst._rider.Transform:SetFourFaced() end
    inst._aom_driver_animstate=nil
    -- 原版 ActualDismount 已恢复 wilson bank，不改角色自己的 build 或皮肤。
end

function M.Attach(inst)
    inst.ApplyBuildOverrides=M.Apply
    inst.ClearBuildOverrides=M.Clear
end

return M
