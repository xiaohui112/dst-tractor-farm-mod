"""施肥完整流程：实际原版养分、肥料消耗、堆叠、容器、归属与存读档方法。"""
from pathlib import Path
import unittest
from test_giant_farming import World

ROOT=Path(__file__).resolve().parents[2]

class FertilizerFlowTests(unittest.TestCase):
    def setUp(self):
        self.w=World()
        self.w.lua.globals().REF=str(ROOT/'tools/api-ref')
        self.w.lua.globals().TESTS=str(ROOT/'tools/tests')
        self.w.lua.execute((ROOT/'tools/tests/fertilizer_engine.lua').read_text())

    def run_lua(self,s):self.w.lua.execute(s)

    def test_full_tile_is_zero_cost_even_when_empty_and_no_fuel(self):
        self.run_lua('''
set_nutrients(100,100,100);inst._fuel:set(0);start_fertilizer()
assert(not Drive.WorkTile(inst,0,0))
assert(inst._working and inst._fuel:value()==0 and inst.components.finiteuses.used==0)
''')

    def test_dry_tile_fills_three_nutrients_and_bills_once(self):
        self.run_lua('''
set_nutrients(0,0,0)
local a=add_stock(material('formula',{8,0,0},20),2)
local b=add_stock(material('compost',{0,24,0},10),3)
local c=add_stock(material('poop',{0,0,8},20),4)
assert(Drive.WorkTile(inst,0,0))
local x,y,z=nutrients();assert(x==100 and y==100 and z==100)
assert(a.components.stackable:StackSize()==7 and b.components.stackable:StackSize()==5 and c.components.stackable:StackSize()==7)
assert(inst._fuel:value()==799 and inst.components.finiteuses.used==1)
''')

    def test_multi_use_item_stays_in_container_and_counts_remaining_doses(self):
        self.run_lua('''
set_nutrients(100,100,84)
local bucket=add_stock(material('fertilizer',{0,0,16},nil,5),2)
assert(store:GetFertilizerCount()==5 and Drive.WorkTile(inst,0,0))
assert(bucket.components.finiteuses:GetUses()==4 and store:GetFertilizerCount()==4)
assert(inst.components.container:GetItemInSlot(2)==bucket and bucket.components.inventoryitem.owner==inst)
''')

    def test_last_use_consumes_bucket_and_retains_native_empty_bottle(self):
        self.run_lua('''
set_nutrients(68,100,100)
local bottle=add_stock(material('soil_amender_fermented',{32,0,0},nil,1,true),2)
assert(Drive.WorkTile(inst,0,0));assert(not bottle:IsValid())
assert(inst.components.container:GetItemInSlot(2)==nil and count_prefab(farmer,'messagebottleempty')==1)
assert(store:GetFertilizerCount()==0 and inst._fuel:value()==799)
''')

    def test_stack_consumes_one_per_native_dose_and_keeps_owner(self):
        self.run_lua('''
set_nutrients(100,100,85)
local poop=add_stock(material('poop',{0,0,8},5),2)
assert(Drive.WorkTile(inst,0,0))
assert(poop.components.stackable:StackSize()==3 and poop.components.inventoryitem.owner==inst)
assert(count_prefab(inst,'poop')==3)
''')

    def test_skips_ineffective_first_slot_and_selects_useful_fertilizer(self):
        self.run_lua('''
set_nutrients(100,100,92)
local bad=add_stock(material('compost',{0,24,0},3),2)
local good=add_stock(material('poop',{0,0,8},3),3)
assert(Drive.WorkTile(inst,0,0))
assert(bad.components.stackable:StackSize()==3 and good.components.stackable:StackSize()==2)
''')

    def test_selection_prefers_less_overflow_then_larger_gain_then_slot_order(self):
        self.run_lua('''
local a=add_stock(material('mixed',{8,8,0},3),2)
local b=add_stock(material('exact',{0,8,0},3),3)
assert(Fertilizer.Select(store,{99,0,100})==b)
local c=add_stock(material('large',{0,24,0},3),4)
assert(Fertilizer.Select(store,{99,0,100})==c)
local d=add_stock(material('tie',{0,24,0},3),5)
assert(Fertilizer.Select(store,{99,0,100})==c)
''')

    def test_no_fertility_improvement_does_not_consume_anything(self):
        self.run_lua('''
set_nutrients(100,100,100)
local item=add_stock(material('poop',{0,0,8},3),2)
assert(not Drive.WorkTile(inst,0,0))
assert(count_prefab(inst,'poop')==3 and inst._fuel:value()==800 and inst.components.finiteuses.used==0)
''')

    def test_nonfarm_and_nearby_pickable_are_untouched(self):
        self.run_lua('''
set_nutrients(0,0,0);local hits=0
local bush=engine_entity();bush.Transform:SetPosition(.5,0,.5)
bush.components.pickable={CanBeFertilized=function()return true end,Fertilize=function()hits=hits+1;return true end}
local all=add_stock(material('all',{100,100,100},3),2)
assert(Drive.WorkTile(inst,0,0));assert(hits==0)
TILES[tkey(4,0)]=-1;assert(not Drive.WorkTile(inst,4,0));assert(hits==0 and all.components.stackable:StackSize()==2)
''')

    def test_shortage_preserves_partial_progress_and_resumes_only_missing_parts(self):
        self.run_lua('''
set_nutrients(0,0,0);add_stock(material('poop',{0,0,8},2),2)
start_fertilizer();Drive.TrackMovement(inst)
local a,b,c=nutrients();assert(a==0 and b==0 and c==16 and not inst._working)
assert(inst._fuel:value()==799 and inst.components.finiteuses.used==1)
assert(string.find(inst._workreason_net:value(),'生长素') and string.find(inst._workreason_net:value(),'堆肥') and string.find(inst._workreason_net:value(),'粪肥'))
add_stock(material('all',{100,100,100},2),2);start_fertilizer();Drive.TrackMovement(inst)
a,b,c=nutrients();assert(a==100 and b==100 and c==100 and inst._working)
assert(inst._fuel:value()==798 and inst.components.finiteuses.used==2)
''')

    def test_specific_shortage_names_only_missing_type(self):
        self.run_lua('''
set_nutrients(100,100,0);add_stock(material('compost',{0,24,0},3),2)
start_fertilizer();Drive.TrackMovement(inst)
local reason=inst._workreason_net:value()
assert(string.find(reason,'粪肥') and not string.find(reason,'生长素') and not string.find(reason,'堆肥'))
assert(inst._fuel:value()==800 and store:GetFertilizerCount()==3 and not inst._working)
''')

    def test_zero_negative_nan_and_exhausted_fertilizer_are_not_used(self):
        self.run_lua('''
set_nutrients(0,0,0)
local zero=add_stock(material('zero',{0,0,0},3),2)
local negative=add_stock(material('negative',{-1,10,0},3),3)
local nan=add_stock(material('nan',{0/0,10,0},3),4)
local empty=add_stock(material('empty',{100,100,100},nil,5),5);empty.components.finiteuses:SetUses(0)
start_fertilizer();Drive.TrackMovement(inst)
assert(not inst._working and inst._fuel:value()==800 and zero:IsValid() and negative:IsValid() and nan:IsValid())
''')

    def test_parking_return_to_full_and_crossed_tiles(self):
        self.run_lua('''
for x=0,12,4 do set_nutrients(0,0,0,x,0)end
local item=add_stock(material('all',{100,100,100},8),2)
start_fertilizer();Drive.TrackMovement(inst)
for i=1,30 do Drive.TrackMovement(inst)end
assert(count_prefab(inst,'all')==7 and inst._fuel:value()==799)
inst.Transform:SetPosition(12,0,0);Drive.TrackMovement(inst)
assert(count_prefab(inst,'all')==4 and inst._fuel:value()==796)
inst.Transform:SetPosition(0,0,0);Drive.TrackMovement(inst)
assert(count_prefab(inst,'all')==4 and inst._fuel:value()==796)
''')

    def test_one_fuel_fills_entire_tile_zero_fuel_preserves_stock(self):
        self.run_lua('''
set_nutrients(0,0,0);add_stock(material('all',{8,8,8},20),2)
inst._fuel:set(1);start_fertilizer();Drive.TrackMovement(inst)
local a,b,c=nutrients();assert(a==100 and b==100 and c==100 and inst._fuel:value()==0 and not inst._working)
set_nutrients(0,0,0,4,0);start_fertilizer();inst.Transform:SetPosition(4,0,0);Drive.TrackMovement(inst)
assert(store:GetFertilizerCount()==7 and inst.components.finiteuses.used==1 and not inst._working)
''')

    def test_batch_sound_plays_once_instead_of_layering_each_dose(self):
        self.run_lua('''
set_nutrients(0,0,0);add_stock(material('all',{8,8,8},20),2)
local sounds=0;farmer.SoundEmitter.PlaySound=function()sounds=sounds+1 end
assert(Drive.WorkTile(inst,0,0));assert(sounds==1)
''')

    def test_actual_native_single_dose_matches_original_deploy_callback(self):
        self.run_lua('''
local item=add_stock(material('mixed',{24,32,24},nil,5),2)
set_nutrients(50,80,0);assert(Farm.Fertilize(0,0,0,farmer,item))
local a,b,c=nutrients();local left=item.components.finiteuses:GetUses()
set_nutrients(50,80,0);local oracle=material('oracle',{24,32,24},nil,5)
NativeDeploy(oracle,Vector3(0,0,0),farmer)
local x,y,z=nutrients();assert(a==x and b==y and c==z and left==oracle.components.finiteuses:GetUses())
''')

    def test_noop_or_error_before_mutation_preserves_materials_and_cost(self):
        self.run_lua('''
set_nutrients(0,0,0);local item=add_stock(material('all',{100,100,100},3),2)
local add=FM.AddTileNutrients;FM.AddTileNutrients=function()return true end
start_fertilizer();Drive.TrackMovement(inst)
assert(not inst._working and count_prefab(inst,'all')==3 and inst._fuel:value()==800)
FM.AddTileNutrients=function()error('failed before application')end
start_fertilizer();Drive.TrackMovement(inst)
assert(not inst._working and count_prefab(inst,'all')==3 and inst._fuel:value()==800)
''')

    def test_error_after_mutation_bills_one_actual_dose_and_can_resume(self):
        self.run_lua('''
set_nutrients(0,0,0);add_stock(material('all',{8,8,8},20),2)
local add=FM.AddTileNutrients;FM.AddTileNutrients=function(...)add(...);error('callback failed')end
start_fertilizer();Drive.TrackMovement(inst)
local a,b,c=nutrients();assert(a==8 and b==8 and c==8 and count_prefab(inst,'all')==19)
assert(inst._fuel:value()==799 and inst.components.finiteuses.used==1 and not inst._working)
FM.AddTileNutrients=add;start_fertilizer();Drive.TrackMovement(inst)
a,b,c=nutrients();assert(a==100 and b==100 and c==100 and count_prefab(inst,'all')==7 and inst._fuel:value()==798)
''')

    def test_read_failure_stops_without_spending(self):
        self.run_lua('''
local item=add_stock(material('all',{8,8,8},3),2)
FM.GetTileNutrients=function()error('unavailable')end
start_fertilizer();Drive.TrackMovement(inst)
assert(not inst._working and count_prefab(inst,'all')==3 and inst._fuel:value()==800)
''')

    def test_remaining_doses_and_net_stock_follow_stack_and_finiteuses(self):
        self.run_lua('''
local item=add_stock(material('bucket',{0,0,16},nil,5),2)
local stack=add_stock(material('poop',{0,0,8},3),3)
assert(store:GetFertilizerCount()==8 and inst._fertilizeruses_net:value()==8)
item.components.finiteuses:Use(1);assert(inst._fertilizeruses_net:value()==7)
stack.components.stackable:SetStackSize(2);assert(inst._fertilizeruses_net:value()==6)
assert(string.find(inst._fertilizerstock_net:value(),'bucket 4次'))
inst.components.container:RemoveItem(item,true);assert(inst._fertilizeruses_net:value()==2)
item.components.finiteuses:Use(1);assert(inst._fertilizeruses_net:value()==2)
''')

    def test_load_moves_ownership_instead_of_duplicating_reference(self):
        self.run_lua('''
local item=hold(material('bucket',{0,0,16},nil,5),1)
assert(store:LoadItem(item,farmer))
assert(farmer.components.inventory:GetItemInSlot(1)==nil)
assert(count_prefab(inst,'bucket')==1 and item.components.inventoryitem.owner==inst and not farmer.children[item])
''')

    def test_full_container_keeps_entire_source_item_in_original_slot(self):
        self.run_lua('''
for i=2,9 do add_stock(material('stock'..i,{8,8,8},nil,5),i)end
local item=hold(material('bucket',{0,0,16},nil,5),1)
assert(not store:LoadItem(item,farmer))
assert(farmer.components.inventory:GetItemInSlot(1)==item and item.components.inventoryitem.owner==farmer)
''')

    def test_partial_stack_load_only_detaches_capacity_and_keeps_remainder(self):
        self.run_lua('''
local dest=add_stock(material('poop',{0,0,8},38),2)
for i=3,9 do add_stock(material('stock'..i,{8,8,8},nil,5),i)end
local item=hold(SpawnPrefab('poop'),1);item.components.stackable:SetStackSize(5)
local ok,n=store:LoadItem(item,farmer)
assert(ok and n==2 and dest.components.stackable:StackSize()==40)
assert(item.components.stackable:StackSize()==3 and item.components.inventoryitem.owner==farmer)
assert(count_prefab(farmer,'poop')==3 and count_prefab(inst,'poop')==40)
''')

    def test_load_failure_returns_to_original_owner_and_slot(self):
        self.run_lua('''
local item=hold(material('bucket',{0,0,16},nil,5),1)
inst.components.container.GiveItem=function()return false end
assert(not store:LoadItem(item,farmer))
assert(farmer.components.inventory:GetItemInSlot(1)==item and item.components.inventoryitem.owner==farmer)
assert(item.hidden and farmer.children[item])
''')

    def test_failed_partial_transfer_merges_split_back_into_original_stack(self):
        self.run_lua('''
local item=hold(material('poop',{0,0,8},5),1)
inst.components.container.CanAcceptCount=function()return 2 end
inst.components.container.GiveItem=function()return false end
assert(not store:LoadItem(item,farmer))
assert(count_prefab(farmer,'poop')==5 and count_prefab(inst,'poop')==0)
''')

    def test_failed_load_falls_back_to_source_position_when_owner_cannot_receive(self):
        self.run_lua('''
local item=hold(material('bucket',{0,0,16},nil,5),1)
farmer.Transform:SetPosition(8,0,4)
inst.components.container.GiveItem=function()return false end
farmer.components.inventory.GiveItem=function()return false end
assert(not store:LoadItem(item,farmer))
assert(item:IsValid() and not item.hidden and item.components.inventoryitem.owner==nil)
local x,_,z=item.Transform:GetWorldPosition();assert(x==8 and z==4)
''')

    def test_duplicate_loading_same_machine_item_is_rejected(self):
        self.run_lua('''
local item=add_stock(material('bucket',{0,0,16},nil,5),2)
assert(not store:LoadItem(item,farmer) and store:GetFertilizerCount()==5)
''')

    def test_partial_acceptance_after_capacity_change_returns_only_remainder(self):
        self.run_lua('''
local dest=add_stock(material('poop',{0,0,8},38),2)
local item=hold(SpawnPrefab('poop'),1);item.components.stackable:SetStackSize(5)
local give=inst.components.container.GiveItem
inst.components.container.GiveItem=function(self,...)
 for i=3,9 do if not self.slots[i] then self.slots[i]=material('block'..i,{8,8,8},nil,1) end end
 return give(self,...)
end
local ok,n=store:LoadItem(item,farmer)
assert(ok and n==2 and dest.components.stackable:StackSize()==40)
assert(count_prefab(farmer,'poop')==3 and count_prefab(inst,'poop')==40)
''')

    def test_bounded_batch_can_complete_all_300_single_point_applications(self):
        self.run_lua('''
set_nutrients(0,0,0)
for i=1,3 do local n={0,0,0};n[i]=1;add_stock(material('slow'..i,n,nil,100),i+1)end
assert(Drive.WorkTile(inst,0,0));local a,b,c=nutrients()
assert(a==100 and b==100 and c==100 and inst._fuel:value()==799 and inst.components.finiteuses.used==1)
''')

    def test_native_extra_callback_runs_once_per_dose_and_failure_keeps_progress(self):
        self.run_lua('''
set_nutrients(84,100,100)
local item=add_stock(material('formula',{8,0,0},4),2);local calls=0
item.ondeployed_fertilzier_extra_fn=function(_,pt,worker)
 calls=calls+1;local x,y,z=pt:Get();assert(x==0 and z==0 and worker==farmer)
end
assert(Drive.WorkTile(inst,0,0));assert(calls==2 and count_prefab(inst,'formula')==2)
set_nutrients(92,100,100)
item.ondeployed_fertilzier_extra_fn=function()error('extra callback')end
start_fertilizer();Drive.TrackMovement(inst)
assert(not inst._working and count_prefab(inst,'formula')==1 and inst._fuel:value()==798)
local a=nutrients();assert(a==100)
''')

    def test_container_save_reload_preserves_partial_bucket_stack_and_no_double_owner(self):
        self.run_lua('''
local bucket=add_stock(material('bucket',{0,0,16},nil,5),2)
bucket.components.finiteuses:Use(2)
add_stock(material('poop',{0,0,8},9),3)
local saved=inst.components.container:OnSave()
local restored=engine_entity();restored.components.container=new_container(restored)
restored.components.container:OnLoad(saved,{})
local b=restored.components.container:GetItemInSlot(2)
assert(b~=bucket and b.components.finiteuses:GetUses()==3 and b.components.inventoryitem.owner==restored)
assert(count_prefab(restored,'poop')==9)
''')

    def test_legacy_attachment_uses_are_ignored_and_not_charged(self):
        self.run_lua('''
local tool=SpawnPrefab('aom_fertilizer')
Persistence.SetPersistData(tool,{finiteuses={uses=1}},{})
assert(tool.components.finiteuses==nil and tool.attachment_type=='fertilizer')
set_nutrients(0,0,0);add_stock(material('all',{100,100,100},2),2)
assert(Drive.WorkTile(inst,0,0));assert(tool:IsValid() and inst.components.finiteuses.used==1)
''')

    def test_full_action_loading_start_shortage_refill_save_resume_and_dismount(self):
        text=(ROOT/'mod/AgeOfMachines/modmain.lua').read_text()
        start=text.index('local AOM_LOAD = AddAction(');end=text.index('AOM_LOAD.distance',start)
        self.run_lua('function AddAction(_,_,fn)LoadAction=fn;return {}end')
        self.run_lua(text[start:end])
        self.run_lua('''
set_nutrients(0,0,0)
local item=hold(material('all',{8,8,8},2),1)
assert(LoadAction({target=inst,invobject=item,doer=farmer}))
assert(count_prefab(farmer,'all')==0)
farmer.components.rider={IsRiding=function()return true end,GetMount=function()return inst end}
function inst:DoPeriodicTask(_,fn)return {Cancel=function()end,fn=fn}end
assert(Drive.ToggleWorking(inst,farmer));Drive.TrackMovement(inst)
assert(not inst._working and inst._fuel:value()==799)
local refill=hold(material('strong',{32,32,32},3),1)
assert(LoadAction({target=inst,invobject=refill,doer=farmer}))
local saved=inst.components.container:OnSave()
inst.components.container=new_container(inst);inst.components.container:OnLoad(saved,{})
store:SetMaterialContainer(inst.components.container)
assert(Drive.ToggleWorking(inst,farmer));Drive.TrackMovement(inst)
local a,b,c=nutrients();assert(a==100 and b==100 and c==100 and inst._fuel:value()==798)
Drive.OnDismounted(inst);assert(not inst._working)
''')

if __name__=='__main__':unittest.main()
