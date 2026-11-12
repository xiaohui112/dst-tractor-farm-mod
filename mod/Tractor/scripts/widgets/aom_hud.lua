-- 常驻仅图标和数值；说明走原版 Hoverer。客户端仅读 netvar/replica。
local Widget=require("widgets/widget")
local Image=require("widgets/image")
local ImageButton=require("widgets/imagebutton")
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
    -- 数字牌加高后整体上移，底部控件仍留在物品栏上方。
    self.root:SetPosition(0,166,0)
    self.badges={}
    local colors={health={174/255,21/255,21/255,1},chassis={.8,.55,.12,1},fuel={.8,.37,.08,1},tool={.12,.48,.46,1},cargo={.4,.4,.2,1},water={.12,.52,.72,1}}
    self.order={"health","chassis","fuel","cargo","tool"}
    for _,key in ipairs(self.order)do self.badges[key]=self.root:AddChild(Dial(owner,colors[key],key=="health"))end
    self.badges.water=self.root:AddChild(Dial(owner,colors.water,false))
    self.badges.water:SetIcon("images/aom_water.xml","water_drop.tex")
    self.badges.water:Hide()
    self.badges.chassis:SetIcon(ItemImage("gears"))
    self.badges.fuel:SetIcon(ItemImage("charcoal"))
    self.badges.cargo:SetIcon(ItemImage("treasurechest"))
    self.badges.cargo.warn_low=false
    self.badges.cargo:SetOnClick(function()self:Send(AOM_RPC.STORAGE)end)
    self.badges.tool:SetOnClick(function()
        if Value(self.tractor,"_atttype_net","")=="seeder" then
            self._seed_controls_open=not self._seed_controls_open
            self:Refresh(self.tractor)
        end
    end)
    self.seedcontrols=self.root:AddChild(Widget("seed_settings"))
    self.seedbackground=self.seedcontrols:AddChild(Image("images/hud.xml","craft_slot.tex"))
    self.seedbackground:SetClickable(false)
    self.seedcontrols:Hide()
    self.seedbutton=self.seedcontrols:AddChild(ImageButton("images/ui.xml","spin_arrow.tex","spin_arrow_over.tex",nil,"spin_arrow_down.tex"))
    self.seedbutton:ForceImageSize(28,28)
    self.seedbutton:SetOnClick(function()self:Send(AOM_RPC.SEED_MODE)end)
    self.planbutton=self.seedcontrols:AddChild(ImageButton("images/ui.xml","button_small.tex"))
    self.planbutton:ForceImageSize(62,28);self.planbutton:SetTextSize(20)
    self.planbutton:SetOnClick(function()self:Send(AOM_RPC.PLAN)end)
    self.rotatebutton=self.seedcontrols:AddChild(ImageButton("images/ui.xml","spin_arrow.tex","spin_arrow_over.tex",nil,"spin_arrow_down.tex"))
    self.rotatebutton:ForceImageSize(24,24)
    self.rotatebutton:SetOnClick(function()self:Send(AOM_RPC.PLAN_ROTATE)end)
    self:LayoutControls(nil)
    self:MatchStatusScale()
    self:Hide()
end)
-- 按实际控件收紧木板；仅切换挂件/策略时重排，不打断按键或悬停。
function AOMHud:LayoutControls(kind,mode)
    local key=(kind or "")..(kind=="seeder" and mode=="GIANT" and ":GIANT" or "")
    if self._layout_key==key then return end
    self._layout_key=key
    if kind=="seeder" and mode=="GIANT" then
        self.seedbackground:ScaleToSize(204,36)
        self.rotatebutton:SetPosition(-72,0,0);self.planbutton:SetPosition(0,0,0)
        self.seedbutton:SetPosition(72,0,0)
    else
        self.seedbackground:ScaleToSize(48,36)
        self.seedbutton:SetPosition(0,0,0)
    end
