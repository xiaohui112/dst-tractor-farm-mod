"""规划开始、进度与结束沿用墙钟秒表，全流程不写日志。"""
import unittest
from test_giant_farming import World


class PlanStopwatchTests(unittest.TestCase):
    def setUp(self):
        self.lua = World().lua
        self.lua.execute('''
print=function()error('planning must not print into the master log')end
io.open=function()error('planning must not open files')end
package.preload.aom_plan_log=function()error('planning logger must not load')end
Timing=require('aom_plan_timing')
NOW=100;os.time=function()return NOW end
said={};vehicle={GUID=42,_rider={components={talker={
 Say=function(_,text,duration,noanim)said[#said+1]={text=text,duration=duration,noanim=noanim}end
}}}}
vehicle._planprogress_net={set=function(_,text)vehicle.progress=text end}
''')

    def test_start_progress_and_end_use_same_real_elapsed_time_without_io(self):
        self.lua.execute('''
Timing.Request(vehicle);NOW=110
trace=Timing.New(vehicle,0,0)
assert(#said==1 and string.find(said[1].text,'0秒',1,true))
trace:Progress();assert(#said==1)
trace:TickBegin();trace:Stage('field_scan')
NOW=111;trace:Progress();assert(#said==1)
NOW=112;trace:Progress();trace:Progress()
assert(#said==2 and string.find(said[2].text,'2秒',1,true))
assert(said[2].duration==3 and said[2].noanim==true)
NOW=113;trace:TickEnd('complete')
trace:Complete('complete',nil,{total=8,upper=8,optimal=true})
assert(#said==3 and string.find(said[3].text,'用时3秒',1,true))
assert(vehicle.progress==said[3].text)
NOW=120;trace:Progress(true);assert(#said==3 and trace.completed_seconds==3)
trace:Stage('first_seed');trace:FirstSeed({crop='potato',x=0,z=0})
trace:Sown({crop='potato'},{done=8,total=8});trace:Abort('STOP')
assert(trace.finished and trace.first_seed and trace.execution_finished)
for _,message in ipairs(said)do assert(not string.find(message.text,'写入失败',1,true))end
assert(not package.loaded.aom_plan_log)
''')

    def test_cancelled_or_failed_timer_stops_once_without_io(self):
        for status in ('cancelled', 'failed'):
            with self.subTest(status=status):
                self.setUp()
                self.lua.globals().STATUS = status
                self.lua.execute('''
trace=Timing.New(vehicle,0,0);vehicle._aom_plan_trace=trace
NOW=104;trace:Complete(STATUS,'TEST_STOP')
assert(trace.finished and trace.completed_seconds==4 and trace.reason=='TEST_STOP')
local count=#said;NOW=120;trace:Progress(true);trace:Abort('AGAIN')
assert(#said==count and string.find(said[count].text,'4秒',1,true))
assert(not trace.first_seed and not package.loaded.aom_plan_log)
''')

    def test_quiet_background_timer_remains_silent_without_io(self):
        self.lua.execute('''
trace=Timing.New(vehicle,0,0,true)
NOW=102;trace:Stage('field_scan');trace:Progress(true)
NOW=103;trace:Abort('BACKGROUND_STOP')
assert(#said==0 and vehicle.progress==nil and trace.finished)
assert(trace.completed_seconds==3 and not package.loaded.aom_plan_log)
''')
