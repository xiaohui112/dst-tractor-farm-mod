-- Extracted from native scripts/widgets/widget.lua; test-only, not distributed with the Mod.
local Widget=...
function Widget:GetLooseScale()
    return self.inst.UITransform:GetScale()
end
