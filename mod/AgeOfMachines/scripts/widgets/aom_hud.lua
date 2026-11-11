--[[
	Tractor —— 驾驶状态面板

	纯文本面板（不依赖任何美术图集），骑上拖拉机时显示在屏幕中下方、物品栏上方。
	显示：当前挂件 / 燃料 / 车速 / 作业状态 / 停机原因 / 水量肥料 / 耐久。

	客户端可读的数据只有 netvar，所以这里只读 netvar：
	  _fuel        (net_float)   燃料
	  _atttype_net (net_string)  挂件类型（容器里的实体客户端拿不到，不能读 _attachment）
	  _workstatus  (net_bool)    作业开关
	水量与上限由服务端从当前挂件汇总到 netvar，客户端不访问组件。
]]

local Widget = require "widgets/widget"
local Text = require "widgets/text"
local TextButton = require "widgets/textbutton"
local L=require("aom_locale").Text

local MAX_FUEL = 800
local ATT_PREFAB = {
	plow = "AOM_LANDCLEARER",
	seeder = "AOM_SEEDER",
	irrigator = "AOM_IRRIGATOR",
	fertilizer = "AOM_FERTILIZER",
	weeder = "AOM_WEEDER",
	harvester = "AOM_HARVESTER",
}

local AOMHud = Class(Widget, function(self, owner)
	Widget._ctor(self, "AOMHud")

	self.owner = owner

	-- 屏幕中下方、物品栏上方（底部居中锚点）。
	self.root = self:AddChild(Widget("root"))
	self.root:SetVAnchor(ANCHOR_BOTTOM)
	self.root:SetHAnchor(ANCHOR_MIDDLE)
	self.root:SetPosition(0, 150, 0)

	self.lines = {}
	for i = 1, 6 do
		local t = self.root:AddChild(Text(NUMBERFONT, 22, ""))
		t:SetHAlign(ANCHOR_LEFT)
		t:SetVAlign(ANCHOR_MIDDLE)
		-- 第 1 行在最上面，后面几行往下排
		t:SetPosition(-170, (3.5 - i) * 26, 0)
		table.insert(self.lines, t)
	end

	self.seedbutton = self.root:AddChild(TextButton())
	self.seedbutton:SetFont(NUMBERFONT)
	self.seedbutton:SetTextSize(22)
	self.seedbutton:SetPosition(190, 26, 0)
	self.seedbutton:SetText(L("切换播种策略"))
	self.seedbutton:SetOnClick(function()
		SendModRPCToServer(AOM_RPC.SEED_MODE)
	end)

	self.detachbutton = self.root:AddChild(TextButton())
	self.detachbutton:SetFont(NUMBERFONT)
	self.detachbutton:SetTextSize(22)
	self.detachbutton:SetPosition(190, -6, 0)
	self.detachbutton:SetText(L("拆下挂件"))
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
	local att_type = tractor._atttype_net ~= nil and tractor._atttype_net:value() or ""
	local att_text = L("无挂件")
	if ATT_PREFAB[att_type] ~= nil then
		att_text = STRINGS.NAMES[ATT_PREFAB[att_type]] or att_type
	end

	-- 燃料
	local fuel = tractor._fuel ~= nil and tractor._fuel:value() or 0
	local fuel_text = L("燃料 %d/%d", math.floor(fuel), MAX_FUEL)

	-- 作业状态 + 停机原因
	local working = tractor._workstatus ~= nil and tractor._workstatus:value() or false
	local status
	if not working then
		status = L("作业关闭（F 开启）")
	elseif fuel <= 0 then
		status = L("停机：没油了")
	else
		status = L("作业中（F 关闭）")
	end

	local reason = tractor._workreason_net and tractor._workreason_net:value() or ""
	if reason ~= "" then status = L(reason) end

	-- 播种策略（仅播种机）
	local mode_names = { SEQUENTIAL = L("顺序"), RANDOM = L("随机"), GIANT = L("配比") }
	local mode_key = tractor._seedmode_net ~= nil and tractor._seedmode_net:value() or ""
	local mode_text = mode_names[mode_key] or L("顺序")

	self.lines[1]:SetString("==== " .. STRINGS.NAMES.AOM_TRACTOR_CHASSIS .. " ====")
	if att_type == "seeder" then
		self.lines[3]:SetString(status .. L("   [播种:%s]", mode_text))
	else
		self.lines[3]:SetString(status)
	end

	local progress = tractor._planprogress_net and tractor._planprogress_net:value() or ""
	if att_type == "irrigator" then
		local water = tractor._water_net and tractor._water_net:value() or 0
		local capacity = tractor._watermax_net and tractor._watermax_net:value() or 0
		self.lines[4]:SetString(L("水箱 %d/%d 次水壶用量", water, capacity))
	elseif att_type == "fertilizer" then
		local uses = tractor._fertilizeruses_net and tractor._fertilizeruses_net:value() or 0
		local stock = tractor._fertilizerstock_net and tractor._fertilizerstock_net:value() or ""
		self.lines[4]:SetString(L("肥料剩余 %d 次", uses) .. (stock ~= "" and ": " .. stock or ""))
	elseif att_type == "seeder" then
		self.lines[4]:SetString(L("种子剩余 %d 颗", tractor._seedcount_net and tractor._seedcount_net:value() or 0))
	else
		self.lines[4]:SetString("")
	end

	local uses = tractor._uses_net and tractor._uses_net:value() or 0
	local tooluses = tractor._tooluses_net and tractor._tooluses_net:value() or 0
	local toolmax = tractor._toolmax_net and tractor._toolmax_net:value() or 0
	self.lines[5]:SetString(L("底盘 %d/%d", uses, 1000) .. (toolmax > 0 and "   " .. L("挂件耐久 %d/%d", tooluses, toolmax) or ""))
	self.lines[6]:SetString(mode_key == "GIANT" and progress or "")

	local factor = tractor._speedfactor_net and tractor._speedfactor_net:value() or 1
	self.lines[2]:SetString(L("挂件：%s   %s   车速 %.0f%%", att_text, fuel_text, factor * 100))
	self.seedbutton:SetText(L("切换播种策略"))

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
