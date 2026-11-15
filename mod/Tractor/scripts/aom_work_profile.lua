-- 速度依据及选值理由见 docs/28-行驶作业与速度依据.md。
-- mph 用于保留现实作业速度比例；世界单位/秒是游戏尺度，不是物理换算。
local M = {}
M.BASE_SPEED = 6
M.SAMPLE_INTERVAL = .1
M.TILE_SIZE = 4
M.DRIVE_FUEL_PER_UNIT = 1 / M.TILE_SIZE -- 每行驶一格另扣1燃料，与农业成本分开。
M.MAX_SWEEP_DISTANCE = 16 -- 超出正常短时移动视为传送，不耕种沿途地块。
M.REFERENCE_MPH = {}
for kind,def in pairs(require("aom_equipment_defs")) do M.REFERENCE_MPH[kind]=def.mph end
function M.Speed(attachment, working)
    return M.BASE_SPEED * (working and (M.REFERENCE_MPH[attachment] or 7) / 7 or 1)
end

-- 网格射线遍历：补上两次采样之间真正经过的地块；对角穿过角点时只进对角格。
function M.TraceTiles(map, x0, z0, x1, z1)
    local cx,_,cz=map:GetTileCenterPoint(x0,0,z0)
    local ex,_,ez=map:GetTileCenterPoint(x1,0,z1)
    if cx==nil or ex==nil then return {} end
    local out={{x=cx,z=cz}}
    local dx,dz=x1-x0,z1-z0
    if dx*dx+dz*dz>M.MAX_SWEEP_DISTANCE*M.MAX_SWEEP_DISTANCE then
        return {{x=ex,z=ez}}
    end
    local sx=dx>0 and 1 or -1
    local sz=dz>0 and 1 or -1
    local tx=dx~=0 and (cx+sx*2-x0)/dx or math.huge
    local tz=dz~=0 and (cz+sz*2-z0)/dz or math.huge
    local dtx=dx~=0 and M.TILE_SIZE/math.abs(dx) or math.huge
    local dtz=dz~=0 and M.TILE_SIZE/math.abs(dz) or math.huge
    for _=1,16 do
        if math.abs(cx-ex)<.01 and math.abs(cz-ez)<.01 then break end
        if math.abs(tx-tz)<1e-9 then
            cx=cx+sx*M.TILE_SIZE;cz=cz+sz*M.TILE_SIZE;tx=tx+dtx;tz=tz+dtz
        elseif tx<tz then cx=cx+sx*M.TILE_SIZE;tx=tx+dtx
        else cz=cz+sz*M.TILE_SIZE;tz=tz+dtz end
        out[#out+1]={x=cx,z=cz}
    end
    return out
end
return M
