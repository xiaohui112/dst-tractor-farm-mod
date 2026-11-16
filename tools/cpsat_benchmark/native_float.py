"""Offline engine surface: macOS x64 DST 762172 float32 position/query semantics.

This does not patch Lua planner arithmetic. Each SSE scalar arithmetic step is
rounded separately; no epsilon, decimal rounding, grid snapping or fused math.
"""
import numpy as np
from farm_native_math import f32, distance_squared, radius_squared


def distance_matrix(slots):
    # Separate NumPy ufunc calls reproduce subss/mulss/addss, including y.
    xyz = np.array([[p['x'], p.get('y', 0), p['z']] for p in slots], dtype=np.float32)
    dx = xyz[:, 0, None] - xyz[None, :, 0]
    dy = xyz[:, 1, None] - xyz[None, :, 1]
    dz = xyz[:, 2, None] - xyz[None, :, 2]
    return dz*dz + (dx*dx + dy*dy)


def install(world):
    """Replace only test-engine stubs, not package.loaded planner functions."""
    L = world.lua
    g = L.globals()
    g.engine_f32 = f32
    g.engine_distance_squared = distance_squared
    g.engine_radius_squared = radius_squared
    L.execute('''
local function AttachNativeTransform(v)
 v.x=engine_f32(v.x or 0);v.y=engine_f32(v.y or 0);v.z=engine_f32(v.z or 0)
 v.Transform.SetPosition=function(_,x,y,z)
  v.x=engine_f32(x);v.y=engine_f32(y);v.z=engine_f32(z)
 end
 v.Transform.GetWorldPosition=function()return v.x,v.y,v.z end
end
local original_spawn=SpawnPrefab
SpawnPrefab=function(...)
 local v=original_spawn(...);AttachNativeTransform(v);return v
end
for _,v in ipairs(ENTITIES)do AttachNativeTransform(v)end
TheSim.FindEntities=function(_,x,y,z,r,must,exclude,oneof)
 local out={};local r2=engine_radius_squared(r)
 for _,v in ipairs(ENTITIES)do
  local ok=v.valid and engine_distance_squared(x,y,z,v.x,v.y or 0,v.z)<=r2
  for _,tag in ipairs(must or {})do if not v:HasTag(tag)then ok=false end end
  for _,tag in ipairs(exclude or {})do if v:HasTag(tag)then ok=false end end
  if oneof and #oneof>0 then
   local found=false;for _,tag in ipairs(oneof)do if v:HasTag(tag)then found=true end end
   if not found then ok=false end
  end
  if ok then out[#out+1]=v end
 end
 return out
end
''')
