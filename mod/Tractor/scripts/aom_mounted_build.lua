-- 只放宽拖拉机驾驶员放置农机配方的原版骑乘限制，制作与使用材料仍走 Builder。
local M={}
local recipes={}

function M.Allow(name)
    recipes[name]=true
end

function M.Install(builder)
    local build=builder.DoBuild
    builder.DoBuild=function(self,name,point,rotation,skin)
        local player=self.inst
        local rider=player.components.rider
        local tractor=recipes[name] and rider and rider:IsRiding() and rider:GetMount()
        if not tractor or not tractor:IsValid() or tractor.prefab~="aom_tractor_chassis" or tractor._rider~=player then
            return build(self,name,point,rotation,skin)
        end
        local recipe=GetValidRecipe(name)
        if not recipe or not point or not self:IsBuildBuffered(name)
            or not TheWorld.Map:CanDeployRecipeAtPoint(point,recipe,rotation,player) then
            return false
        end
        -- DoBuild 只在入口读取骑乘状态。该次读取后立即还原，后续制作回调看到真实骑乘状态。
        local override=rawget(rider,"IsRiding")
        rider.IsRiding=function()
            rider.IsRiding=override
            return false
        end
        local ok,built,reason=pcall(build,self,name,point,rotation,skin)
        rider.IsRiding=override
        if not ok then error(built,0) end
        return built,reason
    end
end

return M
