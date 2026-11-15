"""货仓逐列对齐人物栏，含5/6、10/11分组及原版Rebuild的RefreshPosition路径。"""
import unittest
import test_dashboard as dashboard


class CargoAlignmentTests(unittest.TestCase):
    setUp=dashboard.DashboardTests.setUp
    run_lua=dashboard.DashboardTests.run_lua

    def prepare(self):
        self.run_lua('''
Cargo=require('aom_cargo');UI=require('widgets/aom_cargo_widget')
local _,_,native_refresh=dofile(REF..'/inventory_container.lua')()
local function slot(x)
 return {x=x,GetPosition=function(self)return Vector3(self.x,0,0)end,
  SetPosition=function(self,p)self.x=p.x;self.y=p.y end}
end
bar={inv={}}
-- 原版 inventorybar: x += W + (k % 5 == 0 and INTERSEP or SEP)
local x=-700;local W,SEP,INTERSEP=68,12,28
for i=1,15 do bar.inv[i]=slot(x);x=x+W+(i%5==0 and INTERSEP or SEP)end
player.HUD={controls={inv=bar}}
w={owner=player,container=t,inv={},isopen=false,refreshes=0,
 SetPosition=function(self,p)self.position=p end,
 SetScale=function(self,n)self.scale=n end,
 bgimage={ScaleToSize=function(self,a,b)self.width=a;self.height=b end,SetClickable=function()end}}
for i=1,15 do w.inv[i]=slot(0);w.inv[i].tile={index=i}end
function w:Open(container,owner)
 self.container=container;self.owner=owner;self.isopen=true
 self:SetPosition(Cargo.Position(container,owner))
 for i,p in ipairs(Cargo.SlotPositions(container,owner))do self.inv[i]:SetPosition(p)end
end
function w:Close()self.isopen=false end
function w:RefreshPosition()self.refreshes=self.refreshes+1;return native_refresh(self)end
UI.Install(w);w:Open(t,player)
function check_columns()
 for i=1,15 do
  assert(w.position.x+w.inv[i].x==bar.inv[i]:GetPosition().x,'column '..i)
  assert(w.inv[i].tile.index==i)
 end
 assert(w.position.y==80 and w.scale==1)
 assert(w.bgimage.width==bar.inv[15].x-bar.inv[1].x+128)
end
''')

    def test_open_matches_all_fifteen_columns_including_both_group_separators(self):
        self.prepare();self.run_lua('''
check_columns()
assert(w.inv[6].x-w.inv[5].x==96 and w.inv[11].x-w.inv[10].x==96)
assert(w.inv[5].x-w.inv[4].x==80 and w.bgimage.width==1280)
assert(#Cargo.SlotPositions(t,player)==15)
''')

    def test_inventory_rebuild_updates_positions_and_background_without_recreating_slots(self):
        self.prepare();self.run_lua('''
local original=w.inv[6]
-- 背包/控制器或其他Mod改变人物栏位置与分组间距。
for i,slot in ipairs(bar.inv)do slot.x=-810+(i-1)*75+math.floor((i-1)/5)*22 end
w:RefreshPosition();check_columns()
assert(w.inv[6]==original and w.inv[6].x-w.inv[5].x==97)
assert(w.inv[11].x-w.inv[10].x==97)
for _,scale in ipairs({.8,1,1.4})do
 -- 两行共用物品栏父节点，HUD缩放不产生第二次独立缩放。
 w:SetScale(scale);check_columns()
 for i=1,15 do assert((w.position.x+w.inv[i].x)*scale==bar.inv[i].x*scale)end
end
''')

    def test_close_reopen_preserves_alignment_and_other_containers_use_native_refresh(self):
        self.prepare();self.run_lua('''
w:Close();assert(w._aom_cargo_owner==nil and not w._aom_integrated_cargo and w.scale==.6)
w:RefreshPosition();assert(w.refreshes==1)
for _,slot in ipairs(bar.inv)do slot.x=slot.x-50 end
w:Open(t,player);check_columns()
local root=hud.root.position[2];hud:Refresh(t)
assert(hud.root.position[2]==root)
''')

    def test_missing_hud_uses_native_group_spacing_and_keeps_first_slot_anchor(self):
        self.run_lua('''
local Cargo=require('aom_cargo');player.HUD=nil
local slots,position,width=Cargo.Layout(player)
assert(#slots==15 and width==1280 and position.x==0)
assert(slots[6].x-slots[5].x==96 and slots[11].x-slots[10].x==96)
player.HUD={controls={inv={inv={{GetPosition=function()return Vector3(-750,0,0)end}}}}}
slots,position,width=Cargo.Layout(player)
assert(position.x+slots[1].x==-750 and width==1280)
''')


if __name__=='__main__':unittest.main()
