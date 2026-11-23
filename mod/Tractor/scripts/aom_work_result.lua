-- 一次结算单位的实际进度。只记录已发生的农业改动，拾取不计费。
local M={}
-- 结算和展示分别保护；一个回调失败不能跳过后续独立结算。
function M.Protect(result,fn)
    local ok,err=pcall(fn)
    if not ok then
        result.error=result.error and (result.error.."; "..tostring(err)) or tostring(err)
        result.reason="WORK_ERROR";result.complete=false
    end
    return ok
end
function M.Mark(vehicle)
    local result=vehicle and vehicle._aom_work_result
    if result then result.changed=true end
end
function M.MarkAt(vehicle,x,z)
    local result=vehicle and vehicle._aom_work_result
    if result then
        result.changed=true
        result.position=result.position or {x=x,z=z}
    end
end
-- 原版回调可能在改动实体后抛错；无论是否抛错，都先观察真实结果。
function M.Observe(vehicle,fn,changed)
    local ok,a,b,c=pcall(fn)
    if changed() then M.Mark(vehicle) end
    if not ok then error(a,0) end
    return a,b,c
end
function M.Run(vehicle,fn)
    local result={changed=false,complete=false}
    local previous=vehicle._aom_work_result
    vehicle._aom_work_result=result
    local ok,changed,reason,complete,position=pcall(fn)
    vehicle._aom_work_result=previous
    if ok then
        result.changed=result.changed or changed or false
        result.reason=reason;result.complete=complete~=false;result.position=position or result.position
    else
        result.reason="WORK_ERROR";result.error=tostring(changed)
    end
    return result
end
return M
