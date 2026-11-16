"""15格独立货仓、满格选择性收割及原版物品栏容器挂接。"""
import unittest
import test_work_cargo as cargo
import test_dashboard as dashboard


class SelectiveHarvestTests(unittest.TestCase):
    def setUp(self):
        cargo.WorkCargoTests.setUp(self)
        self.lua.execute('''
function stock(slot,name,n)
 local old=t.components.container:RemoveItemBySlot(slot);if old then old:Remove()end
 local e=SpawnPrefab(name);e.components.stackable:SetStackSize(n)
 assert(t.components.container:GiveItem(e,slot));return e
end
''')

    run_lua = cargo.WorkCargoTests.run_lua

    def test_all_fifteen_slots_hold_cargo_and_last_slot_survives_reload(self):
        self.run_lua('''
assert(t.components.container:GetNumSlots()==15);fill()
stock(15,'tomato_seeds',31)
assert(t._cargo_used_net:value()==15 and t._cargo_count_net:value()==14*40+31)
local record=clone(t:GetSaveRecord());t:Remove();local loaded=SpawnSaveRecord(record)
assert(loaded.components.container:GetNumSlots()==15)
assert(loaded.components.container:GetItemInSlot(15).components.stackable:StackSize()==31)
assert(loaded:GetAttachment().prefab=='aom_harvester')
''')

    def test_old_sixteenth_slot_merges_then_preserves_overflow_on_ground(self):
        self.run_lua('''
fill();stock(1,'tomato_seeds',35)
local record=clone(t:GetSaveRecord());local extra=SpawnPrefab('tomato_seeds')
extra.components.stackable:SetStackSize(12)
record.data.container.items[16]=clone(extra:GetSaveRecord());extra:Remove();t:Remove()
local loaded=SpawnSaveRecord(record)
assert(loaded.components.container:GetNumSlots()==15)
assert(loaded.components.container:GetItemInSlot(1).components.stackable:StackSize()==40)
assert(quantity(loaded,'tomato_seeds')==40 and quantity(nil,'tomato_seeds')==7)
local nextrecord=clone(loaded:GetSaveRecord());assert(nextrecord.data.container.items[16]==nil)
loaded:Remove();local again=SpawnSaveRecord(nextrecord)
assert(quantity(again,'tomato_seeds')==40 and quantity(nil,'tomato_seeds')==7)
''')

    def test_old_sixteenth_slot_moves_into_free_space_after_restoring_saved_slots(self):
        self.run_lua('''
stock(1,'tomato_seeds',40)
local record=clone(t:GetSaveRecord());local extra=SpawnPrefab('corn_seeds')
extra.components.stackable:SetStackSize(23)
record.data.container.items[16]=clone(extra:GetSaveRecord());extra:Remove();t:Remove()
local loaded=SpawnSaveRecord(record)
assert(quantity(loaded,'tomato_seeds')==40 and quantity(loaded,'corn_seeds')==23)
assert(quantity(nil,'corn_seeds')==0 and loaded.components.container:GetItemInSlot(16)==nil)
''')

    def test_legacy_nine_occupied_slots_expand_without_changing_saved_contents(self):
        self.run_lua('''
for i=1,9 do stock(i,'tomato_seeds',i)end
local record=clone(t:GetSaveRecord());t:Remove();local loaded=SpawnSaveRecord(record)
assert(loaded.components.container:GetNumSlots()==15)
for i=1,9 do assert(loaded.components.container:GetItemInSlot(i).components.stackable:StackSize()==i)end
for i=10,15 do assert(loaded.components.container:GetItemInSlot(i)==nil)end
assert(loaded._cargo_count_net:value()==45)
''')

    def test_full_slots_skip_new_crop_and_continue_two_existing_crop_types(self):
        self.run_lua('''
fill();stock(1,'tomato',38);stock(2,'corn',37)
local skip=crop('onion',0,0,false)
for i=1,2 do crop('tomato',i*.4,0,false)end
for i=1,3 do crop('corn',i*.4,1,false)end
t:SetWorking(true);local changed,why=Drive.WorkTile(t,0,0)
assert(changed and why=='CARGO_FULL' and not t._working)
assert(skip:IsValid() and skip.components.pickable:CanBePicked())
assert(quantity(t,'tomato')==40 and quantity(t,'corn')==40)
assert(quantity(nil,'tomato_seeds')==2 and quantity(nil,'corn_seeds')==3)
assert(t._fuel:value()==399 and t:GetAttachment().components.finiteuses:GetUses()==99)
''')

    def test_unaccepted_ground_item_does_not_block_existing_crop_stack(self):
        self.run_lua('''
fill();stock(1,'tomato',30)
local old=SpawnPrefab('rocks');old.Transform:SetPosition(0,0,0)
local plant=crop('tomato',1,0,false)
t:SetWorking(true);assert(Drive.WorkTile(t,0,0) and not plant:IsValid() and t._working)
assert(old:IsValid() and old.components.inventoryitem.owner==nil)
assert(quantity(t,'tomato')==31 and quantity(nil,'tomato_seeds')==1)
assert(require('aom_work_status').Describe(t)=='')
''')

    def test_only_unmatched_crops_are_left_standing_and_driving_continues_without_cost(self):
        self.run_lua('''
fill();stock(1,'corn',30);local plant=crop('tomato',0,0,false)
t:SetWorking(true);local changed,why=Drive.WorkTile(t,0,0)
assert(not changed and why==nil and t._working and plant:IsValid())
assert(t._fuel:value()==400 and quantity(nil,'tomato')==0)
local nextplant=crop('corn',4,0,false);assert(Drive.WorkTile(t,4,0))
assert(not nextplant:IsValid() and t._working and quantity(t,'corn')==31)
''')

    def test_last_stack_room_stops_once_and_does_not_pick_the_next_crop(self):
        self.run_lua('''
fill();stock(1,'tomato',39);stock(2,'tomato',39)
local a=crop('tomato',0,0,false);local b=crop('tomato',1,0,false);local nextplant=crop('tomato',0,1,false)
local messages={};player.components.talker={Say=function(_,text)messages[#messages+1]=text end}
t:SetWorking(true);local changed,why=Drive.WorkTile(t,0,0)
assert(changed and why=='CARGO_FULL' and quantity(t,'tomato')==80)
assert(not a:IsValid() and not b:IsValid() and nextplant:IsValid())
assert(#messages==1 and not t._working)
Drive.WorkTile(t,0,0);assert(#messages==1 and t._fuel:value()==399)
''')

    def test_a_free_slot_still_allows_new_crop_and_seeds_do_not_block_next_matching_crop(self):
        self.run_lua('''
fill();stock(1,'corn',30);t.components.container:RemoveItemBySlot(2):Remove()
local first=crop('tomato',0,0,false);local second=crop('corn',1,0,false)
t:SetWorking(true);assert(Drive.WorkTile(t,0,0))
assert(not first:IsValid() and not second:IsValid() and t._working)
assert(quantity(t,'tomato')==1 and quantity(t,'corn')==31)
assert(quantity(nil,'tomato_seeds')==1 and quantity(nil,'corn_seeds')==1)
''')

    def test_oversized_harvest_preserves_every_native_drop_when_only_fruit_fits(self):
        self.run_lua('''
fill();stock(1,'tomato',39);local plant=crop('tomato',0,0,true)
t:SetWorking(true);local changed,why=Drive.WorkTile(t,0,0)
assert(changed and why=='CARGO_FULL' and not plant:IsValid())
assert(quantity(t,'tomato')==40)
assert(quantity(t,'tomato')-39+quantity(nil,'tomato')+quantity(nil,'tomato_seeds')==5)
assert(quantity(nil,'tomato_oversized')==0 and quantity(player,'tomato')==0)
''')

    def test_incompatible_skin_or_custom_stacking_rule_does_not_destroy_crop(self):
        self.run_lua('''
fill();local stored=stock(1,'tomato',30);local plant=crop('tomato',0,0,false)
stored.skinname='custom';t:SetWorking(true)
assert(not Drive.WorkTile(t,0,0) and plant:IsValid() and t._working)
stored.skinname=nil;stored.stackable_CanStackWithFn=function()return false end
assert(not Drive.WorkTile(t,0,0) and plant:IsValid() and t._fuel:value()==400)
''')

    def test_seed_stack_room_alone_does_not_pick_an_unstorable_fruit(self):
        self.run_lua('''
fill();stock(1,'tomato_seeds',30);local plant=crop('tomato',0,0,false)
t:SetWorking(true);assert(not Drive.WorkTile(t,0,0))
assert(plant:IsValid() and quantity(t,'tomato_seeds')==30 and quantity(nil,'tomato')==0)
assert(t._working and t._fuel:value()==400)
''')

    def test_actual_plant_definition_product_takes_precedence_over_prefab_name(self):
        self.run_lua('''
fill();stock(1,'corn',30);local plant=crop('tomato',0,0,false)
plant.plant_def={product='corn'};plant.components.lootdropper.loot={'corn'}
t:SetWorking(true);assert(Drive.WorkTile(t,0,0))
assert(not plant:IsValid() and quantity(t,'corn')==31 and t._working)
''')


