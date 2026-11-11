-- 原版 MakeDeployableFertilizer 的施肥回调原文摘录，仅用于行为对照。
local function fertilizer_ondeploy(inst, pt, deployer)
    local tile_x, tile_z = TheWorld.Map:GetTileCoordsAtPoint(pt:Get())
    local nutrients = inst.components.fertilizer.nutrients
    TheWorld.components.farming_manager:AddTileNutrients(tile_x, tile_z, nutrients[1], nutrients[2], nutrients[3])
    
    inst.components.fertilizer:OnApplied(deployer)
    if deployer ~= nil and deployer.SoundEmitter ~= nil and inst.components.fertilizer.fertilize_sound ~= nil then
        deployer.SoundEmitter:PlaySound(inst.components.fertilizer.fertilize_sound)
    end

    if inst.ondeployed_fertilzier_extra_fn then
        inst.ondeployed_fertilzier_extra_fn(inst, pt, deployer)
    end
end

return fertilizer_ondeploy
