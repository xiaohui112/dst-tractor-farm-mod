-- 常驻仅图标和数值；说明走原版 Hoverer。客户端仅读 netvar/replica。
local Widget=require("widgets/widget")
local Image=require("widgets/image")
local ImageButton=require("widgets/imagebutton")
local Text=require("widgets/text")
local NineSlice=require("widgets/nineslice")
local Dial=require("widgets/aom_badge")
local L=require("aom_locale").Text
local ATT={}
for kind,def in pairs(require("aom_equipment_defs")) do ATT[kind]=def.prefab end
local MODE={SEQUENTIAL="顺序",RANDOM="随机",GIANT="配比"}
local NEXT={SEQUENTIAL="RANDOM",RANDOM="GIANT",GIANT="SEQUENTIAL"}
local EFFECT={plow="铺农田、清杂物、整理九宫格；掉落自动入仓",seeder="播种空坑；切换策略后按 F 重新开始",irrigator="按需浇水；驾驶到池塘边右键补满水箱",fertilizer="按需自动选肥并切换；悬停查看剩余肥料",weeder="清理杂草与残渣；掉落自动入仓",harvester="收割成熟作物、拆分巨大作物；产物自动入仓"}
local function Value(inst,key,default)
    local net=inst and inst[key]
    if net then return net:value() end
    return default
end
local function ItemImage(name)return GetInventoryItemAtlas(name..".tex"),name..".tex" end
local function SetLamp(image,on,blocked)
    image:SetTexture("images/ui.xml",(on or blocked) and "radiobutton_on.tex" or "radiobutton_off.tex")
    image:ScaleToSize(18,18)
    image:SetTint(blocked and 1 or on and .45 or .5,blocked and .15 or on and 1 or .5,blocked and .05 or on and .15 or .5,1)
end
local function Visible(widget,on)
    if widget._aom_visible~=on then
        widget._aom_visible=on
        if on then widget:Show()else widget:Hide()end
    end
end
local AOMHud=Class(Widget,function(self,owner)
    Widget._ctor(self,"AOMHud")
    self.owner=owner
    self.root=self:AddChild(Widget("tractor_dashboard"))
    self.root:SetPosition(0,150,0)
    self.badges={}
    local colors={health={174/255,21/255,21/255,1},chassis={.8,.55,.12,1},fuel={.8,.37,.08,1},tool={.12,.48,.46,1},cargo={.4,.4,.2,1}}
    self.order={"health","chassis","fuel","tool","cargo"}
    for _,key in ipairs(self.order)do self.badges[key]=self.root:AddChild(Dial(owner,colors[key],key=="health"))end
    self.badges.chassis:SetIcon(ItemImage("gears"))
    self.badges.fuel:SetIcon(ItemImage("charcoal"))
    self.badges.cargo:SetIcon(ItemImage("treasurechest"))
    self.badges.cargo.warn_low=false
    self.badges.cargo:SetOnClick(function()self:Send(AOM_RPC.STORAGE)end)
    self.strip=self.root:AddChild(Widget("equipment_controls"))
    self.strip:SetPosition(0,-42,0)
    self.background=self.strip:AddChild(NineSlice("images/dialogrect_9slice.xml"))
    self.background:SetSize(488,22)
    self.background:SetScale(.14,.14)
    self.background:SetClickable(false)
    self.attachment_icon=self.strip:AddChild(Image())
    self.attachment_icon:SetPosition(-226,0,0)
    self.resource=self.strip:AddChild(Widget("resource"))
    self.resource:SetPosition(-70,0,0)
    self.resource_num=self.resource:AddChild(Text(NUMBERFONT,24,""))
    self.resource_num:SetPosition(-42,0,0)
    self.resource_frame=self.resource:AddChild(Image("images/global_redux.xml","progressbar_wxplarge_frame.tex"))
    self.resource_frame:ScaleToSize(100,18)
    self.resource_frame:SetPosition(58,0,0)
    self.resource_fill=self.resource:AddChild(Image("images/global_redux.xml","progressbar_wxplarge_fill.tex"))
    self.resource_fill:SetTint(.2,.65,1,1)
    self.resource_frame:MoveToFront()
    self.seedbutton=self.strip:AddChild(ImageButton("images/ui.xml","spin_arrow.tex","spin_arrow_over.tex",nil,"spin_arrow_down.tex"))
    self.seedbutton:ForceImageSize(28,28)
    self.seedbutton:SetPosition(155,0,0)
    self.seedbutton:SetOnClick(function()self:Send(AOM_RPC.SEED_MODE)end)
    self.planbutton=self.strip:AddChild(ImageButton("images/ui.xml","button_small.tex"))
    self.planbutton:ForceImageSize(62,28);self.planbutton:SetTextSize(20)
    self.planbutton:SetPosition(90,0,0)
    self.planbutton:SetOnClick(function()self:Send(AOM_RPC.PLAN)end)
    self.rotatebutton=self.strip:AddChild(ImageButton("images/ui.xml","spin_arrow.tex","spin_arrow_over.tex",nil,"spin_arrow_down.tex"))
    self.rotatebutton:ForceImageSize(24,24);self.rotatebutton:SetPosition(40,0,0)
    self.rotatebutton:SetOnClick(function()self:Send(AOM_RPC.PLAN_ROTATE)end)
    self.music_icon=self.strip:AddChild(Image(ItemImage("onemanband")))
    self.music_icon:ScaleToSize(26,26)
    self.music_icon:SetPosition(128,0,0)
    self.music_icon:SetClickable(false)
    self.musicbutton=self.strip:AddChild(ImageButton("images/ui.xml","radiobutton_on.tex"))
    self.musicbutton:ForceImageSize(22,22)
    self.musicbutton:SetPosition(163,0,0)
    self.musicbutton.scale_on_focus=false
    self.musicbutton:SetOnClick(function()
        if Value(self.tractor,"_music_available_net",false)then
            self:Send(AOM_RPC.MUSIC,not Value(self.tractor,"_music_enabled_net",true))
        end
    end)
    self.worklamp=self.strip:AddChild(Image("images/ui.xml","radiobutton_off.tex"))
    self.worklamp:SetPosition(225,0,0)
    self:MatchStatusScale()
    self:Hide()
end)
function AOMHud:MatchStatusScale()
    local controls=self.owner.HUD and self.owner.HUD.controls
    local status=controls and controls.status
    local scale=status and status:GetLooseScale().x or 1.4
    -- 原版 Controls 的 StatusDisplays 倍率为1.4；共用表盘原始尺寸。
    for i,key in ipairs(self.order)do
        self.badges[key]:SetScale(scale)
        self.badges[key]:SetPosition((i-3)*78*scale,40,0)
    end
