-- 固定坐标配比规划：每格养分独立平衡，逐株验证家族距离。
local AOMBlock = {}
local BLOCKS = require("aom_giant_layouts")
local Farm = require("aom_farm_work")
local BY_ID = {}
local CROP_CN = {carrot="胡萝卜",corn="玉米",potato="土豆",tomato="番茄",asparagus="芦笋",eggplant="茄子",pumpkin="南瓜",watermelon="西瓜",dragonfruit="火龙果",durian="榴莲",garlic="大蒜",onion="洋葱",pepper="辣椒",pomegranate="石榴"}
local VERSION = 2
local MATCH_DIST_SQ = .04
local function Key(x,z) return string.format("%.3f:%.3f",x,z) end
local function ValidNumber(v) return type(v)=="number" and v==v and math.abs(v)<1000000 end
local function Near(a,b) return (a.x-b.x)^2+(a.z-b.z)^2<=MATCH_DIST_SQ end
function AOMBlock.GetCropName(crop) return CROP_CN[crop] or crop end
function AOMBlock.BuildName(ratio)
    local parts={}
    for crop,n in pairs(ratio) do parts[#parts+1]=AOMBlock.GetCropName(crop)..n end
    table.sort(parts)
    return table.concat(parts," ")
end
for _,list in pairs(BLOCKS) do
    for _,combo in ipairs(list) do
        combo.name=AOMBlock.BuildName(combo.ratio);combo.total=0
        for _,n in pairs(combo.ratio) do combo.total=combo.total+n end
        BY_ID[combo.id]=combo
    end
    table.sort(list,function(a,b)
        if a.total~=b.total then return a.total<b.total end
        return a.id<b.id
    end)
end
AOMBlock.BLOCKS=BLOCKS

-- 按当前游戏的实际作物定义再次验证，避免升级或其他 Mod 改数值后仍误称免施肥。
function AOMBlock.ValidateCombo(combo,season)
    if not combo or combo.reference_only or not combo.slots then return false,"NO_LAYOUT" end
    local defs=require("prefabs/farm_plant_defs").PLANT_DEFS
    local tiles,counts,exempt={},{},{}
    for _,crop in ipairs(combo.not_giant or {}) do exempt[crop]=true end
    for _,slot in ipairs(combo.slots) do
        if not ValidNumber(slot.x) or not ValidNumber(slot.z) or math.abs(slot.x)>=2 or math.abs(slot.z)>=2 then return false,"INVALID_LAYOUT" end
        if slot.crop then
            local def=defs[slot.crop]
            if not def or not def.good_seasons or not def.good_seasons[season] then return false,"WRONG_SEASON" end
            counts[slot.crop]=(counts[slot.crop] or 0)+1
            local k=Key(slot.tx,slot.tz)
            local tile=tiles[k] or {net={0,0,0},count=0,positions={}}
            tiles[k]=tile;tile.count=tile.count+1
            if tile.count>(TUNING.FARM_PANT_OVERCROWDING_MAX_PLANTS or 10) then return false,"OVERCROWDED" end
            for _,p in ipairs(tile.positions) do
                if (p.x-slot.x)^2+(p.z-slot.z)^2<.99 then return false,"MOUNDS_TOO_CLOSE" end
            end
            tile.positions[#tile.positions+1]=slot
            local consume,restore=def.nutrient_consumption,def.nutrient_restoration
            if not consume or not restore then return false,"NO_NUTRIENT_DATA" end
            local total,types=0,0
            for n=1,3 do total=total+(consume[n] or 0);if restore[n] then types=types+1 end end
            if types==0 or total%types~=0 then return false,"UNSTABLE_NUTRIENTS" end
            for n=1,3 do tile.net[n]=tile.net[n]-(consume[n] or 0)+(restore[n] and total/types or 0) end
        end
    end
    for crop,n in pairs(combo.ratio) do if counts[crop]~=n then return false,"INVALID_COUNTS" end end
    for crop in pairs(counts) do if not combo.ratio[crop] then return false,"INVALID_COUNTS" end end
    for _,tile in pairs(tiles) do
        for _,n in ipairs(tile.net) do if math.abs(n)>.0001 then return false,"NUTRIENT_IMBALANCE" end end
    end
    for _,p in ipairs(combo.slots) do
        if p.crop and not exempt[p.crop] then
            local def=defs[p.crop]
            local radius=def.family_check_dist or 4
            local family=0
            for _,q in ipairs(combo.slots) do
                if p.crop==q.crop and ((p.tx-q.tx)*4+p.x-q.x)^2+((p.tz-q.tz)*4+p.z-q.z)^2<=radius^2 then family=family+1 end
            end
            if family<(def.family_min_count or 4) then return false,"NO_FAMILY" end
        end
    end
    return true
end
local function Remaining(block,combo)
    local counts={}
    for i,p in ipairs(combo.slots) do
        if p.crop and not block.completed[i] then counts[p.crop]=(counts[p.crop] or 0)+1 end
    end
    return counts
end
local function HasSeeds(counts,needs)
    for crop,n in pairs(needs) do if (counts[crop] or 0)<n then return false end end
    return true
end
function AOMBlock.ChooseCombo(season,seed_counts)
    for _,combo in ipairs(BLOCKS[season] or {}) do
        if HasSeeds(seed_counts,combo.ratio) and AOMBlock.ValidateCombo(combo,season) then return combo end
    end
end
local function Rotate(x,z,r)
    if r==1 then return -z,x elseif r==2 then return -x,-z elseif r==3 then return z,-x end
    return x,z
end
function AOMBlock.WorldSlots(block)
    local combo=BY_ID[block.combo_id]
    local slots,tiles={},{}
    for i,p in ipairs(combo.slots) do
        local dx,dz=Rotate(p.tx*4,p.tz*4,block.rotation)
        local ox,oz=Rotate(p.x,p.z,block.rotation)
        local cx,cz=block.x+dx,block.z+dz
        slots[i]={x=cx+ox,z=cz+oz,cx=cx,cz=cz,crop=p.crop,index=i}
        tiles[Key(cx,cz)]={x=cx,z=cz}
    end
    return slots,tiles
end
local function CheckField(block,preparing)
    local slots,tiles=AOMBlock.WorldSlots(block)
    local found={}
    for _,tile in pairs(tiles) do
        if not TheWorld.Map:IsPassableAtPoint(tile.x,0,tile.z) then return false,"INVALID_LAND" end
        if not preparing and TheWorld.Map:GetTileAtPoint(tile.x,0,tile.z)~=WORLD_TILES.FARMING_SOIL then return false,"NEED_PLOW" end
        for _,v in ipairs(TheWorld.Map:GetEntitiesOnTileAtPoint(tile.x,0,tile.z)) do
            local clearable=preparing and Farm.IsClearableDebris(v)
            if v:IsValid() and not clearable and (v:HasTag("farm_plant") or v:HasTag("weed") or v.prefab=="farm_soil_debris") then
                local x,_,z=v.Transform:GetWorldPosition()
                local matched=false
                for i,p in ipairs(slots) do
                    if p.crop and block.completed[i] and v.prefab=="farm_plant_"..p.crop and Near(p,{x=x,z=z}) then
                        if found[i] then return false,"FOREIGN_CROP" end
                        found[i]={x=x,z=z,crop=p.crop};matched=true;break
                    end
                end
                if not matched then return false,"FOREIGN_CROP" end
            end
        end
    end
    for i in pairs(block.completed) do if not found[i] then return false,"PLANT_MISSING" end end
    return true,nil,found
end
local function NewBlock(combo,season,x,z,r)
    return {version=VERSION,combo_id=combo.id,season=season,x=x,z=z,rotation=r,completed={},done=0}
end
function AOMBlock.ResetBlock(inst) inst._block=nil end

-- 先检查整套余料及真实场地，再返回本格目标；调用方不得降级为顺序播种。
function AOMBlock.GetTargets(inst,season,seed_counts,cx,cz,preparing)
    if not inst._block then
        local has_candidate=false
        local blocked_reason="INVALID_LAND"
        for _,combo in ipairs(BLOCKS[season] or {}) do
            if HasSeeds(seed_counts,combo.ratio) and AOMBlock.ValidateCombo(combo,season) then
                has_candidate=true
                for r=0,3 do
                    local candidate=NewBlock(combo,season,cx,cz,r)
                    local clear,why=CheckField(candidate,true)
                    if clear then inst._block=candidate;break end
                    blocked_reason=why
                end
                if inst._block then break end
            end
        end
        if not inst._block then return nil,has_candidate and blocked_reason or "MISSING_SEEDS" end
    end
    local block=inst._block
    local combo=BY_ID[block.combo_id]
    -- 整片收获完毕后，换开垦机可以开始下一轮；不能在尚有作物时填掉留空位。
    if preparing and block.done>=combo.total then
        local _,tiles=AOMBlock.WorldSlots(block)
        local empty=true
        for _,tile in pairs(tiles) do
            for _,v in ipairs(TheWorld.Map:GetEntitiesOnTileAtPoint(tile.x,0,tile.z)) do
                if v:IsValid() and not Farm.IsClearableDebris(v)
                    and (v:HasTag("farm_plant") or v:HasTag("weed") or v.prefab=="farm_soil_debris") then empty=false end
            end
        end
        if empty then
            AOMBlock.ResetBlock(inst)
            return AOMBlock.GetTargets(inst,season,seed_counts,cx,cz,preparing)
        end
    end
    if block.season~=season then return nil,"SEASON_CHANGED" end
    local valid,reason=AOMBlock.ValidateCombo(combo,season)
    if not valid then return nil,reason end
    local slots,tiles=AOMBlock.WorldSlots(block)
    if not tiles[Key(cx,cz)] then return nil,"NEXT_TILE" end
    if block.done>=combo.total then return nil,"COMPLETE" end
    if not HasSeeds(seed_counts,Remaining(block,combo)) then return nil,"MISSING_SEEDS" end
    local field_ok,field_reason,positions=CheckField(block,preparing)
    if not field_ok then return nil,field_reason end
    -- 全部地块都准备好才开种，降低两边生长阶段相差过大的风险。
    if not preparing then
        for i,p in ipairs(slots) do
            if p.crop and not block.completed[i] then
                local soil=AOMBlock.FindSoilAt(p.x,p.z)
                if not soil then return nil,"NEED_PLOW" end
                local sx,_,sz=soil.Transform:GetWorldPosition()
                positions[i]={x=sx,z=sz,crop=p.crop}
            end
        end
    end
    -- 手工土坑可能略有偏移：还要检查实际坑位/已种作物，而不是只信任模板坐标。
    if not preparing then
        local defs=require("prefabs/farm_plant_defs").PLANT_DEFS
        local exempt={}
        for _,crop in ipairs(combo.not_giant) do exempt[crop]=true end
        for _,p in pairs(positions) do
            if not exempt[p.crop] then
                local family=0
                local def=defs[p.crop]
                for _,q in pairs(positions) do
                    if q.crop==p.crop and (p.x-q.x)^2+(p.z-q.z)^2<=(def.family_check_dist or 4)^2 then family=family+1 end
                end
                if family<(def.family_min_count or 4) then return nil,"NO_FAMILY" end
            end
        end
    end
    -- 初始养分需足以承担本格一轮消耗；免追加施肥不等于贫瘠土地也能开种。
    if not preparing and block.done==0 then
        local defs=require("prefabs/farm_plant_defs").PLANT_DEFS
        local needs={}
        for _,p in ipairs(slots) do
            if p.crop then
                local key=Key(p.cx,p.cz)
                local t=needs[key] or {x=p.cx,z=p.cz,n={0,0,0}}
                needs[key]=t
                for j=1,3 do t.n[j]=t.n[j]+(defs[p.crop].nutrient_consumption[j] or 0) end
            end
        end
        local manager=TheWorld.components.farming_manager
        if not manager then return nil,"LOW_NUTRIENTS" end
        for _,t in pairs(needs) do
            local tx,tz=TheWorld.Map:GetTileCoordsAtPoint(t.x,0,t.z)
            local current={manager:GetTileNutrients(tx,tz)}
            for j=1,3 do if (current[j] or 0)<t.n[j] then return nil,"LOW_NUTRIENTS" end end
        end
    end
    local targets={}
    for i,p in ipairs(slots) do
        if p.crop and not block.completed[i] and Key(p.cx,p.cz)==Key(cx,cz) then targets[#targets+1]=p end
    end
    if #targets==0 then return nil,"NEXT_TILE" end
    return targets
end
function AOMBlock.FindSoilAt(x,z)
    for _,v in ipairs(TheSim:FindEntities(x,0,z,.2,{"soil"},{"NOCLICK","INLIMBO"})) do
        if v.prefab=="farm_soil" and v:IsValid() then return v end
    end
end
function AOMBlock.RecordPlanted(inst,target)
    local block=inst._block
    if not block or not target or block.completed[target.index] then return false end
    local expected=AOMBlock.WorldSlots(block)[target.index]
    if not expected or expected.crop~=target.crop or not Near(expected,target) then return false end
    block.completed[target.index]=true;block.done=block.done+1
    return true
end
function AOMBlock.OnSave(inst)
    local b=inst._block
    if not b then return nil end
    local completed={}
    for i in pairs(b.completed) do completed[#completed+1]=i end
    table.sort(completed)
    return {version=VERSION,combo_id=b.combo_id,season=b.season,x=b.x,z=b.z,rotation=b.rotation,completed=completed}
end
function AOMBlock.OnLoad(inst,data)
    -- 旧版只有总株数，无法推断真实位置；不把旧计数迁移进新地图。
    if not data or data.version~=VERSION or not BY_ID[data.combo_id] then return end
    if not ValidNumber(data.x) or not ValidNumber(data.z) or type(data.rotation)~="number" or data.rotation%1~=0 or data.rotation<0 or data.rotation>3 then return end
    local combo=BY_ID[data.combo_id]
    if not AOMBlock.ValidateCombo(combo,data.season) then return end
    local b=NewBlock(combo,data.season,data.x,data.z,data.rotation)
    for _,i in ipairs(data.completed or {}) do
        if type(i)~="number" or i%1~=0 or not combo.slots[i] or not combo.slots[i].crop or b.completed[i] then return end
        b.completed[i]=true;b.done=b.done+1
    end
    inst._block=b
end
function AOMBlock.DescribeProgress(inst)
    local b=inst._block
    if not b then return "配比：待规划" end
    local combo=BY_ID[b.combo_id]
    local text=string.format("%s %d/%d",combo.name,b.done,combo.total)
    if #combo.not_giant>0 then
        local names={}
        for _,crop in ipairs(combo.not_giant) do names[#names+1]=AOMBlock.GetCropName(crop) end
        text=text.."（"..table.concat(names,"、").."不保证巨大化）"
    end
    return text
end
return AOMBlock
