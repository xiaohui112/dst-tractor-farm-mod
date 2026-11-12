-- 悬停信息仅读网络字段；手持燃料/修理材料时也能看到目标机器状态。
local L=require("aom_locale").Text
local M={}
local function Value(inst,key,default)
    return inst[key] and inst[key]:value() or default
end
function M.Describe(inst)
    if not inst or not inst:IsValid() then return nil end
    if inst.prefab=="aom_tractor_chassis" then
        return L("燃料 %d/%d",Value(inst,"_fuel",0),800)
    elseif inst.prefab=="aom_irrigator" then
        return L("机械耐久 %d/%d",Value(inst,"_durability_net",0),require("aom_equipment_defs").irrigator.uses)
            .."\n"..L("水量 %d/%d",Value(inst,"_aom_water_net",0),require("aom_irrigator").Capacity())
    end
end
function M.Install(hoverer)
    local original=hoverer.text.SetString
    hoverer.text.SetString=function(text,str,...)
        local added=0
        if type(str)=="string" and TheInput:GetHUDEntityUnderMouse()==nil then
            local extra=M.Describe(TheInput:GetWorldEntityUnderMouse())
            if extra and not string.find(str,extra,1,true) then
                -- 保留Show Me用于排版的尾部空行，把自身信息插在其前面。
                local body,padding=string.match(str,"^(.-)([\n ]*)$")
                str=body.."\n"..extra..padding
                added=1+select(2,string.gsub(extra,"\n",""))
            end
        end
        local result=original(text,str,...)
        if added>0 and type(text.cnt_lines)=="number" then text.cnt_lines=text.cnt_lines+added end
        return result
    end
end
return M