end
function AOMHud:Send(rpc,...)
    local rider=self.owner.replica and self.owner.replica.rider
    local tractor=rider and rider:IsRiding() and rider:GetMount()
    if self.tractor and self.tractor:IsValid() and tractor==self.tractor
        and tractor.prefab=="aom_tractor_chassis" and not self.owner:HasTag("playerghost")then
        SendModRPCToServer(rpc,...)
    end
end
function AOMHud:Refresh(tractor)
    require("aom_plan_preview").Refresh(self,tractor)
    if not tractor or not tractor:IsValid() or self.owner:HasTag("playerghost")then self.tractor=nil;self:Hide();return end
    self.tractor=tractor
    self:MatchStatusScale()
    local hp=Value(tractor,"_health_net",600)
    local uses=Value(tractor,"_uses_net",0)
    local fuel=Value(tractor,"_fuel",0)
    local kind=Value(tractor,"_atttype_net","")
    local name=ATT[kind]
    local att=name and (STRINGS.NAMES[string.upper(name)] or name) or L("无挂件")
    local tool=Value(tractor,"_tooluses_net",0)
    local max=Value(tractor,"_toolmax_net",0)
    local cargo=Value(tractor,"_cargo_used_net",0)
    local code=require("aom_work_status").Read(tractor)
    local reason=require("aom_work_status").Describe(tractor)
    self.badges.health:SetValue(hp,600,L("车体生命 %d/%d",math.ceil(hp),600).."\n"..L("齿轮修复生命和底盘耐久；生命归零留下残骸"),tostring(math.ceil(hp)),hp<=0)
    self.badges.chassis:SetValue(uses,1000,L("底盘 %d/%d",uses,1000).."\n"..L("齿轮每份恢复100；耐久归零停止作业"),nil,uses<=0)
    self.badges.fuel:SetValue(fuel,800,L("燃料 %d/%d",fuel,800).."\n"..L("下车手持木头、木炭等燃料右键加油"),nil,fuel<=0)
    if name then self.badges.tool:SetIcon("images/aom_attachment_inventory.xml",name..".tex")else self.badges.tool:SetIcon(ItemImage("gears"))end
    local tool_tip=max>0 and att.."\n"..L("挂件耐久 %d/%d",tool,max).."\n"..L("下车手持燧石维修；每份恢复10") or att
    self.badges.tool:SetValue(tool,max,tool_tip,max<=0 and "—" or nil,max>0 and tool<=0,max<=0)
    local full=code=="CARGO_FULL"
    local storage=tractor.replica and tractor.replica.container
    local opened=storage and storage:IsOpenedBy(self.owner)
    local cargo_tip=L("货仓：%d/9格",cargo).."\n"..L("左键：打开/关闭货仓；也可左键车身")
    if full then cargo_tip=cargo_tip.."\n"..reason
    elseif cargo==9 then cargo_tip=cargo_tip.."\n"..L("格子已占用，同类物品仍可叠堆")end
    self.badges.cargo:SetValue(cargo,9,cargo_tip,tostring(cargo).."/9",full)
    self.badges.cargo.icon:SetTint(opened and 1 or .85,opened and .85 or .85,opened and .5 or .85,1)
    if name then
        self.attachment_icon:SetTexture("images/aom_attachment_inventory.xml",name..".tex")
        self.attachment_icon:ScaleToSize(32,32)
        self.attachment_icon:SetTooltip(att.."\n"..L(EFFECT[kind]))
        self.attachment_icon:Show()
    else self.attachment_icon:Hide()end
    Visible(self.seedbutton,kind=="seeder")
    Visible(self.musicbutton,kind=="irrigator")
    Visible(self.music_icon,kind=="irrigator")
    Visible(self.resource,kind=="irrigator" or kind=="seeder" or kind=="fertilizer")
    local mode=Value(tractor,"_seedmode_net","SEQUENTIAL")
    local block=require("aom_block_plan")
    local plan=block.Decode(Value(tractor,"_plan_net",""))
    Visible(self.planbutton,kind=="seeder" and mode=="GIANT")
    Visible(self.rotatebutton,kind=="seeder" and mode=="GIANT" and plan~=nil and plan.confirmed==false)
    self.planbutton:SetText(L(not plan and "预览" or plan.confirmed==false and "确认" or "重规划"))
    self.planbutton:SetTooltip(block.DescribePreview(plan))
    self.rotatebutton:SetTooltip(L("旋转预览90°；不会改动农田"))
    local current,capacity=0,0
    if kind=="irrigator"then
        current,capacity=Value(tractor,"_water_net",0),Value(tractor,"_watermax_net",40)
        self.resource_num:SetString(tostring(current).."/"..tostring(capacity))
        self.resource:SetTooltip(L("水箱 %d/%d 次水壶用量",current,capacity).."\n"..L("补水：驾驶到池塘边，右键池塘补满水箱"))
        local available=Value(tractor,"_music_available_net",false)
        local enabled=Value(tractor,"_music_enabled_net",true)
        local on=available and enabled
        if self._music_on~=on then
            self._music_on=on
            self.musicbutton:SetTextures("images/ui.xml",on and "radiobutton_on.tex" or "radiobutton_off.tex")
            self.musicbutton:ForceImageSize(22,22)
        end
        self.musicbutton.image:SetTint(available and .6 or .4,available and 1 or .4,.3,1)
        self.musicbutton:SetTooltip(not available and L("音乐安抚不可用：世界设置已关闭或音频资源缺失")
            or L("音乐安抚：%s",enabled and L("开启") or L("关闭")).."\n"..L("点击切换音乐和植物安抚；洒水持续进行"))
    elseif kind=="seeder"then
        current=Value(tractor,"_seedcount_net",0)
        self.resource_num:SetString(tostring(current))
        local mode=Value(tractor,"_seedmode_net","SEQUENTIAL")
        local tip=L("播种策略：%s",L(MODE[mode] or "顺序")).."\n"..L("点击切换为：%s",L(MODE[NEXT[mode] or "SEQUENTIAL"])).."\n"..L("切换策略后按 F 重新开始作业")
        self.seedbutton:SetTooltip(tip)
        self.resource:SetTooltip(L("种子剩余 %d 颗",current).."\n"..tip.."\n"..(plan and block.DescribeProgress({_block=plan}) or L("配比：待规划")))
    elseif kind=="fertilizer"then
        current=Value(tractor,"_fertilizeruses_net",0)
        self.resource_num:SetString(tostring(current))
        self.resource:SetTooltip(L("肥料剩余 %d 次",current).."\n"..Value(tractor,"_fertilizerstock_net",""))
    end
    Visible(self.resource_frame,kind=="irrigator" and capacity>0)
    Visible(self.resource_fill,kind=="irrigator" and capacity>0 and current>0)
    if kind=="irrigator" and capacity>0 then
        local percent=math.clamp(current/capacity,0,1)
        if percent>0 then
            self.resource_fill:ScaleToSize(92*percent,10)
            self.resource_fill:SetPosition(12+46*percent,0,0)
        end
    end
    local working=Value(tractor,"_workstatus",false)
    SetLamp(self.worklamp,working,reason~="")
    self.worklamp:SetTooltip((reason~="" and reason or L(working and "作业中（F 关闭）" or "作业关闭（F 开启）")).."\n"..L("车速 %.0f%%",Value(tractor,"_speedfactor_net",1)*100))
    self:Show()
end
return AOMHud
