"""用真实文件IO核对独立规划日志及人物头顶计时；不替代游戏渲染验收。"""
from pathlib import Path
import tempfile
import unittest
from test_giant_farming import World


class PlanStopwatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.lua = World().lua
        self.lua.globals().LOGPATH = str(self.root / 'planning.log')
        self.lua.execute('''
print=function()error('planning must not print into the master log')end
Log=require('aom_plan_log');Log.Configure(nil,LOGPATH)
Timing=require('aom_plan_timing')
NOW=100;os.time=function()return NOW end
said={};vehicle={GUID=42,_rider={components={talker={
 Say=function(_,text,duration,noanim)said[#said+1]={text=text,duration=duration,noanim=noanim}end
}}}}
vehicle._planprogress_net={set=function(_,text)vehicle.progress=text end}
''')

    def contents(self):
        return (self.root / 'planning.log').read_text()

    def test_start_progress_and_end_use_same_real_elapsed_time(self):
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
''')
        log = self.contents()
        self.assertIn('[START]', log)
        self.assertIn('start_epoch_seconds=110', log)
        self.assertIn('timer_origin=planning_task_created', log)
        self.assertIn('elapsed_s=2', log)
        self.assertIn('planning_elapsed_seconds=3', log)
        self.assertIn('end_epoch_seconds=113', log)
        self.assertIn('wall_precision_ms=1000', log)
        self.assertIn('execution_mode=world_serial_sliced', log)
        self.assertEqual(log.count('[END]'), 1)

    def test_cancelled_or_failed_timer_stops_once(self):
        for status in ('cancelled', 'failed'):
            with self.subTest(status=status):
                self.setUp()
                self.lua.globals().STATUS = status
                self.lua.execute('''
trace=Timing.New(vehicle,0,0);vehicle._aom_plan_trace=trace
NOW=104;trace:Complete(STATUS,'TEST_STOP')
assert(trace.finished and trace.completed_seconds==4)
local count=#said;NOW=120;trace:Progress(true);trace:Abort('AGAIN')
assert(#said==count and string.find(said[count].text,'4秒',1,true))
''')
                log = self.contents()
                self.assertIn('status=' + status, log)
                self.assertEqual(log.count('[END]'), 1)
                self.assertNotIn('[FIRST_SEED]', log)

    def test_history_appended_across_logger_reconfiguration(self):
        self.lua.execute('''
assert(Log.Append('older planning record'))
Log.Configure(nil,LOGPATH)
trace=Timing.New(vehicle,0,0);NOW=102;trace:Abort('STOP')
''')
        self.assertTrue(self.contents().startswith('older planning record\n'))
        self.assertIn('[START]', self.contents())
        self.assertIn('[END]', self.contents())

    def test_write_failure_reports_on_head_without_print_or_crash(self):
        self.lua.globals().BADPATH = str(self.root / 'missing' / 'planning.log')
        self.lua.execute('''
Log.Configure(nil,BADPATH)
local ok,err=Log.Append('test');assert(not ok and err)
trace=Timing.New(vehicle,0,0)
assert(string.find(said[1].text,'规划日志写入失败',1,true))
NOW=101;trace:Complete('complete',nil,{total=8,upper=8,optimal=true})
assert(trace.planning and trace.completed_seconds==1)
assert(string.find(said[#said].text,'规划日志写入失败',1,true))
''')
        self.assertFalse((self.root / 'missing').exists())

    def test_master_and_caves_have_separate_log_files(self):
        directory = self.root / 'Documents/Klei/DoNotStarveTogether'
        directory.mkdir(parents=True)
        self.lua.globals().TESTHOME = str(self.root)
        self.lua.execute('''
os.getenv=function(name)if name=='HOME'then return TESTHOME end end
TheSim={GetRealTime=function()return 0 end}
Log.Configure('/unneeded/')
assert(Log.Path()==TESTHOME..'/Documents/Klei/DoNotStarveTogether/tractor_giant_planning_master.log')
assert(Log.Append('master planning record'))
TheWorld.prefab='cave';Log.Configure('/unneeded/')
assert(Log.Path()==TESTHOME..'/Documents/Klei/DoNotStarveTogether/tractor_giant_planning_caves.log')
assert(Log.Append('caves planning record'))
''')
        self.assertEqual((directory / 'tractor_giant_planning_master.log').read_text(), 'master planning record\n')
        self.assertEqual((directory / 'tractor_giant_planning_caves.log').read_text(), 'caves planning record\n')
        self.assertFalse((directory / 'master_server_log.txt').exists())

    def test_file_io_error_falls_back_to_mod_log_directory(self):
        self.lua.globals().TESTROOT = str(self.root) + '/'
        self.lua.execute('''
os.getenv=function()return nil end;TheSim={GetRealTime=function()return 0 end}
Log.Configure(TESTROOT)
assert(Log.Append('fallback record'))
assert(Log.Path()==TESTROOT..'tractor_giant_planning_master.log')
''')
        self.assertEqual((self.root / 'tractor_giant_planning_master.log').read_text(), 'fallback record\n')
