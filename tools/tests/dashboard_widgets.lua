-- 图形引擎表面为桩；实际执行本机 Badge、Button、ImageButton、NineSlice、UIAnim。
CONTROL_PRIMARY=0;CONTROL_ACCEPT=29;ANCHOR_LEFT=0;ANCHOR_RIGHT=2;ANCHOR_MIDDLE=1;ANCHOR_TOP=2;ANCHOR_BOTTOM=0
ValidateLineNumber=noop
NEWFONT='newfont';BODYTEXTFONT='body';NUMBERFONT='number'
STRINGS.UI={HELP={SELECT='Select'}}
package.preload.constants=function()return {}end
package.preload.easing=function()return {}end
function GetInventoryItemAtlas(texture)
 if texture=='gears.tex' or texture=='onemanband.tex' then return 'images/inventoryimages2.xml' end
 if texture=='charcoal.tex' then return 'images/inventoryimages1.xml' end
 return 'images/inventoryimages3.xml'
end
TheInput.ResolveVirtualControls=function(_,control)return control==CONTROL_ACCEPT and CONTROL_PRIMARY or control end
TheFrontEnd.isprimary=true
TheFrontEnd.GetFadeLevel=function()return 0 end
TheFrontEnd.GetSound=function()return {PlaySound=noop}end
function ClickMouseoverSoundReduction()return 1 end
local old_vector=Vector3
function Vector3(x,y,z)
 return setmetatable(old_vector(x,y,z),{__add=function(a,b)return Vector3(a.x+b.x,a.y+b.y,a.z+b.z)end})
end
local function animation()
 local a={}
 for _,name in ipairs({'SetBank','SetBuild','PlayAnimation','SetPercent','SetMultColour','Hide','OverrideSymbol','AnimateWhilePaused'})do
  a[name]=function(self,...)self[name..'_args']={...}end
 end
 function a:GetCurrentAnimationLength()return .1 end
 return a
end
local Widget=Class(function(self,name)
 self.name=name;self.visible=true;self.shown=true;self.enabled=true;self.children={};self.focus=false
 self.inst={entity={AddAnimState=noop},AnimState=animation(),IsValid=function()return true end,
  DoTaskInTime=function(_,delay,fn)return {Cancel=noop,fn=fn}end}
end)
function Widget:AddChild(child)self.children[child]=true;child.widget_parent=self;return child end
function Widget:SetPosition(x,y,z)
 if type(x)=='table'then self.position={x.x,x.y,x.z}else self.position={x,y,z or 0}end
end
local function ui_vector(x,y,z)
 local v={x=x,y=y,z=z}
 return setmetatable(v,{__add=function(a,b)return ui_vector(a.x+b.x,a.y+b.y,a.z+b.z)end,
  __sub=function(a,b)return ui_vector(a.x-b.x,a.y-b.y,a.z-b.z)end})
end
function Widget:GetLocalPosition()return ui_vector(unpack(self.position or {0,0,0}))end
function Widget:SetScale(x,y,z)self.scale={x,y or x,z or x}end
function Widget:GetLooseScale()return Vector3(unpack(self.scale or {1,1,1}))end
function Widget:SetTooltip(t)self.tooltip=t end
function Widget:GetTooltip()return self.tooltip end
function Widget:SetClickable(v)self.clickable=v end
function Widget:Hide()
 self.visible=false;self.shown=false;self.hide_count=(self.hide_count or 0)+1
 if self.focus then self:OnLoseFocus();self.focus=false end
end
function Widget:Show()self.visible=true;self.shown=true end
function Widget:IsVisible()return self.visible and (not self.widget_parent or self.widget_parent:IsVisible())end
function Widget:OnGainFocus()self.focus=true end
function Widget:OnLoseFocus()self.focus=false end
function Widget:IsEnabled()return self.enabled end
function Widget:OnControl()return false end
function Widget:UpdateWhilePaused(v)self.update_while_paused=v end
function Widget:MoveToFront()self.moved_front=true end
function Widget:MoveToBack()end
function Widget:StartUpdating()end
function Widget:StopUpdating()end
Widget.SetHAlign=noop;Widget.SetVAlign=noop;Widget.SetFont=noop
Widget.SetHAnchor=noop;Widget.SetVAnchor=noop;Widget.SetHRegPoint=noop;Widget.SetVRegPoint=noop
local Text=Class(Widget,function(self,font,size,text)Widget._ctor(self,'Text');self.size=size;self:SetString(text or '')end)
function Text:SetString(text)self.text=text end
function Text:GetString()return self.text end
function Text:SetSize(size)self.size=size end
function Text:SetColour(...)self.colour={...}end
local Image=Class(Widget,function(self,atlas,texture)Widget._ctor(self,'Image');self:SetTexture(atlas,texture)end)
function Image:SetTexture(atlas,texture)self.atlas=atlas;self.texture=texture end
function Image:SetSize(w,h)self.size={w,h}end
function Image:GetSize()return unpack(self.size or {20,20})end
function Image:ScaleToSize(w,h)self.render_size={w,h}end
function Image:SetTint(...)self.tint={...}end
package.preload['widgets/widget']=function()return Widget end
package.preload['widgets/text']=function()return Text end
package.preload['widgets/image']=function()return Image end
package.preload['widgets/textbutton']=function()return Text end
for _,name in ipairs({'uianim','button','imagebutton','badge','nineslice'})do
 package.preload['widgets/'..name]=function()return dofile(REF..'/widget_'..name..'.lua')end
end
