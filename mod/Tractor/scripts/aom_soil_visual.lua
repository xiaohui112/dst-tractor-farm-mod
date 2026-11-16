-- 土坑是地面覆盖物；沿用原版塌陷土坑的背景层和排序，不参与实体前后遮挡。
local M={}
function M.Ground(inst,preview)
    inst.AnimState:SetLayer(LAYER_BACKGROUND)
    inst.AnimState:SetSortOrder(preview and 3 or 2)
end
return M
