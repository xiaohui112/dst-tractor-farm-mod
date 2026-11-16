"""实机截图反馈：非血量底色、水条图层、紧凑布局与数字牌叠层。"""
import unittest
import test_dashboard as dashboard


class DashboardStyleTests(unittest.TestCase):
    setUp=dashboard.DashboardTests.setUp
    run_lua=dashboard.DashboardTests.run_lua

    def test_only_health_uses_native_red_backing(self):
        self.run_lua('''
assert(hud.badges.health.meter.backing:GetAnimState().SetBank_args[1]=='status_meter')
for _,kind in ipairs({'chassis','fuel','tool','cargo'})do
 local badge=hud.badges[kind]
 assert(badge.meter.backing:GetAnimState().SetBank_args[1]=='status_clear_bg')
 local c=badge.meter.backing:GetAnimState().SetMultColour_args
 assert(c[1]/c[2]<1.1 and c[1]<.5 and c[4]==1)
 assert(badge.meter.scale[1]==1)
end
''')

    def test_water_drop_dial_shows_empty_half_and_full_without_lower_strip(self):
        self.run_lua('''
for _,water in ipairs({0,1,200,399,400})do
 t._water_net:set(water);t._watermax_net:set(400);hud:Refresh(t)
 assert(hud.badges.water:GetText()==tostring(water) and hud.badges.water.meter.percent==water/400)
 assert(hud.strip==nil and hud.resource_fill==nil)
end
''')

    def test_all_seed_modes_have_no_planning_controls_or_lower_square(self):
        self.run_lua('''
for _,kind in ipairs({'plow','weeder','harvester','fertilizer','seeder','irrigator'})do
 for _,mode in ipairs({'SEQUENTIAL','GIANT'})do
  t._atttype_net:set(kind);t._seedmode_net:set(mode);hud:Refresh(t)
  assert(hud.strip==nil and hud.seedcontrols==nil and hud.planbutton==nil and hud.rotatebutton==nil)
 end
end
''')

    def test_numeric_plate_and_large_text_share_one_aligned_cell(self):
        self.run_lua('''
t._uses_net:set(1000);t._cargo_used_net:set(9);t._cargo_count_net:set(9);hud:Refresh(t)
for _,kind in ipairs(hud.order)do
 local badge=hud.badges[kind]
 assert(badge.plate.render_size[1]==58 and badge.plate.render_size[2]==32)
 assert(badge.size==26 and badge.text.size==26)
 assert(badge.text.position[1]==badge.plate.position[1])
 assert(badge.text.position[2]==badge.plate.position[2] and badge.text.position[2]==-40)
 assert(badge.text:IsVisible() and not badge.meter.num:IsVisible())
end
assert(hud.badges.chassis:GetText()=='1000' and hud.badges.cargo:GetText()=='9')
''')

    def test_combined_status_extra_number_background_is_hidden_only_on_our_badges(self):
        self.run_lua('''
local NativeBadge=require('widgets/badge')
local Image=require('widgets/image');local Text=require('widgets/text')
-- 重现本机综合状态显示BadgePostConstruct的缩放、bg与maxnum注入。
package.loaded['widgets/badge']=function(...)
 local b=NativeBadge(...);b:SetScale(.9)
 b.bg=b:AddChild(Image('images/ui.xml','button_small.tex'))
 b.maxnum=b:AddChild(Text(NUMBERFONT,25,'100'));b.num:Show()
 local set=b.SetPercent
 b.SetPercent=function(self,...)
  set(self,...);self.bg:Show();self.num:Show();self.maxnum:Show()
 end
 return b
end
package.loaded['widgets/aom_badge']=nil;package.loaded['widgets/aom_hud']=nil
local unrelated=package.loaded['widgets/badge'](nil,player)
local fresh=require('widgets/aom_hud')(player)
for _=1,3 do
 fresh:Refresh(t)
 for _,kind in ipairs(fresh.order)do
  local b=fresh.badges[kind]
  assert(b.meter.scale[1]==1 and not b.meter.bg:IsVisible())
  assert(not b.meter.maxnum:IsVisible() and not b.meter.num:IsVisible())
  assert(b.plate:IsVisible() and b.text:IsVisible())
 end
end
assert(unrelated.bg:IsVisible() and unrelated.maxnum:IsVisible() and unrelated.scale[1]==.9)
''')

    def test_layout_refresh_keeps_seed_dial_pressed_until_single_release(self):
        self.run_lua('''
attach('aom_seeder');t:CycleSeedStrategy(player);hud:Refresh(t)
local button=hud.badges.tool;button:OnGainFocus()
assert(button:OnControl(CONTROL_PRIMARY,true) and button.down)
local x,y=button.position[1],button.position[2]
for _=1,20 do
 hud:Refresh(t);assert(button.down and button.position[1]==x and button.position[2]==y and t._seed_strategy=='GIANT_TEMPLATE')
end
assert(button:OnControl(CONTROL_PRIMARY,false));assert(t._seed_strategy=='GIANT')
''')


if __name__=='__main__':unittest.main()
