"""最大数量证明与排列阶段隔离；不读取开发机下载目录或离线求解器见证。"""
import itertools,random,sys,unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import seed_strategy_audit as audit

class MaximumSeedTests(unittest.TestCase):
 def test_balanced_components_reach_safe_upper_on_irregular_fields(self):
  available={c['id']:c for c in audit.cases()}
  for name,target in [('spring/bridge-7/all-six',60),('autumn/ring-8/all-six',50),('summer/ring-8/six-seven',35)]:
   case=available[name]
   with self.subTest(case=name):
    w,b=self.build(case['tiles'],case['stock'],case['season'],inspect=True)
    points=[{k:p[k] for k in ('x','z','cx','cz','crop')} for p in b.slots.values()]
    errors,metrics=audit.independent_check(case,points)
    self.assertFalse(errors);self.assertEqual(metrics['count'],target)
    self.assertEqual(b.upper,audit.upper_bound(case['stock'],case['season'],len(case['tiles'])*9)[0])
    self.assertEqual(w.lua.globals().arrangements,1)

 def test_fixed_quantity_allocations_cover_exhaustive_stock_profiles(self):
  rng=random.Random(918731);w=audit.world();L=w.lua;B=L.eval("require('aom_seed_balance')")
  scenes=[{'tomato':8,'pepper':5},{'tomato':7}]
  for season in ('autumn','winter','spring','summer'):
   choices=[k for k,v in audit.RULES.items() if season in v['seasons']]
   for _ in range(4):scenes.append({k:rng.choice((3,4,5,6,8)) for k in rng.sample(choices,min(5,len(choices)))})
  for stock in scenes:
   crops=sorted(stock);vectors=[audit.RULES[k]['net'] for k in crops]
   classes={}
   for i,k in enumerate(crops):classes.setdefault((tuple(vectors[i]),audit.RULES[k]['minimum'],audit.RULES[k]['radius']),[]).append(i)
   def signature(counts):return tuple(sorted((key,tuple(sorted(counts[i] for i in indices))) for key,indices in classes.items()))
   expected={}
   for counts in itertools.product(*([0]+list(range(audit.RULES[k]['minimum'],stock[k]+1)) for k in crops)):
    if any(sum(n*vectors[i][j] for i,n in enumerate(counts)) for j in (0,1)):continue
    expected.setdefault(sum(counts),set()).add(signature(counts))
   lc=L.table_from(crops);ls=L.table_from(stock);lv=L.table_from([L.table_from(v) for v in vectors])
   for target in range(sum(stock.values())+1):
    profiles,limited,_,_=B.TargetAllocations(lc,ls,lv,target,L.globals().DEFS,None,1000000)
    actual=[]
    for profile in profiles.values():
     counts=[profile[i+1] for i in range(len(crops))]
     self.assertTrue(all(n==0 or audit.RULES[k]['minimum']<=n<=stock[k] for k,n in zip(crops,counts)))
     actual.append(signature(counts))
    self.assertFalse(limited);self.assertEqual(len(actual),len(set(actual)))
    self.assertEqual(set(actual),expected.get(target,set()),(stock,target))

 def build(self,tiles,stock,season='autumn',inspect=False):
  w=audit.world();L=w.lua;g=L.globals();g.inst=w.make(stock,season)
  L.execute("inst.components.container.numslots=15;D=require('aom_dynamic_farm');P=require('aom_seed_packing');A=require('aom_seed_layout');TheWorld.components.farming_manager.GetTileNutrients=function()error('soil must not be read')end")
  if inspect:
   L.execute("arrangements=0;local old=A.Regularize;A.Regularize=function(...)assert(P.last_report and P.last_report.optimal==true);arrangements=arrangements+1;return old(...)end")
  for x,z in tiles:
   for dx in (-1,0,1):
    for dz in (-1,0,1):g.SpawnPrefab('farm_soil').Transform.SetPosition(None,x*4+dx*4/3,0,z*4+dz*4/3)
  r=g.D.Build(g.inst,tiles[0][0]*4,tiles[0][1]*4)
  b=r[0] if isinstance(r,tuple) else r
  if b:
   self.assertTrue(b.optimal);self.assertEqual(b.upper,b.total);self.assertTrue(g.D.Validate(b)[0])
  return w,b

 def test_new_inventory_and_all_rotations_reach_45(self):
  original=((0,0),(1,0),(1,1),(2,0),(2,1))
  for orientation in range(8):
   coords=[]
   for x,z in original:
    if orientation>=4:x=-x
    for _ in range(orientation%4):x,z=-z,x
    coords.append((x,z))
   for egg in (0,4):
    with self.subTest(orientation=orientation,egg=egg):
     w,b=self.build(coords,{'potato':16,'tomato':16,'eggplant':egg,'garlic':8,'onion':8,'pepper':8},inspect=True)
     self.assertEqual(b.total,45);self.assertEqual(w.lua.globals().arrangements,1)
     self.assertGreaterEqual(b.construction.quantity_seconds,0);self.assertGreaterEqual(b.construction.arrangement_seconds,0)

 def test_single_tile_matches_exhaustive_quantity_oracle(self):
  rng=random.Random(53117)
  for season in ('autumn','winter','spring','summer'):
   available=[k for k,v in audit.RULES.items() if season in v['seasons']]
   for _ in range(12):
    kinds=rng.sample(available,min(4,len(available)));stock={k:rng.choice((0,3,4,5,6,8,13)) for k in kinds}
    best=0
    for ns in itertools.product(*(range(min(9,stock[k])+1) for k in kinds)):
     n=sum(ns)
     if n>9 or any(0<x<audit.RULES[k]['minimum'] for k,x in zip(kinds,ns)):continue
     if any(sum(x*audit.RULES[k]['net'][j] for k,x in zip(kinds,ns)) for j in range(3)):continue
     best=max(best,n)
    w,b=self.build(((0,0),),stock,season)
    self.assertEqual(b.total if b else 0,best,(season,stock))
    self.assertTrue(w.lua.globals().P.last_report.optimal)

 def test_unattainable_relaxed_upper_is_proved_before_arranging(self):
  # 五格狭长田的全局净变化可容纳45；逐株同族几何只容纳43。
  _,b=self.build(tuple((x,0) for x in range(5)),{'carrot':7,'corn':7,'potato':24,'tomato':17},inspect=True)
  self.assertEqual(b.total,43);self.assertGreater(b.relaxed_upper,b.total)

 def test_cancellation_never_returns_or_arranges_a_partial_maximum(self):
  w=audit.world();L=w.lua;g=L.globals();g.inst=w.make({'potato':16,'tomato':16,'eggplant':4,'garlic':8,'onion':8,'pepper':8},'autumn')
  for x,z in ((0,0),(1,0),(1,1),(2,0),(2,1)):
   for dx in (-1,0,1):
    for dz in (-1,0,1):g.SpawnPrefab('farm_soil').Transform.SetPosition(None,x*4+dx*4/3,0,z*4+dz*4/3)
  L.execute("D=require('aom_dynamic_farm');A=require('aom_seed_layout');arranged=false;local old=A.Regularize;A.Regularize=function(...)arranged=true;return old(...)end;D._yield=function()error('user cancelled')end")
  with self.assertRaisesRegex(Exception,'user cancelled'):g.D.Build(g.inst,0,0)
  self.assertFalse(g.arranged)

 def test_raw_spacing_conflicts_are_part_of_search_and_arrangement_validity(self):
  w=audit.world();L=w.lua
  L.execute("A=require('aom_seed_layout');local defs=require('prefabs/farm_plant_defs').PLANT_DEFS;G=A.Geometry({{x=0,z=0}},{{x=0,z=0},{x=.5,z=0},{x=0,z=1.5},{x=1.5,z=1.5}},defs);assert(not A.Valid({'potato','potato','potato','potato'},G))")

 def test_arrangement_timeout_preserves_completed_quantity_timing_and_proof(self):
  w=audit.world()
  def clock():
   return 100 if w.lua.eval("package.loaded.aom_seed_packing and package.loaded.aom_seed_packing.phase")=='arrangement' else 0
  case={'id':'phase-interruption','tiles':[(0,0),(1,0),(1,1),(2,0),(2,1)],'season':'autumn','stock':{'potato':16,'tomato':16,'eggplant':4,'garlic':8,'onion':8,'pepper':8}}
  with patch.object(audit,'world',return_value=w),patch.object(audit.time,'perf_counter',side_effect=clock):
   row=audit.run_case(case,case_seconds=5)
  self.assertTrue(row['incomplete']);self.assertEqual(row['incomplete_phase'],'arrangement')
  self.assertTrue(row['maximum_proven']);self.assertEqual(row['maximum_quantity_count'],45)
  self.assertTrue(row['timings']['quantity_complete']);self.assertFalse(row['timings']['arrangement_complete'])
  self.assertGreater(row['timings']['quantity_seconds'],0);self.assertIsNone(row['count'])
