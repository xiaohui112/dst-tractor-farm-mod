-- 六类设备共享的机械规则；农业行为留在各自作业模块。
local M={
    plow={prefab="aom_landclearer",mph=3.75,broken="BROKEN_ATTACHMENT"},
    seeder={prefab="aom_seeder",mph=5.5,broken="BROKEN_SEEDER",material="seeds"},
    irrigator={prefab="aom_irrigator",mph=6.5,broken="BROKEN_IRRIGATOR",material="water",separate_uses=true},
    fertilizer={prefab="aom_fertilizer",mph=7,broken="BROKEN_FERTILIZER",material="fertilizer",separate_uses=true},
    weeder={prefab="aom_weeder",mph=5,broken="BROKEN_WEEDER"},
    harvester={prefab="aom_harvester",mph=5,broken="BROKEN_HARVESTER"},
}
for _,def in pairs(M) do def.uses=200;def.repair=50 end
return M
