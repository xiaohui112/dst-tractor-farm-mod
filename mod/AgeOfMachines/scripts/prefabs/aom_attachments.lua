--[[
	Age of Machines —— 六种拖拉机挂件

	挂件都是物品，带 tag "aom_attachment" 与字段 attachment_type。
	装上底盘后，底盘按 attachment_type 调用对应的原版农场动作。
]]

local AOMFarmWork = require("aom_farm_work")
local AOM = require("aom_common")
local LandClearer = require("aom_landclearer_tool")
local Irrigator = require("aom_irrigator")

local assets =
{
	Asset("ANIM", "anim/aom_attachment_shared.zip"),
	Asset("ATLAS", "images/aom_attachment_inventory.xml"),
	Asset("IMAGE", "images/aom_attachment_inventory.tex"),
}

local function MakeAttachment(name, att_type, postinit)
	local function fn()
		local inst = CreateEntity()

		inst.entity:AddTransform()
		inst.entity:AddAnimState()
		inst.entity:AddNetwork()

		MakeInventoryPhysics(inst)

		inst.AnimState:SetBank("aom_attachment_shared")
		inst.AnimState:SetBuild("aom_attachment_shared")
		inst.AnimState:PlayAnimation(att_type)

		inst:AddTag(AOM.TAG.ATTACHMENT)
		inst:AddTag("irreplaceable")

		inst.attachment_type = att_type

		inst.entity:SetPristine()

		if not TheWorld.ismastersim then
			return inst
		end

		inst:AddComponent("inspectable")
		inst:AddComponent("inventoryitem")
		inst.components.inventoryitem.atlasname = "images/aom_attachment_inventory.xml"
		if name=="aom_plow" then inst.components.inventoryitem.imagename="aom_landclearer" end

		inst:AddComponent("finiteuses")
		inst.components.finiteuses:SetMaxUses(postinit and postinit.uses or 60)
		inst.components.finiteuses:SetUses(postinit and postinit.uses or 60)

		if postinit and postinit.setup then
			postinit.setup(inst)
		end

		return inst
	end

	return Prefab(name, fn, assets)
end

---------------------------------------------------------------------------
-- 配方
---------------------------------------------------------------------------

return
	MakeAttachment("aom_landclearer", AOM.TYPE.PLOW, {
		uses = LandClearer.MAX_USES,
	}),
	-- 旧存档沿用旧 prefab 名，图标、属性与新开垦机一致；不增加旧配方。
	MakeAttachment("aom_plow", AOM.TYPE.PLOW, { uses = LandClearer.MAX_USES }),

	MakeAttachment("aom_seeder", AOM.TYPE.SEEDER, {
		uses = 100,
	}),

	MakeAttachment("aom_irrigator", AOM.TYPE.IRRIGATOR, {
		uses = Irrigator.Capacity(),
		setup = Irrigator.Setup,
	}),

	MakeAttachment("aom_fertilizer", AOM.TYPE.FERTILIZER, {
		uses = 100,
	}),

	MakeAttachment("aom_weeder", AOM.TYPE.WEEDER, {
		uses = 50,
	}),

	MakeAttachment("aom_harvester", AOM.TYPE.HARVESTER, {
		uses = 40,
	})
