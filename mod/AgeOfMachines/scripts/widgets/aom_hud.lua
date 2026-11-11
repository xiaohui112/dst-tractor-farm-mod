--[[
	Tractor —— 驾驶状态面板

	纯文本面板（不依赖任何美术图集），骑上拖拉机时显示在屏幕左上角。
	显示：当前挂件 / 燃料 / 作业状态 / 停机原因。

	客户端可读的数据只有 netvar，所以这里只读 netvar：
	  _fuel        (net_float)   燃料
	  _attachment  (net_entity)  挂件物品
	  _workstatus  (net_bool)    作业开关
	水量与上限由服务端从当前挂件汇总到 netvar，客户端不访问组件。
]]

local Widget = require "widgets/widget"
local Text = require "widgets/text"
local TextButton = require "widgets/textbutton"

local MAX_FUEL = 800

local AOMHud = Class(Widget, function(self, owner)
	Widget._ctor(self, "AOMHud")

	self.owner = owner

	self.root = self:AddChild(Widget("root"))
	self.root:SetVAnchor(ANCHOR_TOP)
	self.root:SetHAnchor(ANCHOR_LEFT)
	self.root:SetPosition(18, -60, 0)

	self.lines = {}
	for i = 1, 4 do
		local t = self.root:AddChild(Text(NUMBERFONT, 22, ""))
		t:SetHAlign(ANCHOR_LEFT)
		t:SetVAlign(ANCHOR_TOP)
		t:SetPosition(0, -(i - 1) * 26, 0)
		table.insert(self.lines, t)
	end

	self.seedbutton = self.root:AddChild(TextButton())
	self.seedbutton:SetFont(NUMBERFONT)
	self.seedbutton:SetTextSize(22)
	self.seedbutton:SetPosition(100, -112, 0)
	self.seedbutton:SetText("切换播种策略")
	self.seedbutton:SetOnClick(function()
		SendModRPCToServer(AOM_RPC.SEED_MODE)
	end)

	self.detachbutton = self.root:AddChild(TextButton())
	self.detachbutton:SetFont(NUMBERFONT)
	self.detachbutton:SetTextSize(22)
	self.detachbutton:SetPosition(100, -140, 0)
	self.detachbutton:SetText("拆下挂件")
	self.detachbutton:SetOnClick(function()
		SendModRPCToServer(AOM_RPC.DETACH)
	end)
	self.detachbutton:Hide()

	self:Hide()
end)

function AOMHud:Refresh(tractor)
	if tractor == nil or not tractor:IsValid() then
		self:Hide()
		return
	end

	-- 挂件类型走 net_string：容器里的实体引用在客户端拿不到，不能靠 _attachment:value()。
	local ATT_PREFAB = {
		plow = "AOM_LANDCLEARER",
		seeder = "AOM_SEEDER",
		irrigator = "AOM_IRRIGATOR",
		fertilizer = "AOM_FERTILIZER",
		weeder = "AOM_WEEDER",
		harvester = "AOM_HARVESTER",
	}
	local att_type = tractor._atttype_net ~= nil and tractor._atttype_net:value() or ""
	local att_text = "无挂件"
	if ATT_PREFAB[att_type] ~= nil then
		att_text = STRINGS.NAMES[ATT_PREFAB[att_type]] or att_type
	end

	-- 燃料
	local fuel = tractor._fuel ~= nil and tractor._fuel:value() or 0
	local fuel_text = string.format("燃料 %d/%d", math.floor(fuel), MAX_FUEL)

	-- 作业状态 + 停机原因
	local working = tractor._workstatus ~= nil and tractor._workstatus:value() or false
	local status
	if not working then
		status = "作业关闭（F 开启）"
	elseif fuel <= 0 then
		status = "停机：没油了"
	else
		status = "作业中（F 关闭）"
	end

    local reason=tractor._workreason_net and tractor._workreason_net:value() or ""
    if reason~="" then status=reason end
	-- 播种策略（仅播种机）
	local mode_names = { SEQUENTIAL = "顺序", RANDOM = "随机", GIANT = "配比" }
	local mode_key = tractor._seedmode_net ~= nil and tractor._seedmode_net:value() or ""
	local mode_text = mode_names[mode_key] or "顺序"

	self.lines[1]:SetString("==== " .. STRINGS.NAMES.AOM_TRACTOR_CHASSIS .. " ====")
	self.lines[2]:SetString("挂件：" .. att_text .. "   " .. fuel_text)
	if att_type == "seeder" then
		self.lines[3]:SetString(status .. "   [播种:" .. mode_text .. "]")
	else
		self.lines[3]:SetString(status)
	end

    local progress=tractor._planprogress_net and tractor._planprogress_net:value() or ""
    if att_type == "irrigator" then
        local water=tractor._water_net and tractor._water_net:value() or 0
        local capacity=tractor._watermax_net and tractor._watermax_net:value() or 0
        self.lines[4]:SetString(string.format("水箱 %d/%d 次水壶用量",water,capacity))
    elseif att_type == "fertilizer" then
        local uses=tractor._fertilizeruses_net and tractor._fertilizeruses_net:value() or 0
        local stock=tractor._fertilizerstock_net and tractor._fertilizerstock_net:value() or ""
        self.lines[4]:SetString(string.format("肥料剩余 %d 次",uses)..(stock~="" and "："..stock or ""))
    else self.lines[4]:SetString(mode_key=="GIANT" and progress or "") end
	local factor=tractor._speedfactor_net and tractor._speedfactor_net:value() or 1
	self.lines[2]:SetString("挂件："..att_text.."   "..fuel_text..string.format("   车速 %.0f%%",factor*100))
	if att_type == "seeder" then
		self.seedbutton:Show()
	else
		self.seedbutton:Hide()
	end
	if att_type ~= "" then
		self.detachbutton:Show()
	else
		self.detachbutton:Hide()
	end
	self:Show()
end

return AOMHud