end
function AOMHud:MatchStatusScale()
    local controls=self.owner.HUD and self.owner.HUD.controls
    local status=controls and controls.status
    -- 原版GetLooseScale返回x,y,z三个数值；GetScale才返回Vector3。
    -- 兼容状态栏覆盖实现返回的向量，但不把数值当作表索引。
    local scale=status and type(status.GetLooseScale)=="function" and status:GetLooseScale() or 1.4
    if type(scale)=="table" then scale=scale.x end
    if type(scale)~="number" or not (scale>0 and scale<math.huge) then scale=1.4 end
    -- 原版 Controls 的 StatusDisplays 倍率为1.4；共用表盘原始尺寸。
    for i,key in ipairs(self.order)do
        self.badges[key]:SetScale(scale)
        self.badges[key]:SetPosition((i-(#self.order+1)/2)*78*scale,40,0)
    end
    self.seedcontrols:SetPosition((#self.order-1)/2*78*scale,-58,0)
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
    if not tractor or not tractor:IsValid() or self.owner:HasTag("playerghost")then
        self.tractor=nil;self._seed_controls_open=false;self:Hide();return
    end
    if self.tractor~=tractor then self._seed_controls_open=false end
    self.tractor=tractor
    local kind=Value(tractor,"_atttype_net","")
    self.order=kind=="irrigator" and {"health","chassis","fuel","cargo","tool","water"} or {"health","chassis","fuel","cargo","tool"}
    Visible(self.badges.water,kind=="irrigator")
    self:MatchStatusScale()
    local hp=Value(tractor,"_health_net",600)
    local uses=Value(tractor,"_uses_net",0)
    local fuel=Value(tractor,"_fuel",0)
    local name=ATT[kind]
    local att=name and (STRINGS.NAMES[string.upper(name)] or name) or L("无挂件")
    local tool=Value(tractor,"_tooluses_net",0)
    local max=Value(tractor,"_toolmax_net",0)
    local cargo=Value(tractor,"_cargo_used_net",0)
    local count=Value(tractor,"_cargo_count_net",0)
    local code=require("aom_work_status").Read(tractor)
    local reason=require("aom_work_status").Describe(tractor)
    self.badges.health:SetValue(hp,600,L("车体生命 %d/%d",math.ceil(hp),600).."\n"..L("齿轮修复生命和底盘耐久；生命归零留下残骸"),tostring(math.ceil(hp)),hp<=0)
    self.badges.chassis:SetValue(uses,1000,L("底盘 %d/%d",uses,1000).."\n"..L("齿轮每份恢复100；耐久归零停止作业"),nil,uses<=0)
    self.badges.fuel:SetValue(fuel,800,L("燃料 %d/%d",fuel,800).."\n"..L("下车手持木头、木炭等燃料右键加油"),nil,fuel<=0)
    if name then self.badges.tool:SetIcon("images/aom_attachment_inventory.xml",name..".tex")else self.badges.tool:SetIcon(ItemImage("gears"))end
    local tool_tip=max>0 and att.."\n"..L("挂件耐久 %d/%d",tool,max).."\n"..L("下车手持燧石维修；每份恢复10") or att
    if name then tool_tip=tool_tip.."\n"..L(EFFECT[kind])end
    if kind=="seeder" then
        tool_tip=tool_tip.."\n"..L("种子剩余 %d 颗",Value(tractor,"_seedcount_net",0))
            .."\n"..L("播种策略：%s",L(MODE[Value(tractor,"_seedmode_net","SEQUENTIAL")] or "顺序"))
            .."\n"..L("左键：打开/关闭播种设置")
    end
    local working=Value(tractor,"_workstatus",false)
    tool_tip=tool_tip.."\n"..(reason~="" and reason or L(working and "作业中（F 关闭）" or "作业关闭（F 开启）")).."\n"..L("车速 %.0f%%",Value(tractor,"_speedfactor_net",1)*100)
    self.badges.tool:SetValue(tool,max,tool_tip,max<=0 and "—" or nil,max>0 and tool<=0,max<=0)
    local full=code=="CARGO_FULL"
    local storage=tractor.replica and tractor.replica.container
    local opened=storage and storage:IsOpenedBy(self.owner)
    local cargo_tip=L("货仓：%d/9格",cargo).."\n"..L("物品总数 %d（含堆叠）",count).."\n"..L("左键：打开/关闭货仓；也可左键车身")
    if kind=="fertilizer" then
        cargo_tip=cargo_tip.."\n"..L("肥料剩余 %d 次",Value(tractor,"_fertilizeruses_net",0)).."\n"..Value(tractor,"_fertilizerstock_net","")
    end
    if full then cargo_tip=cargo_tip.."\n"..reason
    elseif cargo==9 then cargo_tip=cargo_tip.."\n"..L("格子已占用，同类物品仍可叠堆")end
    self.badges.cargo:SetValue(cargo,9,cargo_tip,tostring(count),full)
    self.badges.cargo.icon:SetTint(opened and 1 or .85,opened and .85 or .85,opened and .5 or .85,1)
    Visible(self.seedbutton,kind=="seeder")
    local mode=Value(tractor,"_seedmode_net","SEQUENTIAL")
    self:LayoutControls(kind,mode)
    if kind~="seeder" then self._seed_controls_open=false end
    Visible(self.seedcontrols,kind=="seeder" and self._seed_controls_open==true)
    local block=require("aom_block_plan")
    local plan=block.Decode(Value(tractor,"_plan_net",""))
    Visible(self.planbutton,kind=="seeder" and mode=="GIANT")
    Visible(self.rotatebutton,kind=="seeder" and mode=="GIANT" and plan~=nil and plan.confirmed==false)
    self.planbutton:SetText(L(not plan and "预览" or plan.confirmed==false and "确认" or "重规划"))
    self.planbutton:SetTooltip(block.DescribePreview(plan))
    self.rotatebutton:SetTooltip(L("旋转预览90°；不会改动农田"))
    local current,capacity=0,0
    if kind=="irrigator"then
        current,capacity=Value(tractor,"_water_net",0),Value(tractor,"_watermax_net",400)
        local filling=Value(tractor,"_refilling_net",false)
        local tip=L("水量 %d/%d",current,capacity).."\n"..L(filling and "正在补水（5秒）；移动或下车中止" or "车尾靠近池塘，右键持续补水5秒")
        self.badges.water:SetValue(current,capacity,tip,tostring(current),current<=0)
    elseif kind=="seeder"then
        current=Value(tractor,"_seedcount_net",0)
        local mode=Value(tractor,"_seedmode_net","SEQUENTIAL")
        local tip=L("播种策略：%s",L(MODE[mode] or "顺序")).."\n"..L("点击切换为：%s",L(MODE[NEXT[mode] or "SEQUENTIAL"])).."\n"..L("切换策略后按 F 重新开始作业")
        self.seedbutton:SetTooltip(tip)

    end
    self:Show()
end
return AOMHud
