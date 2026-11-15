"""原版喊话偏移/FollowText、真实骑乘生命周期及四档编译头部变换。"""
from pathlib import Path
from zipfile import ZipFile
import math
import unittest
import test_driver_visual as visual
from driver_animation import parse_anim, name_hash

ROOT = Path(__file__).resolve().parents[2]


class DriverSpeechTests(unittest.TestCase):
    def setUp(self):
        engine=visual.DriverVisualRuntimeTests();engine.setUp();self.lua=engine.lua
        self.lua.execute('''
Speech=require('aom_driver_speech');Native=dofile(REF..'/speech_anchor.lua')
Motion=require('aom_vehicle_motion')
local offset=Native.GetTalkerOffset
NECK={x=-35,y=-174}
p.components.talker={offset_fn=offset}
local widget={target=p,hashud=true,screen_offset=Vector3(0,0,0),offset=Vector3(0,0,0)}
function widget:SetPosition(x,y)self.x=x;self.y=y end
widget.OnUpdate=Native.OnUpdate;widget.GetScreenOffset=Native.GetScreenOffset
widget.SetScreenOffset=Native.SetScreenOffset;widget.SetOffset=Native.SetOffset
p.components.talker.widget=widget
p.AnimState.GetSymbolPosition=function(_,symbol,x,y,z)
 local scale=p.anim_scale and p.anim_scale[1] or 1
 if symbol=='headbase' then return p.x+(NECK.x+x)*scale,0,p.z+(NECK.y+y)*scale end
 return p.x+x*scale,0,p.z+y*scale
end
TheSim={FindEntities=function()return {}end,GetScreenPos=function(_,x,y,z)return x,-z end}
function say()widget.symbol=p.components.talker.symbol;widget:SetOffset(p.components.talker.offset_fn(p))end
function ride()assert(ACTIONS.MOUNT.fn({doer=p,target=t}));p.sg:GoToState('mounted_idle')end
''')

    def run_lua(self, source):self.lua.execute(source)

    def test_native_riding_offset_is_scaled_too_far_and_head_anchor_fixes_existing_line(self):
        self.run_lua('''
ride();Speech.Clear(p,t)
-- 真正远端只有复制的AnimState/骑手，没有服务端ApplyBuildOverrides留下的Lua标记。
TheWorld.ismastersim=false;t._aom_driver_animstate=nil
say();local widget=p.components.talker.widget
assert(widget.offset.y==-700 and widget.y==1750)
Motion.Update(t)
assert(widget.symbol=='headbase' and widget.offset.y==0 and widget.y==491)
assert(p.components.talker.offset_fn(p).y==0)
''')

    def test_rider_dirty_applies_remote_anchor_without_waiting_for_periodic_sample(self):
        self.run_lua('''
ride();Speech.Clear(p,t);TheWorld.ismastersim=false;t._aom_driver_animstate=nil
t:PushEvent('aomriderdirty')
assert(p.components.talker.symbol=='headbase' and p.components.talker.offset_fn(p).y==0)
assert(p.components.talker.widget.screen_offset.y==56)
t._rider_net:set(nil);t:PushEvent('aomriderdirty')
assert(p._aom_driver_speech==nil and p.components.talker.symbol==nil)
assert(p.components.talker.widget.offset.y==-700)
''')

    def test_separate_client_prefab_without_server_rider_components_gets_head_anchor(self):
        self.run_lua('''
TheWorld.ismastersim=false
local client=make_tractor()
assert(client.components.rideable==nil and client._aom_driver_animstate==nil)
client._rider_net:set(p)
for _,scale in ipairs({1.875,2.5,3.125,3.75}) do
 p.anim_scale={scale,scale,scale}
 client:PushEvent('aomriderdirty');say()
 local widget=p.components.talker.widget
 assert(widget.symbol=='headbase' and widget.offset.y==0)
 assert(math.abs(widget.y-(-NECK.y*scale+56))<.0001)
end
client._rider_net:set(nil);client:PushEvent('aomriderdirty')
assert(p._aom_driver_speech==nil and p.components.talker.symbol==nil)
''')

    def test_first_line_after_mount_and_recreated_widget_use_anchor_in_same_frame(self):
        self.run_lua('''
local widget=p.components.talker.widget;p.components.talker.widget=nil
ride();assert(p.components.talker.symbol=='headbase')
p.components.talker.widget=widget;say();p:PushEvent('ontalk')
assert(widget.symbol=='headbase' and widget.offset.y==0 and widget.screen_offset.y==56)
Speech.Clear(p,t);widget:SetScreenOffset(0,0);p:PushEvent('ontalk')
assert(widget.screen_offset.y==0) -- 清理后不留下喊话监听。
''')

    def test_turning_and_movement_follow_current_head_position_without_extra_world_offset(self):
        self.run_lua('''
ride();Motion.Update(t);say();local widget=p.components.talker.widget
NECK.x=45;NECK.y=-150;p.Transform:SetPosition(100,0,200)
Native.OnUpdate(widget)
assert(widget.x==212.5 and widget.y==231)
''')

    def test_actual_dismount_restores_original_offset_and_an_already_visible_line(self):
        self.run_lua('''
local original=p.components.talker.offset_fn
ride();Motion.Update(t);say();p.components.rider:ActualDismount();Motion.Update(t)
assert(p.components.talker.offset_fn==original and p.components.talker.symbol==nil)
assert(p._aom_driver_speech==nil and p.components.talker.widget.offset.y==-400)
assert(p.components.talker.widget.screen_offset.y==0)
say();assert(p.components.talker.widget.y==400)
''')

    def test_missing_driver_assets_and_other_mounts_keep_native_riding_offset(self):
        self.run_lua('''
Visual.ready=false;ride();Motion.Update(t);say()
assert(p.components.talker.symbol==nil and p.components.talker.widget.offset.y==-700)
assert(p._aom_driver_speech==nil)
''')

    def test_external_offset_changes_are_preserved_and_old_vehicle_cannot_clear_new_owner(self):
        self.run_lua('''
ride();Motion.Update(t)
local newer={_aom_driver_animstate=p.AnimState};Speech.Update(newer,p)
Speech.Clear(p,t);assert(p._aom_driver_speech.vehicle==newer)
local custom=function()return Vector3(8,-450,0)end;p.components.talker.offset_fn=custom
Speech.Clear(p,newer)
assert(p.components.talker.offset_fn==custom and p.components.talker.symbol==nil)
assert(p.components.talker.widget.offset.x==8)
''')

    def test_vehicle_removal_and_client_updates_release_or_apply_the_same_anchor(self):
        self.run_lua('''
ride();TheWorld.ismastersim=false;Motion.Update(t)
assert(p.components.talker.symbol=='headbase')
TheWorld.ismastersim=true;t:Remove()
assert(p._aom_driver_speech==nil and p.components.talker.symbol==nil)
''')

    def test_late_widget_creation_and_replacement_never_accumulate_screen_gap(self):
        self.run_lua('''
local first=p.components.talker.widget;p.components.talker.widget=nil
ride();Motion.Update(t)
p.components.talker.widget=first;say();Motion.Update(t)
for i=1,20 do Motion.Update(t)end
assert(first.screen_offset.y==56)
local second={target=p,hashud=true,screen_offset=Vector3(7,12,0),offset=Vector3(0,0,0),OnUpdate=Native.OnUpdate}
second.SetPosition=first.SetPosition;second.SetOffset=first.SetOffset
second.SetScreenOffset=first.SetScreenOffset;second.GetScreenOffset=first.GetScreenOffset
p.components.talker.widget=second;Motion.Update(t)
assert(first.screen_offset.y==0 and second.screen_offset.x==7 and second.screen_offset.y==68)
Speech.Clear(p,t);assert(second.screen_offset.x==7 and second.screen_offset.y==12)
''')

    def test_screen_gap_is_constant_across_model_sizes_and_camera_projection(self):
        self.run_lua('''
ride();Motion.Update(t);say();local widget=p.components.talker.widget
for _,scale in ipairs({1.875,2.5,3.125,3.75})do
 p.anim_scale={scale,scale,scale}
 for _,zoom in ipairs({.5,1,1.5})do
  TheSim.GetScreenPos=function(_,x,y,z)return x*zoom,-z*zoom end
  Native.OnUpdate(widget)
  assert(widget.y-(-NECK.y*scale*zoom)==56)
 end
end
''')

    def test_external_screen_offset_is_preserved_on_cleanup(self):
        self.run_lua('''
ride();Motion.Update(t);p.components.talker.widget:SetScreenOffset(9,99)
Speech.Clear(p,t);assert(p.components.talker.widget.screen_offset.y==99)
''')

    def test_all_compiled_sizes_and_five_views_have_a_head_with_constant_text_gap(self):
        for suffix,scale in [('_075',1.875),('',2.5),('_125',3.125),('_150',3.75)]:
            with ZipFile(ROOT/f'mod/Tractor/anim/aom_tractor_driver{suffix}.zip') as archive:
                anim=parse_anim(archive.read('anim.bin'))
            views=set()
            for a in anim['animations']:
                if a['name'] not in ('idle_loop','run_loop','pickup','pickup_pst'):continue
                for index,frame in enumerate(a['frames']):
                    head=next(e for e in frame['elements'] if e['symbol']==name_hash('headbase'))
                    matrix=head['matrix'];views.add(a['facing'])
                    # Zero local offset anchors exactly at the compiled head; screen gap
                    # is added by FollowText afterward and cannot inherit this scale.
                    self.assertTrue(all(math.isfinite(v) for v in matrix))
                    self.assertLess(abs(matrix[5]*scale),700*scale)
            self.assertEqual(views,{5,48,192,2,8})


if __name__=='__main__':unittest.main()
