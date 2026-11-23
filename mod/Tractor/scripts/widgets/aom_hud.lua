-- 仪表读 netvar/replica；可切换的挂件共用模式标签和操作提示。
local Widget=require("widgets/widget")
local Dial=require("widgets/aom_badge")
local Text=require("widgets/text")
local L=require("aom_locale").Text
local Seed=require("aom_seed_strategy")
local ATT={}
for kind,def in pairs(require("aom_equipment_defs")) do ATT[kind]=def.prefab end
local SEED_MODES={SEQUENTIAL="顺序",GIANT_TEMPLATE="巨大化·模版",GIANT="巨大化·最优"}
local MODE_CONTROLS={
    seeder={rpc="SEED_MODE",tip="播种策略：%s",hint="空手左键播种机图标，可切换巨大化配比"},
    harvester={rpc="HARVEST_MODE",tip="收割模式：%s",hint="空手左键收割机图标，可切换是否保留巨大作物"},
}
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
    self.badges.chassis:SetIcon(ItemImage("boards"))
    self.badges.fuel:SetIcon(ItemImage("charcoal"))
    self.badges.cargo:SetIcon(ItemImage("treasurechest"))
    self.badges.cargo.warn_low=false
    self.badges.cargo:SetOnClick(function()self:Send(AOM_RPC.STORAGE)end)
    for _,part in ipairs({"health","chassis","fuel"})do
        local kind=part
        self.badges[part]:SetOnClick(function()self:Send(AOM_RPC.MAINTAIN,self.tractor,kind)end)
    end
    self.badges.tool:SetOnRightClick(function()self:Send(AOM_RPC.DETACH,self.tractor)end)
    self.badges.tool:SetOnClick(function()
        local inventory=self.owner.replica and self.owner.replica.inventory
        if inventory and inventory:GetActiveItem() then
            self:Send(AOM_RPC.MAINTAIN,self.tractor,"tool")
        else
            local control=MODE_CONTROLS[Value(self.tractor,"_atttype_net","")]
            if control then self:Send(AOM_RPC[control.rpc],self.tractor) end
        end
    end)
    local tool=self.badges.tool
    self.mode_label=tool:AddChild(Text(UIFONT,18))
    self.mode_label:SetPosition(0,-64,0)
    self.mode_cycle=tool:AddChild(Text(UIFONT,19,"↻"))
    self.mode_cycle:SetPosition(24,22,0)
    self.mode_hint=tool:AddChild(Text(UIFONT,19))
    self.mode_hint:SetPosition(-48,48,0)
    for _,label in ipairs({self.mode_label,self.mode_cycle,self.mode_hint}) do
        label:SetColour(1,.88,.65,1)
        label:SetClickable(false)
        Visible(label,false)
    end
    self:MatchStatusScale()
    self:Hide()
end)
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
end
function AOMHud:Send(rpc,...)
    local rider=self.owner.replica and self.owner.replica.rider
    local tractor=rider and rider:IsRiding() and rider:GetMount()
    if self.tractor and self.tractor:IsValid() and tractor==self.tractor
        and tractor.prefab=="aom_tractor_chassis" and not self.owner:HasTag("playerghost")then
        SendModRPCToServer(rpc,...)
    end
end
function AOMHud:RefreshMode(kind,mode)
    local control=MODE_CONTROLS[kind]
    Visible(self.mode_label,control~=nil)
    Visible(self.mode_cycle,control~=nil)
    if kind~=self.mode_kind then
        self.mode_kind=kind
        Visible(self.mode_hint,false)
    end
    if not control then return end
    self.mode_label:SetString(L(mode))
    local seen=self.owner._aom_mode_hints or {}
    self.owner._aom_mode_hints=seen
    if not seen[kind] then
        seen[kind]=true
        self.mode_hint:SetString(L(control.hint))
        Visible(self.mode_hint,true)
        self.inst:DoTaskInTime(4,function()
            if self.mode_kind==kind then Visible(self.mode_hint,false) end
        end)
    end
end
function AOMHud:Refresh(tractor)
    require("aom_plan_preview").Refresh(self,tractor)
    if not tractor or not tractor:IsValid() or self.owner:HasTag("playerghost")then
        self:RefreshMode("")
        self.tractor=nil;self:Hide();return
    end
    self.tractor=tractor
    local storage=tractor.replica and tractor.replica.container
    self._cargo_open=storage and storage:IsOpenedBy(self.owner) or false
    self.root:SetPosition(0,166,0)
    local kind=Value(tractor,"_atttype_net","")
    local mode,next_mode
    if kind=="seeder" then
        local strategy=Seed.Normalize(Value(tractor,"_seedmode_net","SEQUENTIAL"))
        mode,next_mode=SEED_MODES[strategy],SEED_MODES[Seed.Next(strategy)]
    elseif kind=="harvester" then
        if Value(tractor,"_keep_oversized_net",false) then
            mode,next_mode="保留巨大","全部收割"
        else
            mode,next_mode="全部收割","保留巨大"
        end
    end
    self:RefreshMode(kind,mode)
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
    self.badges.health:SetValue(hp,600,L("生命 %d/%d",math.ceil(hp),600),tostring(math.ceil(hp)),hp<=0)
    self.badges.chassis:SetValue(uses,1000,L("底盘 %d/%d",uses,1000),nil,uses<=0)
    self.badges.fuel:SetValue(fuel,800,L("燃料 %d/%d",fuel,800),nil,fuel<=0)
    if name then self.badges.tool:SetIcon("images/aom_attachment_inventory.xml",name..".tex")else self.badges.tool:SetIcon(nil)end
    local tool_tip=max>0 and att.."\n"..L("耐久 %d/%d",tool,max) or att
    if mode then
        tool_tip=tool_tip.."\n"..L(MODE_CONTROLS[kind].tip,L(mode))
            .."\n"..L("空手左键切换 → %s",L(next_mode))
    end
    self.badges.tool:SetValue(tool,max,tool_tip,max<=0 and "—" or nil,max>0 and tool<=0,max<=0)
    local full=code=="CARGO_FULL"
    local opened=storage and storage:IsOpenedBy(self.owner)
    local capacity=require("aom_cargo").SLOTS
    local cargo_tip=L("货仓：%d/%d格",cargo,capacity).."\n"..L("物品总数 %d（含堆叠）",count)
    self.badges.cargo:SetValue(cargo,capacity,cargo_tip,tostring(count),full)
    self.badges.cargo.icon:SetTint(opened and 1 or .85,opened and .85 or .85,opened and .5 or .85,1)
    local current,capacity=0,0
    if kind=="irrigator"then
        current,capacity=Value(tractor,"_water_net",0),Value(tractor,"_watermax_net",400)
        local tip=L("水量 %d/%d",current,capacity)
        self.badges.water:SetValue(current,capacity,tip,tostring(current),current<=0)
    end
    self:Show()
end
return AOMHud
