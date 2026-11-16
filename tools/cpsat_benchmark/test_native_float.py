"""Engine-boundary regressions independent of the planner's double geometry."""
import random
import unittest

import benchmark as b
import native_float as n
from test_model import case


class NativeFloatTests(unittest.TestCase):
    def test_known_engine_example(self):
        a, c = 8+4/3, 4+4/3
        self.assertGreater((a-c)**2, 16)
        self.assertEqual(n.f32(a), 9.333333015441895)
        self.assertEqual(n.f32(c), 5.333333492279053)
        self.assertEqual(n.distance_squared(a, 0, 0, c, 0, 0), 15.999996185302734)

    def test_boundary_has_no_epsilon_and_includes_equality(self):
        w, _ = b.context(case({}))
        for x, expected in [(4, True), (4.0000001, True), (4.000000476837158, False)]:
            w.lua.globals().input_x = x
            hit = w.lua.execute('''
ENTITIES={};local e=SpawnPrefab('farm_soil');e.Transform:SetPosition(input_x,0,0)
return #TheSim:FindEntities(0,0,0,4,{'soil'})==1
''')
            self.assertEqual(hit, expected)

    def test_y_and_tags_and_radius_conversion(self):
        w, _ = b.context(case({}))
        values = w.lua.execute('''
ENTITIES={};local e=SpawnPrefab('farm_soil');e:AddTag('wanted');e.Transform:SetPosition(0,4,0)
local a=#TheSim:FindEntities(0,0,0,4.0000001,{'soil'},{},{'wanted'})
local b=#TheSim:FindEntities(0,0,0,4,{'soil'},{'wanted'})
local c=#TheSim:FindEntities(0,0,0,3.999999,{'soil'})
local d=#TheSim:FindEntities(0,0,0,4,{'soil'},{},{'absent'})
return a,b,c,d
''')
        self.assertEqual(values, (1, 0, 0, 0))

    def test_transform_readback_and_input_quantization(self):
        w, slots = b.context(case({}, ((0, 0), (1, 0), (2, 0))))
        for p in slots:
            self.assertEqual(p['x'], n.f32(p['x']))
            self.assertEqual(p['z'], n.f32(p['z']))
        result = w.lua.execute("local e=SpawnPrefab('farm_soil');e.Transform:SetPosition(8+4/3,0,0);return e.Transform:GetWorldPosition()")
        self.assertEqual(result, (9.333333015441895, 0, 0))

    def test_matrix_matches_scalar_operations(self):
        rng = random.Random(3981)
        slots = [{'x':rng.uniform(-1000,1000), 'y':rng.uniform(-10,10), 'z':rng.uniform(-1000,1000)} for _ in range(25)]
        mat = n.distance_matrix(slots)
        for i, p in enumerate(slots):
            for j, q in enumerate(slots):
                self.assertEqual(float(mat[i,j]), n.distance_squared(p['x'],p['y'],p['z'],q['x'],q['y'],q['z']))

    def test_planner_uses_native_membership_without_changing_double_math(self):
        w, _ = b.context(case({}))
        # Float32 storage does NOT imply Lua's later subtraction uses float32.
        a, c = n.f32(4+4/3), n.f32(4/3)
        self.assertGreater((a-c)**2, 16)
        self.assertEqual(n.distance_squared(a,0,0,c,0,0), 16)
        L=w.lua
        L.globals().test_slots=L.table_from([{'x':a,'z':0},{'x':c,'z':0}],recursive=True)
        self.assertTrue(L.execute('''
for _,p in ipairs(test_slots)do SpawnPrefab('farm_soil').Transform:SetPosition(p.x,0,p.z)end
local g=Layout.Geometry({},test_slots,DEFS)
for _,v in ipairs(g.near[1])do if v.j==2 then return true end end
return false
'''))


if __name__ == '__main__':
    unittest.main()
