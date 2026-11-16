#!/usr/bin/env python3
"""Loopback-only web UI for the Mod's live Lua source."""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
from collections import OrderedDict
import argparse,hashlib,json,threading,time,uuid,webbrowser
import urllib.request
import runner

HERE=Path(__file__).resolve().parent
BUILD_SIGNATURE=hashlib.sha256(b''.join((HERE/name).read_bytes() for name in ('runner.py','server.py','lua_bridge.lua'))).hexdigest()
SERVICE_FILE=HERE/'.runtime/service.json'
JOBS=OrderedDict();LOCK=threading.Lock();POOL=ThreadPoolExecutor(max_workers=1)


def presets():
 def case(label,w,h,tiles,seeds,season='autumn'):
  return {'name':label,'scenario':{'width':w,'height':h,'tiles':tiles,'start':tiles[0],'seeds':seeds,'season':season}}
 rect=lambda w,h:[[x,z] for z in range(h) for x in range(w)]
 return [
  case('番茄＋土豆 · 4＋4中心留空',1,1,rect(1,1),{'tomato':40,'potato':40}),
  case('T形 · 九种各4颗',3,2,[[0,0],[1,0],[2,0],[1,1]],{k:4 for k in ('carrot','corn','potato','tomato','eggplant','pumpkin','garlic','onion','pepper')}),
  case('U形 · 六种各7颗',3,2,[[0,0],[0,1],[1,1],[2,1],[2,0]],{k:7 for k in ('carrot','corn','potato','tomato','eggplant','pumpkin')}),
  case('环形 · 55颗混合库存',3,3,[[x,z] for z in range(3) for x in range(3) if [x,z]!=[1,1]],{'carrot':7,'corn':7,'potato':24,'tomato':17}),
  case('三种作物 · 逐格互补',3,4,rect(3,4),{'carrot':40,'corn':40,'potato':40}),
  case('冬季 · 验证应季筛选',2,2,rect(2,2),{'tomato':40,'potato':40,'carrot':40,'asparagus':40},'winter'),
  case('两个断开的区域',4,2,[[0,0],[0,1],[3,0],[3,1]],{'tomato':40,'potato':40}),
  case('春季T形 · 十二种各4颗',3,2,[[0,0],[1,0],[2,0],[1,1]],{c['id']:4 for c in runner.metadata()['crops'] if 'spring' in c['seasons']},'spring'),
  case('夏季L形 · 多种各4颗',2,2,[[0,0],[1,0],[0,1]],{c['id']:4 for c in runner.metadata()['crops'] if 'summer' in c['seasons']},'summer'),
  case('十字田 · 六种各7颗',3,3,[[1,0],[0,1],[1,1],[2,1],[1,2]],{k:7 for k in ('carrot','corn','potato','tomato','eggplant','pumpkin')}),
  case('单种库存 · 无互补配比',1,1,[[0,0]],{'potato':40}),
  case('64格大田 · 全部九宫格',8,8,rect(8,8),{'carrot':192,'corn':192,'potato':192}),
 ]


def worker(job):
 def phase(text):
  with LOCK:job['phase']=text
 def cancelled():return job['cancel'].is_set()
 with LOCK:job.update(status='running',started=time.monotonic(),phase='正在读取Mod源码')
 try:
  result=runner.run(job['input'],phase,cancelled)
  with LOCK:job.update(status='complete',result=result,phase='生成完成')
 except Exception as exc:
  with LOCK:
   if job['cancel'].is_set() or '__VERIFIER_CANCELLED__' in str(exc):job.update(status='cancelled',phase='已取消')
   else:job.update(status='error',error=str(exc),phase='生成失败')


