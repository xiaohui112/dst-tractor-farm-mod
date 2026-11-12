-- 车体精灵高 300；本机原版成年牛 idle_loop 高约 680～695。
-- 基础倍率 2.5 使标准车体达到同一体量；配置只调整相对大小。
local BASE_SCALE=2.5
local config=rawget(_G,"AOM_CONFIG")
local scale=type(config)=="table" and tonumber(config.MODEL_SCALE) or nil
-- 旧版存档中的 2/2.5/3/4 倍设置自动回到新标准，避免继续使用旧放大倍率。
local multiplier=scale and scale>=.75 and scale<=1.5 and scale or 1
return BASE_SCALE*multiplier
