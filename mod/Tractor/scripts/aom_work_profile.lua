-- 空驶为原版人物初始跑速，F作业时减半。
local M = {}
M.BASE_SPEED = TUNING.WILSON_RUN_SPEED or 6
M.SAMPLE_INTERVAL = .1
M.TILE_SIZE = 4
M.DRIVE_FUEL_PER_UNIT = 1 / 8
M.MAX_SWEEP_DISTANCE = 16 -- 超出正常短时移动视为传送，不耕种沿途地块。
M.REFERENCE_MPH = {}
for kind,def in pairs(require("aom_equipment_defs")) do M.REFERENCE_MPH[kind]=def.mph end
function M.Speed(working)
    return M.BASE_SPEED * (working and .5 or 1)
end

-- 网格射线遍历：补上两次采样之间真正经过的地块；对角穿过角点时只进对角格。
function M.TraceTiles(map, x0, z0, x1, z1)
    local cx,_,cz=map:GetTileCenterPoint(x0,0,z0)
    local ex,_,ez=map:GetTileCenterPoint(x1,0,z1)
    if cx==nil or ex==nil then return {} end
    local out={}
    local dx,dz=x1-x0,z1-z0
    if dx*dx+dz*dz>M.MAX_SWEEP_DISTANCE*M.MAX_SWEEP_DISTANCE then
        return {{x=ex,z=ez,contact_x=x1,contact_z=z1}}
    end
    local sx=dx>0 and 1 or -1
    local sz=dz>0 and 1 or -1
    local tx=dx~=0 and (cx+sx*2-x0)/dx or math.huge
    local tz=dz~=0 and (cz+sz*2-z0)/dz or math.huge
    local dtx=dx~=0 and M.TILE_SIZE/math.abs(dx) or math.huge
    local dtz=dz~=0 and M.TILE_SIZE/math.abs(dz) or math.huge
    local entered=0
    for _=1,16 do
        if math.abs(cx-ex)<.01 and math.abs(cz-ez)<.01 then break end
        if math.abs(cx-ex)<.01 then tx=math.huge end
        if math.abs(cz-ez)<.01 then tz=math.huge end
        -- 沿途格的效果留在实际扫过的段上，最后一格使用当前作业点。
        local exit=math.min(tx,tz)
        local middle=(entered+exit)*.5
        out[#out+1]={x=cx,z=cz,contact_x=x0+dx*middle,contact_z=z0+dz*middle}
        entered=exit
        if math.abs(tx-tz)<1e-9 then
            cx=cx+sx*M.TILE_SIZE;cz=cz+sz*M.TILE_SIZE;tx=tx+dtx;tz=tz+dtz
        elseif tx<tz then cx=cx+sx*M.TILE_SIZE;tx=tx+dtx
        else cz=cz+sz*M.TILE_SIZE;tz=tz+dtz end
    end
    out[#out+1]={x=ex,z=ez,contact_x=x1,contact_z=z1}
    return out
end
return M
