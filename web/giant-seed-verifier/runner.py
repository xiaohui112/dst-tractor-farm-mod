"""Execute unmodified Mod modules in Lua 5.1; no planner is reimplemented here."""
from pathlib import Path
from collections import Counter
from zipfile import ZipFile
from functools import lru_cache
import hashlib,json,math,os,re,sys,time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'.runtime'))
try:from lupa.lua51 import LuaRuntime
except ImportError:
 sys.path.insert(0,'/tmp/pylua')
 from lupa.lua51 import LuaRuntime

ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from farm_native_math import f32, distance_squared, radius_squared
MOD=Path(os.environ.get('TRACTOR_MOD_SOURCE',str(ROOT/'mod/Tractor'))).resolve()
GAME=Path(os.environ.get('DST_GAME_SCRIPTS',str(Path.home()/"Library/Application Support/Steam/steamapps/common/Don't Starve Together/dontstarve_steam.app/Contents/data/databundles/scripts.zip")))
MODULES=('aom_farm_grid.lua','aom_farm_neighbors.lua','aom_seed_catalog.lua','aom_seed_template_data.lua','aom_seed_initial.lua','aom_seed_templates.lua','aom_template_preview.lua','aom_seed_regions.lua','aom_planner_build.lua','aom_dynamic_farm.lua','aom_seed_layout.lua','aom_seed_packing.lua','aom_seed_exact.lua','aom_seed_heuristic.lua','aom_seed_feasible.lua','aom_seed_balance.lua','aom_seed_strategy.lua','aom_farm_registry.lua','aom_crop_state.lua','components/aom_attachment_store.lua')
NAMES={'carrot':'胡萝卜','corn':'玉米','potato':'土豆','tomato':'番茄','asparagus':'芦笋','eggplant':'茄子','pumpkin':'南瓜','watermelon':'西瓜','dragonfruit':'火龙果','durian':'榴莲','garlic':'大蒜','onion':'洋葱','pepper':'辣椒','pomegranate':'石榴'}
CROP_ORDER=tuple(NAMES)
REASONS={'NO_BALANCED_COMBO':'现有应季库存与农田容量无法组成逐地皮互补配比，请调整种子或农田范围。','MISSING_SEEDS':'没有能组成同族的应季种子，请增加种子或检查季节。','FARM_TOO_LARGE':'从起点连通的农田超过最优策略的64块上限；可缩小范围或切换模版策略。','NEED_PLOW':'起点需要完整的九宫格空坑。','FOREIGN_CROP':'起点存在不符合空田要求的作物或障碍。','NO_FAMILY':'本次未找到能通过同族与坑距检查的方案。'}

@lru_cache(maxsize=4)
def _native_data(path,mtime):
 with ZipFile(path) as z:
  source=z.read('scripts/prefabs/farm_plant_defs.lua').decode();tuning=z.read('scripts/tuning.lua').decode()
 constants={k:float(re.search(r'\b'+k+r'\s*=\s*([\d.]+)',tuning).group(1)) for k in ('FARM_PLANT_SAME_FAMILY_MIN','FARM_PLANT_SAME_FAMILY_RADIUS','FARM_TILL_SPACING','FARM_PANT_OVERCROWDING_MAX_PLANTS','FARM_PLANT_CONSUME_NUTRIENT_LOW','FARM_PLANT_CONSUME_NUTRIENT_MED','FARM_PLANT_CONSUME_NUTRIENT_HIGH')}
 return source,constants

def native_data():return _native_data(str(GAME),GAME.stat().st_mtime_ns)

@lru_cache(maxsize=4)
def _grid_spacing(path,mtime):
 return LuaRuntime().execute(Path(path).read_text()).SPACING

def grid_spacing():
 p=MOD/'scripts/aom_farm_grid.lua'
 return _grid_spacing(str(p),p.stat().st_mtime_ns)

