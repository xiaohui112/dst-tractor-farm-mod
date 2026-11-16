-- 前台规划软额度由房主配置；后台预计算保持低额度。
local M={}
local allowed={[2]=true,[4]=true,[8]=true,[12]=true,[16]=true,[24]=true,[32]=true}
function M.Milliseconds(background)
 if background then return 1 end
 local config=rawget(_G,'AOM_CONFIG')
 local value=type(config)=='table' and tonumber(config.PLAN_CPU_BUDGET_MS) or nil
 return allowed[value] and value or 16
end
return M
