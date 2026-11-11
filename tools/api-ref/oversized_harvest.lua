-- 原版 prefabs/veggies.lua 原文摘录，仅供测试。
local function oversized_onfinishwork(inst, chopper)
    inst.components.lootdropper:DropLoot()
    inst:Remove()
end

local function oversized_makeloots(inst, name)
    local product = name
	local seeds = name.."_seeds"
    return {product, product, seeds, seeds, math.random() < 0.75 and product or seeds}
end

return {Finish=oversized_onfinishwork,MakeLoot=oversized_makeloots}
