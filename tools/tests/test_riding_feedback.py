"""执行原版mount时间线：拖拉机无牛叫，其他坐骑与发动机声音保留。"""
import unittest
import test_world_equipment as world


class RidingFeedbackTests(unittest.TestCase):
    def setUp(self):
        world.WorldEquipmentTests.setUp(self)
        self.lua.execute('''
function TimeEvent(time,fn)return {time=time,fn=fn}end
graph={states={mount={timeline=dofile(REF..'/mount_timeline.lua')}}}
assert(SG_POST_FNS.wilson);SG_POST_FNS.wilson(graph)
sounds={};player.SoundEmitter.PlaySound=function(_,name)sounds[#sounds+1]=name end
player.sg.statemem={heavy=false,ridingwoby=false}
function voice()
 for _,e in ipairs(graph.states.mount.timeline)do if e.time==14*FRAMES then return e.fn(player)end end
 error('native mount voice event missing')
end
''')

    run_lua=world.WorldEquipmentTests.run_lua

    def test_tractor_mount_has_no_grunt_and_keeps_other_frames_and_engine(self):
        self.run_lua('''
ride();player.sg.statemem={heavy=false,ridingwoby=false}
for _,event in ipairs(graph.states.mount.timeline)do event.fn(player)end
assert(#sounds==2 and sounds[1]=='dontstarve/beefalo/saddle/dismount')
assert(sounds[2]=='dontstarve/movement/bodyfall_dirt')
require('aom_vehicle_motion').Update(t)
assert(sounds[3]=='aom_tractor_sfx/tractor/idle')
''')

    def test_beefalo_woby_heavy_and_no_mount_keep_native_voice_behavior(self):
        self.run_lua('''
local other=CreateEntity();player.components.rider.GetMount=function()return other end
voice();assert(#sounds==1 and sounds[1]=='dontstarve/beefalo/grunt')
player.sg.statemem.ridingwoby=true;voice()
assert(#sounds==2 and sounds[2]=='dontstarve/characters/walter/woby/big/bark')
player.sg.statemem.ridingwoby=false;player.sg.statemem.heavy=true;voice();assert(#sounds==2)
player.sg.statemem.heavy=false;player.components.rider.GetMount=function()return nil end
voice();assert(#sounds==3 and sounds[3]=='dontstarve/beefalo/grunt')
player.components.rider.target_mount=t;voice();assert(#sounds==3)
''')

    def test_hook_is_idempotent_and_accepts_graphs_without_mount_state(self):
        self.run_lua('''
local original={};for i,event in ipairs(graph.states.mount.timeline)do original[i]=event.fn end
SG_POST_FNS.wilson(graph)
for i,event in ipairs(graph.states.mount.timeline)do assert(original[i]==event.fn)end
SG_POST_FNS.wilson({states={}});SG_POST_FNS.wilson({states={mount={}}})
''')


if __name__=='__main__':unittest.main()
