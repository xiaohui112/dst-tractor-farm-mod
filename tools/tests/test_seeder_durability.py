"""播种机按地皮完成结算；逐颗耗种，油和底盘按地皮结算。"""
import unittest
import test_auto_grid_seeding as auto


class SeederDurabilityTests(unittest.TestCase):
    def setUp(self):
        fixture = auto.AutoGridSeedingTests()
        fixture.setUp()
        self.lua = fixture.lua
        self.lua.execute('''
function uses()return inst.components.container.slots[1].components.finiteuses:GetUses()end
''')

    def test_all_three_strategies_charge_one_per_completed_tile(self):
        for strategy, stock, expected in (
            ('SEQUENTIAL', '{tomato=30}', 27),
            ('GIANT', '{tomato=20,potato=20}', 24),
            ('GIANT_TEMPLATE', '{tomato=20,potato=20}', 24),
        ):
            with self.subTest(strategy=strategy):
                self.setUp()
                self.lua.execute('''
field(0,0,3,1);seeder(%s);inst._seed_strategy='%s'
for x=0,8,4 do assert(drive_at(x,0))end
assert(crop_count()==%d and uses()==97)
assert(inst._fuel:value()==797 and inst.components.finiteuses.used==3)
for x=0,8,4 do drive_at(x,0)end
assert(uses()==97)
''' % (stock, strategy, expected))

    def test_partial_plan_survives_stop_save_load_and_charges_at_completion(self):
        self.lua.execute('''
field(0,0,1,1);seeder({tomato=4,potato=4})
for i=1,3 do assert(Drive.WorkHere(inst,0,0))end
assert(crop_count()==3 and uses()==100)
Drive.SetWorking(inst,false)
local data=Block.OnSave(inst);local container=inst.components.container
local fresh=make_inst({},'autumn');fresh.components.container=container
fresh.components.aom_attachment_store=inst.components.aom_attachment_store
Block.OnLoad(fresh,data);inst=fresh;inst._attachment_type='seeder'
assert(drive_at(0,0));assert(crop_count()==8 and uses()==99)
drive_at(0,0);assert(uses()==99)
''')

    def test_sequential_short_stock_and_refill_charge_only_at_completion(self):
        self.lua.execute('''
field(0,0,1,1);seeder({tomato=3});inst._seed_strategy='SEQUENTIAL'
assert(drive_at(0,0));assert(crop_count()==3 and uses()==100)
inst.components.container:GiveItem(make_seed('tomato',6))
Drive.SetWorking(inst,true);assert(drive_at(0,0))
assert(crop_count()==9 and uses()==99)
''')

    def test_last_durability_point_finishes_whole_tile(self):
        self.lua.execute('''
field(0,0,2,1);seeder({tomato=8,potato=8})
local tool=inst.components.container.slots[1]
tool.Transform={SetPosition=function()end}
tool.attachment_type='seeder'
local remaining=1
tool.components.finiteuses.GetUses=function()return remaining end
tool.components.finiteuses.Use=function(_,n)remaining=remaining-n end
local ok,reason=drive_at(0,0)
assert(ok and reason=='BROKEN_SEEDER' and crop_count()==8)
assert(tool.components.finiteuses:GetUses()==0 and not inst._working)
''')

    def test_last_seed_callback_error_after_change_charges_once(self):
        self.lua.execute('''
field(0,0,1,1);seeder({tomato=4,potato=4})
for i=1,7 do assert(Drive.WorkHere(inst,0,0))end
assert(uses()==100)
for _,item in ipairs(inst.components.aom_attachment_store:ListSeeds())do
 local plant=item.components.farmplantable.Plant
 item.components.farmplantable.Plant=function(...)plant(...);error('after final seed')end
end
local ok,why=drive_at(0,0)
assert(ok and why=='WORK_ERROR' and crop_count()==8 and uses()==99)
Drive.SetWorking(inst,true);drive_at(0,0);assert(uses()==99)
''')

    def test_failed_last_seed_does_not_charge_and_new_round_charges_again(self):
        self.lua.execute('''
field(0,0,1,1);seeder({tomato=20,potato=20})
for i=1,7 do assert(Drive.WorkHere(inst,0,0))end
PLANT_FAIL=true;assert(not drive_at(0,0));assert(uses()==100)
PLANT_FAIL=false;Drive.SetWorking(inst,true);assert(drive_at(0,0));assert(uses()==99)
for _,v in ipairs(ENTITIES)do if v:IsValid() and v:HasTag('farm_plant')then
 local x,_,z=v.Transform:GetWorldPosition();v:Remove();SpawnPrefab('farm_soil').Transform:SetPosition(x,0,z)
end end
assert(drive_at(0,0));assert(uses()==98 and crop_count()==8)
''')
