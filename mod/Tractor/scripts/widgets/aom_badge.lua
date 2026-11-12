-- 与原版状态栏共用 Badge：液面、边框及警告均由原版绘制。
local Button=require("widgets/imagebutton")
local Badge=require("widgets/badge")
local Image=require("widgets/image")
local AOMBadge=Class(Button,function(self,owner,tint,health_icon)
    Button._ctor(self,"images/ui.xml","blank.tex")
    self:SetControl(CONTROL_PRIMARY)
    -- 点击/悬停范围覆盖圆形图标和下方数字牌。
    self:ForceImageSize(66,90)
    self.image:SetPosition(0,-8,0)
    self.image:SetTint(1,1,1,0)
    self.scale_on_focus=false
    self.clickoffset=Vector3(0,0,0)
    self.meter=self:AddChild(Badge(nil,owner,tint,health_icon and "status_health" or nil,nil,not health_icon,true))
    -- 只规范自己的Badge；综合状态显示会给所有Badge缩放并额外添加数字底板。
    self.meter:SetScale(1)
    if not health_icon then self.meter.backing:GetAnimState():SetMultColour(.38,.36,.3,1) end
    self.meter.OnGainFocus=function()end
    self.meter.OnLoseFocus=function()end
    self.meter.num:Hide()
    if self.meter.bg then self.meter.bg:Hide() end
    if self.meter.maxnum then self.meter.maxnum:Hide() end
    if not health_icon then self.meter.circleframe:GetAnimState():Hide("icon") end
    self.icon=self.meter:AddChild(Image())
    self.icon:SetClickable(false)
    if health_icon then self.icon:Hide() end
    self.plate=self:AddChild(Image("images/ui.xml","button_small.tex"))
    -- button_small自带上下透明留边；补足高度，让可见纸面完整承托数字。
    self.plate:ScaleToSize(58,32)
    self.plate:SetPosition(0,-40,0)
    self.plate:SetClickable(false)
    self.text:MoveToFront()
    self:SetFont(NUMBERFONT)
    self:SetTextSize(26)
    self:SetTextColour(1,1,1,1)
    self:SetTextFocusColour(1,.88,.5,1)
    self.text:SetPosition(0,-40,0)
    self.text:SetClickable(false)
end)
function AOMBadge:SetIcon(atlas,texture)
    if self.icon_atlas==atlas and self.icon_texture==texture then return end
    self.icon_atlas,self.icon_texture=atlas,texture
    self.icon:SetTexture(atlas,texture)
    self.icon:ScaleToSize(30,30)
    self.icon:Show()
end
function AOMBadge:SetValue(value,max,tip,display,warning,empty)
    local percent=max>0 and math.clamp(value/max,0,1) or 0
    self.meter:SetPercent(percent,max)
    self.meter.num:Hide()
    if self.meter.bg then self.meter.bg:Hide() end
    if self.meter.maxnum then self.meter.maxnum:Hide() end
    self:SetText(display or tostring(math.floor(value)))
    self:SetTooltip(tip)
    if empty then
        self.icon:SetTint(.45,.45,.45,1)
        self.meter:StopWarning()
    else
        self.icon:SetTint(1,1,1,1)
        if warning then self.meter:StartWarning(1,.1,.05,1)
        elseif self.warn_low~=false and max>0 and percent<=.2 then self.meter:StartWarning(1,.55,.1,1)
        else self.meter:StopWarning() end
    end
end
return AOMBadge