class IntegratedCargoWidgetTests(unittest.TestCase):
    setUp = dashboard.DashboardTests.setUp
    run_lua = dashboard.DashboardTests.run_lua

    def test_fifteen_slot_row_is_symmetric_and_uses_inventory_parent_with_no_titles(self):
        self.run_lua('''
local params=require('containers').params.aom_tractor_chassis
assert(params.type=='inv' and not params.issidewidget and #params.widget.slotpos==15)
local firstx=-640
player.HUD={controls={inv={inv={{GetPosition=function()return Vector3(firstx,0,0)end}}}}}
assert(params.widget.posfn(t,player).x+params.widget.slotpos[1].x==firstx)
firstx=-720;assert(params.widget.posfn(t,player).x+params.widget.slotpos[1].x==firstx)
assert(params.widget.pos.x==0 and params.widget.pos.y==80 and params.widget.bgimage=='inventory_bg.tex')
for i,p in ipairs(params.widget.slotpos)do
 assert(p.y==0 and p.x==(i-1)*80+math.floor((i-1)/5)*16-576)
 assert(p.x==-params.widget.slotpos[16-i].x)
end
local function parent()
 return {AddChild=function(self,child)self.child=child;child.parent=self;return child end}
end
local row=parent();local popup=parent()
local controls={inv={toprow_inv=row,OnNewContainerWidget=function()end},containerroot=popup,containers={}}
local frame={owner=player,controls=controls,CloseSpellWheel=function()error('must not use floating chest parent')end}
local function window()
 local w={owner=player,Open=function(self)self.isopen=true end,Close=function(self)self.isopen=false end,
 SetScale=function(self,x,y,z)self.scale={x,y,z}end,MoveToBack=function()end,
 SetPosition=function(self,p)self.position=p end,
 bgimage={ScaleToSize=function(self,w,h)self.size={w,h}end,SetClickable=function()end}}
 POST_FNS['widgets/containerwidget'](w);return w
end
t.replica.container.type=params.type
local NativeOpen=dofile(REF..'/inventory_container.lua')(window)
NativeOpen(frame,t,false)
local w=controls.containers[t]
assert(w.parent==row and popup.child==nil and w.scale[1]==1 and w.bgimage.size[1]==1280)
assert(w.aom_storage_title==nil and w.aom_storage_hint==nil)
w:SetScale(.8);assert(w.scale[1]==1)
w:Close();assert(w.scale[1]==.6 and not w.isopen)
w:SetScale(.7,.8,.9);assert(w.scale[1]==.7 and w.scale[2]==.8 and w.scale[3]==.9)
''')

    def test_dials_and_seed_controls_stay_fixed_when_cargo_opens_and_closes(self):
        self.run_lua('''
local normal=hud.root.position[2];hud.badges.cargo.onclick();hud:Refresh(t)
assert(t.components.container:IsOpenedBy(player) and hud.root.position[2]==normal)
assert(hud.seedcontrols==nil)
hud.badges.cargo.onclick();hud:Refresh(t)
assert(hud.root.position[2]==normal and hud.seedcontrols==nil)
''')

    def test_native_inventory_rebuild_preserves_the_integrated_cargo_parent(self):
        self.run_lua('''
local function node()
 local n={children={}}
 function n:AddChild(child)
  if child.parent then child.parent.children[child]=nil end
  self.children[child]=true;child.parent=self;return child
 end
 function n:RemoveChild(child)self.children[child]=nil;child.parent=nil end
 function n:Kill()self.killed=true;for child in pairs(self.children)do child:Kill()end end
 return n
end
local root=node();local inventory={root=root}
inventory.toprow=root:AddChild(node());inventory.bottomrow=root:AddChild(node())
inventory.toprow_inv=inventory.toprow:AddChild(node())
local cargo=inventory.toprow_inv:AddChild(node());local oldrow=inventory.toprow
local _,RebuildRows=dofile(REF..'/inventory_container.lua')(nil,node)
RebuildRows(inventory)
assert(oldrow.killed and not cargo.killed and cargo.parent==inventory.toprow_inv)
assert(inventory.toprow_inv.parent==inventory.toprow)
RebuildRows(inventory);assert(not cargo.killed and cargo.parent==inventory.toprow_inv)
''')


if __name__ == '__main__':unittest.main()