def manifest():
 files=[]
 for name in MODULES:
  p=MOD/'scripts'/name;raw=p.read_bytes()
  files.append({'path':'scripts/'+name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
 version=re.search(r'^version\s*=\s*"([^"]+)"',(MOD/'modinfo.lua').read_text(),re.M).group(1)
 source,constants=native_data()
 installed=Path.home()/"Library/Application Support/Steam/steamapps/common/Don't Starve Together/dontstarve_steam.app/Contents/mods/Tractor"
 matches=installed.exists() and all((installed/row['path']).exists() and hashlib.sha256((installed/row['path']).read_bytes()).hexdigest()==row['sha256'] for row in files)
 return {'grid_spacing':grid_spacing(),'version':version,'runtime':'Lua 5.1','files':files,'fingerprint':hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),'installed_match':matches,'native_sha256':hashlib.sha256(source.encode()).hexdigest(),'constants':constants}

def to_lua(L,value):
 if isinstance(value,dict):return L.table_from({k:to_lua(L,v) for k,v in value.items()})
 if isinstance(value,list):return L.table_from([to_lua(L,v) for v in value])
 return value

def normalize(data):
 if not isinstance(data,dict):raise ValueError('请输入有效的测试场景。')
 strategy=data.get('strategy','GIANT')
 if strategy not in ('GIANT_TEMPLATE','GIANT'):raise ValueError('播种策略无效。')
 season=data.get('season','autumn')
 if season not in ('autumn','winter','spring','summer'):raise ValueError('季节无效。')
 width,height=data.get('width',2),data.get('height',2)
 if type(width)!=int or type(height)!=int or not 1<=width<=9007199254740991 or not 1<=height<=9007199254740991:raise ValueError('农田宽高须为正整数。')
 tiles=data.get('tiles',[[x,z] for z in range(height) for x in range(width)])
 if not isinstance(tiles,list) or not tiles:raise ValueError('请至少选一块农田。')
 seen=set();checked=[]
 for p in tiles:
  if not isinstance(p,list) or len(p)!=2 or any(type(v)!=int for v in p) or not(0<=p[0]<width and 0<=p[1]<height):raise ValueError('地皮坐标超出画布范围。')
  t=tuple(p)
  if t in seen:raise ValueError('存在重复地皮。')
  seen.add(t);checked.append(p)
 start=data.get('start',checked[0])
 if not isinstance(start,list) or len(start)!=2 or any(type(v)!=int for v in start) or tuple(start) not in seen:raise ValueError('请在已选择的农田中设置起点。')
 supplied=data.get('seeds',{})
 if not isinstance(supplied,dict) or any(k not in (*CROP_ORDER,'randomseed') for k in supplied):raise ValueError('种子种类无效。')
 seeds={}
 for k in (*CROP_ORDER,'randomseed'):
  n=supplied.get(k,0)
  if type(n)!=int or not 0<=n<=9999:raise ValueError('种子数量须为0至9999的整数。')
  seeds[k]=n
 template_id=data.get('template_id') or None
 if template_id is not None and (strategy!='GIANT_TEMPLATE' or not isinstance(template_id,str) or template_id not in {s['id'] for s in metadata()['templates']}):raise ValueError('锁定模版编号无效，或当前策略不是模版。')
 return {'template_id':template_id,'strategy':strategy,'season':season,'width':width,'height':height,'tiles':checked,'start':start,'seeds':seeds}

def _execute(data,phase=lambda _:None,cancelled=lambda:False):
 source,constants=native_data()
 L=LuaRuntime(unpack_returned_tuples=True,register_eval=False,register_builtins=False)
 L.globals().MOD_SCRIPTS=str(MOD/'scripts');L.globals().NATIVE_SOURCE=source
 L.globals().NATIVE_CONSTANTS=to_lua(L,constants)
 L.globals().INPUT=to_lua(L,{**data,'crop_order':list(CROP_ORDER)+['randomseed']})
 L.globals().PY_PHASE=phase;L.globals().PY_CANCELLED=cancelled
 L.globals().PY_F32=f32;L.globals().PY_DISTANCE_SQ=distance_squared;L.globals().PY_RADIUS_SQ=radius_squared
 return L,L.execute((HERE/'lua_bridge.lua').read_text())

def metadata():
 empty={'season':'autumn','width':1,'height':1,'tiles':[[0,0]],'start':[0,0],'seeds':{}}
 _,r=_execute(empty);crops=[]
 for k in CROP_ORDER:
  d=r.defs[k]
  crops.append({'id':k,'name':NAMES[k],'seasons':[s for s in ('autumn','winter','spring','summer') if d.good_seasons[s]],'family_min':d.family_min_count,'family_radius':d.family_check_dist,'nutrient_net':[sum(d.nutrient_consumption.values())/sum(bool(d.nutrient_restoration[i]) for i in (1,2,3))*(1 if d.nutrient_restoration[j] else 0)-(d.nutrient_consumption[j] or 0) for j in (1,2,3)]})
 templates=[{'id':s.id,'total':s.total,'source':s.source,'size':list(s.size.values())} for s in r.catalog.templates.values()]
 return {**manifest(),'templates':templates,'catalog_version':r.catalog.version,'verifier_schema':4,'strategies':[{'id':'GIANT_TEMPLATE','name':'巨大化·模版'},{'id':'GIANT','name':'巨大化·最优'}],'crops':crops,'max_tiles':64,'strategy_limits':{'GIANT':64,'GIANT_TEMPLATE':None},'policy':['逐地皮养分互补、应季、同族和坑距','合法配比内播种数量优先','同族连片及距离','行列与整体排列']}

def run(data,phase=lambda _:None,cancelled=lambda:False):
 data=normalize(data);before=manifest();started=time.perf_counter()
 L,result=_execute(data,phase,cancelled)
 after=manifest()
 if any(before[k]!=after[k] for k in ('fingerprint','native_sha256','constants')):raise RuntimeError('Mod代码在计算中发生变更，请重新生成。')
 if cancelled():raise RuntimeError('__VERIFIER_CANCELLED__')
 b=result.plan
 construction=result.construction
 response={'strategy':data['strategy'],'input':data,'source':before,'elapsed_ms':round((time.perf_counter()-started)*1000),'reason':result.reason,'valid':bool(result.valid),'ticks':result.ticks,'timings':{'quantity_ms':round(((construction.quantity_seconds or 0) if construction else 0)*1000,3),'arrangement_ms':round(((construction.arrangement_seconds or 0) if construction else 0)*1000,3),'basis':'process_cpu','template_prepare_ms':round(((construction.template_prepare_seconds or 0)if construction else 0)*1000,3),'template_select_ms':round(((construction.template_select_seconds or 0)if construction else 0)*1000,3)}}
 if b is None:
  if construction and (construction.total or 0)>0:raise RuntimeError('最大数量候选没有通过Mod最终校验。')
  response.update(count=0,upper=0,optimal=False,slots=[],tiles=[],used={},remaining=data['seeds'],message=REASONS.get(result.reason,'本次没有生成播种方案。'))
  return response
 slots=[{key:p[key] for key in ('x','z','cx','cz','crop','index')} for p in b.slots.values()]
 tiles=[{'x':t.x,'z':t.z} for t in b.tiles.values()]
 used=Counter(p['crop'] for p in slots if p['crop'])
 checks=[];family_passed=0;spacing_passed=True
 _,constants=native_data()
 # Independent checks use spatial buckets so browser verification does not add
 # a quadratic all-pairs pass to a large native plan.
 from math import floor
 radius=max([float(result.defs[k].family_check_dist) for k in used]+[float(constants['FARM_TILL_SPACING'])])
 buckets={};per_tile={}
 for i,p in enumerate(slots):
  if p['crop']:
   buckets.setdefault((floor(p['x']/radius),floor(p['z']/radius)),[]).append((i,p))
   per_tile.setdefault((p['cx'],p['cz']),[]).append(p)
 for i,p in enumerate(slots):
  if not p['crop']:continue
  d=result.defs[p['crop']];bx,bz=floor(p['x']/radius),floor(p['z']/radius)
  nearby=[(j,q) for dx in (-2,-1,0,1,2) for dz in (-2,-1,0,1,2) for j,q in buckets.get((bx+dx,bz+dz),[])]
  family=sum(q['crop']==p['crop'] and distance_squared(p['x'],0,p['z'],q['x'],0,q['z'])<=radius_squared(d.family_check_dist) for _,q in nearby)
  p['family']=family;p['family_min']=d.family_min_count;p['family_radius']=d.family_check_dist
  family_passed+=family>=d.family_min_count
  for j,q in nearby:
   if j<i and distance_squared(p['x'],0,p['z'],q['x'],0,q['z'])<=radius_squared(constants['FARM_TILL_SPACING']):spacing_passed=False
 nutrient_tiles=[]
 for tile in tiles:
  net=[0,0,0]
  for p in per_tile.get((tile['x'],tile['z']),[]):
   d=result.defs[p['crop']];consume=[d.nutrient_consumption[i] or 0 for i in (1,2,3)]
   restore=[i for i in (1,2,3) if d.nutrient_restoration[i]]
   for j in (1,2,3):net[j-1]+=(sum(consume)/len(restore) if j in restore else 0)-consume[j-1]
  nutrient_tiles.append({**tile,'net':net,'balanced':all(abs(n)<1e-8 for n in net)})
 nutrients=all(t['balanced'] for t in nutrient_tiles)
 quantities=all(used[k]<=data['seeds'].get(k,0) for k in used)
 seasonal=all(result.defs[k].good_seasons[data['season']] for k in used)
 arrange=b.arrangement
 response.update(template_modules=[{'id':m.id,'tiles':list(m.tiles.values()),'symmetry':m.symmetry,'origin':dict(m.origin.items()),'crops':dict(m.crops.items())}for m in (construction.modules.values()if construction and construction.modules else [])],count=b.total,upper=b.upper,optimal=bool(b.optimal),slots=slots,tiles=tiles,used=dict(used),remaining={k:n-used.get(k,0) for k,n in data['seeds'].items()},checks={'family_passed':family_passed,'family_total':sum(used.values()),'spacing':spacing_passed,'stock':quantities,'season':seasonal,'mod_validation':bool(result.valid),'complete_templates':data['strategy']!='GIANT_TEMPLATE' or bool(result.valid),'nutrient_balance':nutrients,'nutrient_tiles':nutrient_tiles},layout={'score':arrange.after.score,'components':arrange.after.components,'fragmentation':arrange.after.fragmentation,'limited':bool(arrange.limited),'family_distance':arrange.after.family,'tidy':arrange.after.tidy,'search_limited':bool(b.construction.limited)},used_tiles=len({(p['cx'],p['cz']) for p in slots if p['crop']}))
 if not(result.valid and family_passed==b.total and spacing_passed and quantities and seasonal and nutrients):raise RuntimeError('布局未通过校验，请保留场景并检查Mod。')
 return response