class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(HERE/'static'),**kwargs)
 def log_message(self,*args):pass
 def end_headers(self):
  self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');super().end_headers()
 def output(self,status,data):
  raw=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def allowed(self):
  host=self.headers.get('Host','').split(':')[0]
  origin=self.headers.get('Origin')
  return host in ('127.0.0.1','localhost') and (not origin or urlparse(origin).netloc==self.headers.get('Host'))
 def do_GET(self):
  if not self.allowed():return self.output(403,{'error':'仅支持本机访问。'})
  path=urlparse(self.path).path
  try:
   if path in ('/','/index.html'):
    # Include live native crop data in the page, so controls do not wait for
    # optional preset requests or a second metadata HTTP round-trip.
    try:bootstrap=runner.metadata()
    except Exception:bootstrap=None  # Frontend can retry /api/meta with a visible message.
    payload=json.dumps(bootstrap,ensure_ascii=False).replace('<','\\u003c')
    html=(HERE/'static/index.html').read_text().replace('<script id="bootstrap-meta" type="application/json">null</script>', '<script id="bootstrap-meta" type="application/json">'+payload+'</script>')
    raw=html.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
   if path=='/api/meta':return self.output(200,{**runner.metadata(),'app_id':'tractor-native-seed-verifier','server_build':BUILD_SIGNATURE})
   if path=='/api/presets':return self.output(200,presets())
   if path.startswith('/api/jobs/'):
    ident=path.rsplit('/',1)[-1]
    with LOCK:
     job=JOBS.get(ident)
     if not job:return self.output(404,{'error':'计算任务不存在，请重新生成。'})
     data={k:v for k,v in job.items() if k not in ('cancel','input','started')}
     data['elapsed_ms']=round((time.monotonic()-job['started'])*1000) if job.get('started') else 0
    return self.output(200,data)
   if path.startswith('/api/'):return self.output(404,{'error':'接口不存在。'})
   return super().do_GET()
  except (BrokenPipeError,ConnectionResetError):pass
  except Exception as exc:return self.output(500,{'error':str(exc)})
 def do_POST(self):
  if not self.allowed():return self.output(403,{'error':'仅支持本机页面提交。'})
  if self.path!='/api/jobs':return self.output(404,{'error':'接口不存在。'})
  try:
   length=int(self.headers.get('Content-Length','0'))
   if not 0<length<=100000:raise ValueError('场景文件大小无效。')
   data=runner.normalize(json.loads(self.rfile.read(length)))
   with LOCK:
    for previous in JOBS.values():
     if previous['status'] in ('queued','running'):previous['cancel'].set()
    job={'id':uuid.uuid4().hex,'status':'queued','phase':'等待计算','input':data,'started':None,'cancel':threading.Event()}
    JOBS[job['id']]=job
    for key in list(JOBS)[:-20]:
     if JOBS[key]['status'] not in ('queued','running'):JOBS.pop(key,None)
   POOL.submit(worker,job)
   self.output(202,{'id':job['id']})
  except (ValueError,TypeError) as exc:self.output(400,{'error':str(exc)})
 def do_DELETE(self):
  if not self.allowed():return self.output(403,{'error':'仅支持本机操作。'})
  ident=urlparse(self.path).path.rsplit('/',1)[-1]
  with LOCK:
   job=JOBS.get(ident)
   if job:job['cancel'].set()
  self.output(200,{'cancelled':bool(job)})


def current_service(port):
 try:
  with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/meta',timeout=2) as response:metadata=json.load(response)
  return metadata.get('app_id')=='tractor-native-seed-verifier' and metadata.get('server_build')==BUILD_SIGNATURE and metadata.get('verifier_schema')==4
 except Exception:return False


def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=8877);parser.add_argument('--open',action='store_true');args=parser.parse_args()
 runner.manifest()
 if args.open:
  candidates=[args.port]
  try:
   previous=json.loads(SERVICE_FILE.read_text());port=previous.get('port')
   if type(port)==int and 0<port<65536:candidates.insert(0,port)
  except (OSError,ValueError):pass
  for port in candidates:
   if current_service(port):webbrowser.open(f'http://127.0.0.1:{port}');return
 try:server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
 except OSError:server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
 SERVICE_FILE.parent.mkdir(exist_ok=True)
 SERVICE_FILE.write_text(json.dumps({'port':server.server_port,'build':BUILD_SIGNATURE}))
 url=f'http://127.0.0.1:{server.server_port}';print('Mod巨大化验证器：'+url,flush=True)
 if args.open:threading.Timer(.3,lambda:webbrowser.open(url)).start()
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:
  with LOCK:
   for job in JOBS.values():job['cancel'].set()
  server.server_close();POOL.shutdown(wait=True)
  try:
   if json.loads(SERVICE_FILE.read_text()).get('port')==server.server_port:SERVICE_FILE.unlink()
  except (OSError,ValueError):pass

if __name__=='__main__':main()
