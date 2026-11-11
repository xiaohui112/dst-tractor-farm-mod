-- 农田按需施肥：肥料留在原容器，养分与每次消耗沿用原版组件。
local M={TARGET=100}
local function Number(n) return type(n)=="number" and n==n and n>=0 and n<math.huge end

function M.Doses(item)
    if not item or not item:IsValid() or not item.components.fertilizer then return 0 end
    local uses=item.components.finiteuses
    local n=uses and uses:GetUses() or 1
    if not Number(n) then return 0 end
    local stack=item.components.stackable
    return math.ceil(n)*(stack and stack:StackSize() or 1)
end

function M.Read(x,z)
    local farm=require("aom_farm_work")
    local ok,a,b,c=pcall(function()
        if not farm.IsFarmTileAt(x,0,z) then return nil,"NOTHING_TO_DO" end
        local tx,tz=TheWorld.Map:GetTileCoordsAtPoint(x,0,z)
        return TheWorld.components.farming_manager:GetTileNutrients(tx,tz)
    end)
    if ok and a==nil and b=="NOTHING_TO_DO" then return nil,b end
    if not ok or not Number(a) or not Number(b) or not Number(c) then return nil,"NUTRIENTS_UNAVAILABLE" end
    return {math.min(M.TARGET,a),math.min(M.TARGET,b),math.min(M.TARGET,c)}
end

function M.Full(n)
    return n[1]>=M.TARGET and n[2]>=M.TARGET and n[3]>=M.TARGET
end

function M.Gain(item,n)
    if M.Doses(item)<=0 then return 0,0 end
    local nutrients=item.components.fertilizer.nutrients
    if type(nutrients)~="table" then return 0,0 end
    local gain,total=0,0
    for i=1,3 do
        local amount=nutrients[i] or 0
        if not Number(amount) then return 0,0 end
        total=total+amount
        gain=gain+math.min(amount,M.TARGET-n[i])
    end
    return gain,total
end

function M.Select(store,n)
    local best,efficiency,bestgain=nil,-1,-1
    for _,item in ipairs(store:ListFertilizers()) do
        local gain,total=M.Gain(item,n)
        if gain>0 then
            local ratio=gain/total
            if ratio>efficiency or ratio==efficiency and gain>bestgain then
                best,efficiency,bestgain=item,ratio,gain
            end
        end
    end
    return best
end

-- 先确认实际养分增加，再且仅再调用一次原版 OnApplied；不预先拆走多次用量物品。
function M.Apply(x,z,doer,item,quiet)
    local before,reason=M.Read(x,z)
    if not before then return false,reason end
    if M.Gain(item,before)<=0 then return false,"NOTHING_TO_DO" end
    local fm=TheWorld.components.farming_manager
    local nutrients=item.components.fertilizer.nutrients
    local tx,tz=TheWorld.Map:GetTileCoordsAtPoint(x,0,z)
    local added=pcall(fm.AddTileNutrients,fm,tx,tz,nutrients[1] or 0,nutrients[2] or 0,nutrients[3] or 0)
    local after=M.Read(x,z)
    local changed=not after or after[1]>before[1] or after[2]>before[2] or after[3]>before[3]
    if not changed then return false,"FERTILIZER_FAILED" end
    -- 即使加养分后的其他回调抛错，已发生的改动也应结算一份真实肥料。
    local consumed=pcall(item.components.fertilizer.OnApplied,item.components.fertilizer,doer,nil)
    if not after then return true,"NUTRIENTS_UNAVAILABLE" end
    if not consumed or not added then return true,"FERTILIZER_FAILED" end
    -- 与原版肥料部署一致的音效和附加回调；不能调用手持 Deploy（骑乘时原版拒绝）。
    if not quiet and doer and doer.SoundEmitter and item.components.fertilizer.fertilize_sound then
        pcall(doer.SoundEmitter.PlaySound,doer.SoundEmitter,item.components.fertilizer.fertilize_sound)
    end
    if item.ondeployed_fertilzier_extra_fn then
        local ok=pcall(item.ondeployed_fertilzier_extra_fn,item,Vector3(x,0,z),doer)
        if not ok then return true,"FERTILIZER_FAILED" end
    end
    return true
end

local function Missing(inst,n)
    local names={"生长素","堆肥","粪肥"}
    local missing={}
    for i=1,3 do if n[i]<M.TARGET then missing[#missing+1]=names[i] end end
    inst._fertilizer_missing_text="缺少可补充"..table.concat(missing,"、").."的肥料，请补料后按 F 继续"
end

function M.WorkTile(inst,x,z)
    local n,reason=M.Read(x,z)
    if not n then return false,reason,reason=="NOTHING_TO_DO" end
    if M.Full(n) then return false,"NOTHING_TO_DO",true end
    if inst._fuel:value()<require("aom_common").FUEL_PER_TICK then return false,"NO_FUEL",false end
    local store=inst.components.aom_attachment_store
    local changed,played=false,false
    -- 原版三类养分按整数存储；每次必须至少增加1点，最多需3*100份。
    for _=1,3*M.TARGET do
        local item=M.Select(store,n)
        if not item then Missing(inst,n);return changed,"FERTILIZER_MISSING",false end
        local sound=item.components.fertilizer.fertilize_sound
        local worked,why=M.Apply(x,z,inst._rider,item,true)
        if worked then
            changed=true
            local rider=inst._rider
            if not played and sound and rider and rider.SoundEmitter then
                pcall(rider.SoundEmitter.PlaySound,rider.SoundEmitter,sound)
                played=true
            end
        end
        M.Sync(inst)
        if not worked or why then return changed,why or "FERTILIZER_FAILED",false end
        n,reason=M.Read(x,z)
        if not n then return changed,reason,false end
        if M.Full(n) then inst._fertilizer_missing_text=nil;return true,nil,true end
    end
    return changed,"FERTILIZER_FAILED",false
end

function M.Sync(inst)
    local store=inst.components.aom_attachment_store
    if not store then return end
    if inst._fertilizeruses_net then inst._fertilizeruses_net:set(store:GetFertilizerCount()) end
    if inst._fertilizerstock_net then
        local counts,order={},{}
        for _,item in ipairs(store:ListFertilizers()) do
            local key=item.prefab
            if not counts[key] then counts[key]=0;order[#order+1]=key end
            counts[key]=counts[key]+M.Doses(item)
        end
        local labels={}
        for i=1,math.min(3,#order) do
            local key=order[i]
            local name=STRINGS and STRINGS.NAMES and STRINGS.NAMES[string.upper(key)] or key
            labels[#labels+1]=name.." "..counts[key].."次"
        end
        if #order>3 then labels[#labels+1]="等"..#order.."种" end
        inst._fertilizerstock_net:set(table.concat(labels,"；"))
    end
end

function M.Watch(inst)
    for _,item in ipairs(inst._fertilizer_watched or {}) do
        inst:RemoveEventCallback("percentusedchange",M.Sync,item)
    end
    inst._fertilizer_watched={}
    local store=inst.components.aom_attachment_store
    if store then
        for _,item in ipairs(store:ListFertilizers()) do
            inst:ListenForEvent("percentusedchange",M.Sync,item)
            inst._fertilizer_watched[#inst._fertilizer_watched+1]=item
        end
    end
    M.Sync(inst)
end

return M
