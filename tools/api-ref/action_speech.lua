-- Test-only excerpts: local DST r762172 stringutil.lua and prefabs/player_common.lua.
local function getmodifiedstring(topic_tab, modifier)
	if type(modifier) == "table" then
		local ret = topic_tab
		for i,v in ipairs(modifier) do
			if ret == nil then
				return nil
			end
			ret = ret[v]
		end
		return ret
	elseif modifier ~= nil then
        local ret = topic_tab[modifier]
        return (type(ret) == "table" and #ret > 0 and ret[math.random(#ret)])
                or ret
                or topic_tab.GENERIC
                or (#topic_tab > 0 and topic_tab[math.random(#topic_tab)])
                or nil
    else
		return topic_tab.GENERIC
                or (#topic_tab > 0 and topic_tab[math.random(#topic_tab)])
                or nil
	end
end

local function getcharacterstring(tab, item, modifier)

    if tab == nil then
        return
    end

    local topic_tab = tab[item]
    if topic_tab == nil then
        return
    elseif type(topic_tab) == "string" then
        return topic_tab
    elseif type(topic_tab) ~= "table" then
        return
    end

	if type(modifier) == "table" then
		for i,v in ipairs(modifier) do
			v = string.upper(v)
		end
	else
		modifier = modifier ~= nil and string.upper(modifier) or nil
	end

	return getmodifiedstring(topic_tab, modifier)
end

function GetSpecialCharacterString(character)
    if character == nil then
        return nil
    end

    character = string.lower(character)

    return (character == "mime" and "")
        or (character == "ghost" and CraftOooh())
        or (character == "wonkey" and CraftMonkeySpeech())
        or (character == "wilton" and wilton_sayings[math.random(#wilton_sayings)])
        or nil
end

function GetActionFailString(inst, action, reason)
    if reason == "ITEMMIMIC" then
        action = "GENERIC" -- Funnel all responses to this one.
    end

    local character =
        type(inst) == "string"
        and inst
        or (inst ~= nil and inst.prefab or nil)

    local specialcharacter =
        type(inst) == "table"
        and ((inst:HasTag("playerghost") and "ghost") or
            (inst:HasTag("mime") and "mime"))
        or character

    local ret = GetSpecialCharacterString(specialcharacter)
    if ret ~= nil then
        return ret
    end

    character = string.upper(character)

	local character_tbl = STRINGS.CHARACTERS[character]
	return character_tbl
		and (	getcharacterstring(character_tbl.ACTIONFAIL, action, reason) or
				getcharacterstring(character_tbl.ACTIONFAIL, "GENERIC", reason) or
				character_tbl.ACTIONFAIL_GENERIC
			)
        or getcharacterstring(STRINGS.CHARACTERS.GENERIC.ACTIONFAIL, action, reason)
        or getcharacterstring(STRINGS.CHARACTERS.GENERIC.ACTIONFAIL, "GENERIC", reason)
        or STRINGS.CHARACTERS.GENERIC.ACTIONFAIL_GENERIC
end

local function OnActionFailed(inst, data)
    if inst.components.talker ~= nil
		and not data.action.action.silent_fail
        and (not data.action.action.silent_generic_fail or data.reason ~= nil)
        and (data.reason ~= nil or
            not data.action.autoequipped or
            inst.components.inventory.activeitem == nil) then
        --V2C: Added edge case to suppress talking when failure is just due to
        --     action equip failure when your inventory is full.
        --     Note that action equip fail is an indirect check by testing
        --     whether your active slot is now empty or not.
        --     This is just to simplify making it consistent on client side.
        inst.components.talker:Say(GetActionFailString(inst, data.action.action.id, data.reason))
    end
end


return {OnActionFailed=OnActionFailed,GetActionFailString=GetActionFailString}
