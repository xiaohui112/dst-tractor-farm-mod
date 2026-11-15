-- Test-only: local DST r762172 player_common.GetTalkerOffset and FollowText.OnUpdate.
local FollowText={}
local TALLER_TALKER_OFFSET = Vector3(0, -700, 0)
local DEFAULT_TALKER_OFFSET = Vector3(0, -400, 0)
local function GetTalkerOffset(inst)
    local rider = inst.replica.rider
    return (rider ~= nil and rider:IsRiding() or inst:HasTag("playerghost"))
        and TALLER_TALKER_OFFSET
        or DEFAULT_TALKER_OFFSET
end

function FollowText:SetOffset(offset)
    self.offset = offset
    self:OnUpdate()
end

function FollowText:SetScreenOffset(x,y)
    self.screen_offset.x = x
    self.screen_offset.y = y
    self:OnUpdate()
end

function FollowText:GetScreenOffset()
    return self.screen_offset.x, self.screen_offset.y
end

function FollowText:OnUpdate(dt)
    if self.target ~= nil and self.target:IsValid() then
        if not self.hashud then
            --legacy support for MODs
            self.text:SetScale(TheFrontEnd:GetHUDScale())
        end
        local x, y
        if self.target.AnimState ~= nil then
            x, y = TheSim:GetScreenPos(self.target.AnimState:GetSymbolPosition(self.symbol or "", self.offset.x, self.offset.y, self.offset.z))
        else
            x, y = TheSim:GetScreenPos(self.target.Transform:GetWorldPosition())
        end
        self:SetPosition(x + self.screen_offset.x, y + self.screen_offset.y, 0)
    end
end


return {GetTalkerOffset=GetTalkerOffset,OnUpdate=FollowText.OnUpdate,
    SetOffset=FollowText.SetOffset,SetScreenOffset=FollowText.SetScreenOffset,GetScreenOffset=FollowText.GetScreenOffset}
