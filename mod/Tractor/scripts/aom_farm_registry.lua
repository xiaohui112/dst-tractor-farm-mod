-- 服务端的世界级、临时农田索引。它只是缓存，播种时必须重新核对现场。
local M={}
local function Key(x,z)return string.format('%.3f:%.3f',x,z)end
local function Registry(world)
    if not world then return end
    world._aom_ready_farm_tiles=world._aom_ready_farm_tiles or {}
    return world._aom_ready_farm_tiles
end
function M.Record(world,x,z)
    local tiles=Registry(world)
    if tiles and type(x)=='number' and type(z)=='number' then tiles[Key(x,z)]={x=x,z=z} end
end
function M.Remove(world,x,z)
    local tiles=Registry(world);if tiles then tiles[Key(x,z)]=nil end
end
-- 只连上下左右；保留真实坐标。上限只限制单次规划，避免遍历整个世界。
function M.Connected(world,x,z,limit)
    local tiles=Registry(world);local queue,out,seen={}, {}, {}
    local first=tiles and tiles[Key(x,z)]
    if not first then return out,false end
    queue[1]=first;seen[Key(x,z)]=true
    local i=1
    while i<=#queue do
        local tile=queue[i];i=i+1;out[#out+1]=tile
        for _,offset in ipairs({{0,-4},{-4,0},{4,0},{0,4}}) do
            local k=Key(tile.x+offset[1],tile.z+offset[2]);local nexttile=tiles[k]
            if nexttile and not seen[k] then seen[k]=true;queue[#queue+1]=nexttile end
        end
        if limit and #out>=limit and i<=#queue then return out,true end
    end
    return out,false
end
return M
