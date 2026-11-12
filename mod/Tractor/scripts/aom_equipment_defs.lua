-- 六类设备共享的机械规则；农业行为留在各自作业模块。
local M={
    plow={prefab="aom_landclearer",uses=60,mph=3.75,broken="BROKEN_ATTACHMENT"},
    seeder={prefab="aom_seeder",uses=100,mph=5.5,broken="BROKEN_SEEDER",material="seeds"},
    irrigator={prefab="aom_irrigator",uses=60,mph=6.5,broken="BROKEN_IRRIGATOR",material="water",separate_uses=true},
    fertilizer={prefab="aom_fertilizer",uses=60,mph=7,broken="BROKEN_FERTILIZER",material="fertilizer",separate_uses=true},
    weeder={prefab="aom_weeder",uses=50,mph=5,broken="BROKEN_WEEDER"},
    harvester={prefab="aom_harvester",uses=40,mph=5,broken="BROKEN_HARVESTER"},
}
for _,def in pairs(M) do def.repair=10 end
return M
