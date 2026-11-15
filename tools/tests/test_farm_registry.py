"""农田记录仅为运行期缓存，记录完整九宫格并按四边连通查找。"""
import unittest
import test_giant_farming as giant

class FarmRegistryTests(unittest.TestCase):
    def setUp(self):
        self.w=giant.World();self.lua=self.w.lua
        self.lua.execute('''Registry=require('aom_farm_registry')
function make_field(x,z)
 for dx=-1,1 do for dz=-1,1 do
  SpawnPrefab('farm_soil').Transform:SetPosition(x+dx*4/3,0,z+dz*4/3)
 end end
end
''')
    def test_component_is_shared_but_bounded_by_world_lifetime(self):
        self.lua.execute('''
Registry.Record(TheWorld,0,0);Registry.Record(TheWorld,4,0);Registry.Record(TheWorld,4,4)
Registry.Record(TheWorld,12,0);Registry.Record(TheWorld,8,4)
local got,truncated=Registry.Connected(TheWorld,0,0,64)
assert(#got==4 and not truncated)
local subset,full=Registry.Connected(TheWorld,0,0,2)
assert(#subset==2 and full)
Registry.Remove(TheWorld,4,0)
assert(#Registry.Connected(TheWorld,0,0,64)==1)
assert(#Registry.Connected({},0,0,64)==0)
''')
    def test_plow_records_complete_and_already_ready_but_not_incomplete(self):
        self.lua.execute('''
inst=make_inst({},'autumn');inst._attachment_type='plow'
make_field(0,0)
local changed,reason,ready=Drive.WorkHere(inst,0,0)
assert(not changed and reason=='ALREADY_TILLED' and ready)
assert(#Registry.Connected(TheWorld,0,0)==1)
local rock=SpawnPrefab('weed_ivy');rock.Transform:SetPosition(4,0,0)
Drive.WorkHere(inst,4,0)
assert(#Registry.Connected(TheWorld,4,0)==0)
''')
