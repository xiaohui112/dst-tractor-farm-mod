-- 原版仅公开“是否湿润”的布尔查询；只读它捕获的实时 DataGrid，不另存水分。
-- 如果原版/其他 Mod 改变接口且无法读取，暂停洒水，不盲浇或预扣物料。
local M = {}

local function FindGrid(fn, seen, depth)
    if type(fn)~="function" or seen[fn] or depth>3 or not debug or not debug.getupvalue then return end
    seen[fn]=true
    local children={}
    for i=1,80 do
        local name,value=debug.getupvalue(fn,i)
        if name==nil then break end
        if name=="_moisturegrid" and value and type(value.GetDataAtPoint)=="function" then return value end
        if type(value)=="function" then children[#children+1]=value end
    end
    for _,child in ipairs(children) do
        local grid=FindGrid(child,seen,depth+1)
        if grid then return grid end
    end
end

function M.Max() return TUNING.SOIL_MAX_MOISTURE_VALUE or 100 end
function M.Dose() return TUNING.WATERINGCAN_WATER_AMOUNT or 25 end

function M.Read(x,y,z)
    local fm=TheWorld.components.farming_manager
    if not fm or not TheWorld.Map then return nil,"MOISTURE_UNAVAILABLE" end
    local ok,value=pcall(function()
        local grid=FindGrid(fm.IsSoilMoistAtPoint,{},0)
        if not grid then return end
        local moisture=grid:GetDataAtPoint(TheWorld.Map:GetTileCoordsAtPoint(x,y,z))
        if moisture==nil then moisture=TheWorld.state.wetness end
        if type(moisture)=="number" and moisture==moisture then
            return math.max(0,math.min(M.Max(),moisture))
        end
    end)
    if not ok or value==nil then return nil,"MOISTURE_UNAVAILABLE" end
    return value
end

-- 只执行一次原版水壶用量；调用者负责水箱记账。
-- 即使别的 Mod 的回调在加水后抛错，也根据真实结果计费，避免退水后重复获得水分。
function M.Apply(x,y,z)
    local before,reason=M.Read(x,y,z)
    if before==nil then return false,reason end
    if before>=M.Max() then return false,"FULL" end
    local fm=TheWorld.components.farming_manager
    local ok=pcall(fm.AddSoilMoistureAtPoint,fm,x,y,z,M.Dose())
    local after=M.Read(x,y,z)
    if after==nil then return true,"MOISTURE_UNAVAILABLE" end -- 已执行，无法确认时不退水
    if after<=before then return false,"WATER_FAILED" end
    return true,not ok and "WATER_FAILED" or nil
end

return M
