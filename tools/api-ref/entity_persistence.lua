-- 原版 EntityScript 存读档方法原文摘录；仅测试使用。
local EntityScript={}
function EntityScript:GetPersistData()
    local references = {}
    local data = {}
    for k, v in pairs(self.components) do
        if v.OnSave then
            local t, refs = v:OnSave()
            if type(t) == "table" and not IsTableEmpty(t) then
                data[k] = t
				if t.add_component_if_missing then
					data.add_component_if_missing = true
				end
            end

            if refs then
                for k1, v1 in pairs(refs) do
                    table.insert(references, v1)
                end
            end
        end
    end

    if self.OnSave then
        local refs = self.OnSave(self, data)

        if refs then
            for k, v in pairs(refs) do
                table.insert(references, v)
            end
        end
    end

    if not IsTableEmpty(data) or not IsTableEmpty(references) then
        return data, references
    end
end

function EntityScript:LoadPostPass(newents, savedata)
    if savedata ~= nil then
        for k, v in pairs(savedata) do
            local cmp = self.components[k]
            if cmp ~= nil and cmp.LoadPostPass ~= nil then
                cmp:LoadPostPass(newents, v)
            end
        end
    end

    if self.OnLoadPostPass ~= nil then
        self:OnLoadPostPass(newents, savedata)
    end
end

function EntityScript:SetPersistData(data, newents)
	if data and data.add_component_if_missing then
		for k, v in pairs(data) do
			if self.components[k] == nil and type(v) == "table" and v.add_component_if_missing then
				self:AddComponent(k)
			end
		end
	end

    if self.OnPreLoad ~= nil then
        self:OnPreLoad(data, newents)
    end

    if data ~= nil then
        for k, v in pairs(data) do
            local cmp = self.components[k]

			--V2C: -backward compatibility for add_component_if_missing
			--     -the flag has since been added to the base data table as well so that we
			--      can add the missing components before preload
            if cmp == nil and type(v) == "table" and v.add_component_if_missing then
				self:AddComponent(k)
                cmp = self.components[k]
            end
			------

            if cmp ~= nil and cmp.OnLoad ~= nil then
                cmp:OnLoad(v, newents)
            end
        end
    end

    if self.OnLoad ~= nil then
        self:OnLoad(data, newents)
    end
end


return EntityScript
