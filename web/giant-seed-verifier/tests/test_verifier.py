"""Native-runner parity, input, cancellation and HTTP tests. No duplicated planner."""
from pathlib import Path
import json,sys,tempfile,threading,unittest,urllib.request,urllib.error
from unittest.mock import patch
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parents[1]/'tools'))
import runner,server
import seed_strategy_audit as audit

class NativeParity(unittest.TestCase):
 def test_binary_grid_fills_both_autumn_5_by_5_cases(self):
  seasonal={c['id']:40 for c in runner.metadata()['crops'] if 'autumn' in c['seasons']}
  for seeds in ({'garlic':100,'onion':100,'pepper':100},seasonal):
   r=runner.run({'strategy':'GIANT','season':'autumn','width':5,'height':5,'seeds':seeds})
   self.assertEqual(r['count'],225);self.assertEqual(r['upper'],225)
   self.assertTrue(r['valid'] and r['optimal'])
   self.assertEqual(r['source']['grid_spacing'],1.3125)
   for p in r['slots']:
    self.assertIn(p['x']-p['cx'],(-1.3125,0,1.3125))
    self.assertIn(p['z']-p['cz'],(-1.3125,0,1.3125))

 def test_full_point_parity(self):
  # Every season × every irregular shape, with varying minimum/tail/full stocks.
  cases=audit.cases();chosen=[]
  for season in ('autumn','winter','spring','summer'):
   for i,shape in enumerate(audit.SHAPES):
    options=[c for c in cases if c['season']==season and c['shape']==shape]
    chosen.append(options[i%12])
  chosen+=audit.holdout_cases(12)
  for case in chosen:
   with self.subTest(case=case['id']):
    coords=[list(t) for t in case['tiles']]
    data={'season':case['season'],'width':max(x for x,z in coords)+1,'height':max(z for x,z in coords)+1,'tiles':coords,'start':coords[0],'seeds':case['stock']}
    actual=runner.run(data);expected=audit.run_case(case,native_float=True)
    points=[{k:p[k] for k in ('x','z','cx','cz','crop')} for p in actual['slots']]
    self.assertEqual(points,expected['points'])
    self.assertEqual(actual['count'],expected['count'])
    self.assertFalse(expected['errors'])
  self.assertEqual(len(chosen),76)

 def test_template_point_parity_and_strategy_roundtrip(self):
  cases=audit.cases()
  chosen=[]
  for season in ('autumn','winter','spring','summer'):
   for i,shape in enumerate(audit.SHAPES):
    options=[c for c in cases if c['season']==season and c['shape']==shape]
    chosen.append(options[i%12])
  for case in chosen:
   case={**case,'strategy':'GIANT_TEMPLATE'}
   coords=[list(t) for t in case['tiles']]
   data={'strategy':'GIANT_TEMPLATE','season':case['season'],'width':max(x for x,z in coords)+1,'height':max(z for x,z in coords)+1,'tiles':coords,'start':coords[0],'seeds':case['stock']}
   with self.subTest(case=case['id']):
    actual=runner.run(data);expected=audit.run_case(case,native_float=True)
    self.assertEqual([{k:p[k] for k in ('x','z','cx','cz','crop')} for p in actual['slots']],expected['points'])
    self.assertEqual(actual['strategy'],'GIANT_TEMPLATE')
    self.assertFalse(expected['errors'])
    self.assertEqual(runner.normalize(data)['strategy'],'GIANT_TEMPLATE')
  self.assertEqual(len(chosen),64)
  self.assertEqual(runner.normalize({})['strategy'],'GIANT')
  with self.assertRaises(ValueError):runner.normalize({'strategy':'invalid'})

 def test_inventory_boundary_and_disconnected_start(self):
  for count in (0,1,3,4,7,9,10):
   with self.subTest(count=count):
    r=runner.run({'width':1,'height':1,'seeds':{'potato':count,'tomato':40,'randomseed':100}})
    self.assertEqual(r['count'],8 if count>=4 else 0)
    self.assertEqual(r['remaining']['randomseed'],100)
  data={'width':4,'height':1,'tiles':[[0,0],[3,0]],'start':[3,0],'seeds':{'potato':20,'tomato':20}}
  r=runner.run(data);self.assertEqual(r['count'],8);self.assertTrue(all(p['cx']==12 for p in r['slots']))

 def test_large_and_cancel(self):
  r=runner.run({'width':9,'height':8,'seeds':{'carrot':900}})
  self.assertEqual(r['reason'],'FARM_TOO_LARGE')
  with self.assertRaisesRegex(Exception,'__VERIFIER_CANCELLED__'):
   runner.run({'width':4,'height':4,'seeds':{k:40 for k in runner.CROP_ORDER}},cancelled=lambda:True)

 def test_source_reread_and_manifest(self):
  import shutil
  original=runner.manifest()
  self.assertEqual(original['runtime'],'Lua 5.1');self.assertEqual(len(original['files']),len(runner.MODULES));self.assertIn('aom_seed_regions.lua',runner.MODULES)
  with tempfile.TemporaryDirectory() as directory:
   mod=Path(directory)/'Tractor';shutil.copytree(runner.MOD,mod,ignore=shutil.ignore_patterns('anim','images','sound','minimap','bigportraits'))
   file=mod/'scripts/aom_seed_layout.lua';file.write_text(file.read_text()+'\n-- live-source-test\n')
   with patch.object(runner,'MOD',mod):
    changed=runner.run({'seeds':{'potato':40}})['source']
   self.assertNotEqual(changed['fingerprint'],original['fingerprint'])
   self.assertFalse(changed['installed_match'])
   with patch.object(runner,'MOD',mod):
    file.write_text("error('live-source-loaded')\n"+file.read_text())
    with self.assertRaisesRegex(Exception,'live-source-loaded'):runner.run({'seeds':{'potato':40}})
  self.assertEqual(runner.manifest()['fingerprint'],original['fingerprint'])

 def test_bad_inputs(self):
  for data in ({'width':True},{'season':'bad'},{'tiles':[]},{'tiles':[[0,0],[0,0]]},{'seeds':{'potato':-1}},{'seeds':{'potato':4.5}},{'start':[9,9]},{'seeds':{'other':4}}):
   with self.subTest(data=data),self.assertRaises(ValueError):runner.normalize(data)

class HTTPTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
  cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start();cls.base=f'http://127.0.0.1:{cls.http.server_port}'
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.thread.join()
 def request(self,path,body=None,headers=None,method=None):
  req=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers or {},method=method)
  return urllib.request.urlopen(req,timeout=5)
 def test_static_and_meta(self):
  with self.request('/') as r:self.assertIn('巨大化播种验证',r.read().decode())
  with self.request('/api/meta') as r:self.assertEqual(json.load(r)['runtime'],'Lua 5.1')
 def test_page_bootstraps_live_crop_data(self):
  import re
  for path in ('/','/index.html'):
   with self.subTest(path=path),self.request(path) as response:
    html=response.read().decode()
    data=json.loads(re.search(r'<script id="bootstrap-meta" type="application/json">(.*?)</script>',html,re.S).group(1))
    self.assertEqual(data['verifier_schema'],4)
    self.assertEqual(len(data['crops']),14)
    self.assertEqual(data['crops'],runner.metadata()['crops'])
 def test_page_keeps_retry_ui_when_native_metadata_unavailable(self):
  with patch.object(runner,'metadata',side_effect=RuntimeError('temporarily unavailable')):
   with self.request('/') as response:html=response.read().decode()
  self.assertIn('id="bootstrap-meta" type="application/json">null</script>',html)
  self.assertIn('id="retry-connection"',html)
 def test_embedded_metadata_cannot_terminate_script(self):
  import re
  data=runner.metadata();data['crops'][0]['name']='</script><script>bad()</script>'
  with patch.object(runner,'metadata',return_value=data):
   with self.request('/') as response:html=response.read().decode()
  payload=re.search(r'<script id="bootstrap-meta" type="application/json">(.*?)</script>',html,re.S).group(1)
  self.assertNotIn('<',payload)
  self.assertEqual(json.loads(payload)['crops'][0]['name'],data['crops'][0]['name'])
 def test_stale_service_is_not_reused(self):
  self.assertTrue(server.current_service(self.http.server_port))
  class OldHandler(server.Handler):
   def do_GET(self):self.output(200,{'runtime':'Lua 5.1'})
  old=server.ThreadingHTTPServer(('127.0.0.1',0),OldHandler)
  thread=threading.Thread(target=old.serve_forever,daemon=True);thread.start()
  try:self.assertFalse(server.current_service(old.server_port))
  finally:old.shutdown();old.server_close();thread.join()
 def test_job_roundtrip(self):
  with self.request('/api/jobs',{'seeds':{'potato':40,'tomato':40}}) as r:ident=json.load(r)['id']
  import time
  deadline=time.monotonic()+5
  while time.monotonic()<deadline:
   with self.request('/api/jobs/'+ident) as r:job=json.load(r)
   if job['status']=='complete':break
   time.sleep(.02)
  self.assertEqual(job['status'],'complete');self.assertEqual(job['result']['used'],{'potato':16,'tomato':16})
 def test_invalid_and_origin(self):
  for data,headers,code in (({'tiles':[]},{},400),({}, {'Origin':'https://other.example'},403)):
   with self.subTest(code=code),self.assertRaises(urllib.error.HTTPError) as caught:self.request('/api/jobs',data,headers)
   self.assertEqual(caught.exception.code,code)
 def test_cancel(self):
  with self.request('/api/jobs',{'width':8,'height':8,'seeds':{k:40 for k in runner.CROP_ORDER}}) as r:ident=json.load(r)['id']
  with self.request('/api/jobs/'+ident,method='DELETE') as r:self.assertTrue(json.load(r)['cancelled'])

if __name__=='__main__':unittest.main(verbosity=2)
