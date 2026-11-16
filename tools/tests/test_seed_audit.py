"""Previously missed inventories/geometries, with independent quantity/family checks."""
import json
from pathlib import Path
from collections import Counter
from math import factorial
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import seed_strategy_audit as audit
import test_giant_farming as giant

FIXTURES=Path(__file__).parent/'fixtures/seed-audit-counterexamples.json'

class SeedAuditTests(unittest.TestCase):
 def make(self,tiles,stock,season='autumn'):
  w=giant.World();L=w.lua;L.globals().inst=w.make(stock,season)
  L.execute("inst.components.container.numslots=15;D=require('aom_dynamic_farm');A=require('aom_seed_layout');TheWorld.components.farming_manager.GetTileNutrients=function()error('nutrients must not be read')end")
  for x,z in tiles:
   for dx in (-1,0,1):
    for dz in (-1,0,1):L.globals().SpawnPrefab('farm_soil').Transform.SetPosition(None,x*4+dx*4/3,0,z*4+dz*4/3)
  x,z=tiles[0];b=L.globals().D.Build(L.globals().inst,x*4,z*4)
  return w,b[0] if isinstance(b,tuple) else b
 def validate(self,case,b):
  upper=audit.upper_bound(case['stock'],case['season'],len(case['tiles'])*9)[0]
  if b is None:
   self.assertEqual(upper,0,case['id']);return
  points=[{k:p[k] for k in ('x','z','cx','cz','crop')} for p in b.slots.values()]
  errors,metrics=audit.independent_check(case,points)
  self.assertFalse(errors,(case['id'],errors))
  self.assertEqual(metrics['count'],b.total);self.assertLessEqual(b.total,upper)
  # New priorities are lexicographic; weighted aesthetic score may rise as compactness improves.
  before,after=b.arrangement.before,b.arrangement.after
  self.assertLessEqual((after.fragmentation,round(after.family,6),round(after.tidy,6)),(before.fragmentation,round(before.family,6),round(before.tidy,6)))
 def test_historical_inventory_and_geometry_cases_obey_balanced_policy(self):
  for case in json.loads(FIXTURES.read_text())['cases']:
   marker=audit.ROOT/'outputs/selfcheck-seed-case.txt';marker.parent.mkdir(parents=True,exist_ok=True);marker.write_text(case['id']+'\n')
   with self.subTest(case=case['id']):
    _,b=self.make(case['tiles'],case['stock'],case['season']);self.validate(case,b)
 def test_rotated_and_mirrored_tight_family_cover(self):
  original=[(0,0),(1,0),(2,0),(1,1)]
  stock={k:4 for k in ('carrot','corn','potato','tomato','eggplant','pumpkin','garlic','onion','pepper')}
  for r in range(8):
   coords=[]
   for x,z in original:
    if r>=4:x=-x
    for _ in range(r%4):x,z=-z,x
    coords.append((x,z))
   case={'id':'T-cover-'+str(r),'tiles':coords,'stock':stock,'season':'autumn'}
   _,b=self.make(coords,stock);self.validate(case,b);self.assertEqual(b.total,32)
 def test_quality_scenes_preserve_lexicographic_priorities(self):
  path=Path(__file__).parent/'fixtures/seed-layout-quality-baseline.json'
  for case in json.loads(path.read_text())['cases']:
   with self.subTest(case=case['id']):
    _,b=self.make(case['tiles'],case['stock'],case['season']);self.validate(case,b)
 def test_quantity_regressions_match_independent_balanced_upper(self):
  names=('autumn/horizontal-5/all-season','autumn/T-4/all-season','spring/T-4/all-season','autumn/U-5/six-seven','autumn/horizontal-2/three-tails','summer/L-3/all-season')
  allcases={c['id']:c for c in audit.cases()}
  for name in names:
   case=allcases[name]
   with self.subTest(case=name):
    _,b=self.make(case['tiles'],case['stock'],case['season']);self.validate(case,b)
    self.assertEqual(b.total,audit.upper_bound(case['stock'],case['season'],len(case['tiles'])*9)[0])
  # An independently validated 44-plant witness exists; a fallback of 18 is a regression.
  case=allcases['summer/horizontal-5/all-six']
  _,b=self.make(case['tiles'],case['stock'],case['season']);self.validate(case,b);self.assertGreaterEqual(b.total,44)
 def test_small_multisets_include_every_pit_arrangement(self):
  for groups in [(4,5),(4,4,1),(3,3,3),(9,)]:
   w=giant.World();L=w.lua
   values=[]
   colors=('carrot','corn',False if groups==(4,4,1) else 'potato')
   for k,n in zip(colors,groups):values.extend([k]*n)
   L.globals().cells=L.table_from(values);bank=L.eval("require('aom_seed_layout').Candidates(cells)")
   expected=factorial(9)
   for n in groups:expected//=factorial(n)
   self.assertEqual(len(bank),expected,groups)
 def test_regularizer_preserves_tile_stock_and_family_under_repeated_runs(self):
  # The quantity tests above validate larger fields; use a direct Lua pass here to
  # check the rearranger's stronger per-tile multiset invariant.
  w=giant.World();L=w.lua
  L.execute("A=require('aom_seed_layout');tiles={{x=0,z=0},{x=4,z=0}};slots={};board={'potato','tomato','potato',false,'potato','tomato','tomato','potato','tomato','tomato','potato','tomato','potato','tomato',false,'potato','tomato','potato'};for t=1,2 do for s=0,8 do slots[#slots+1]={x=(t-1)*4+(s%3-1)*4/3,z=(math.floor(s/3)-1)*4/3} end end;for _,p in ipairs(slots)do SpawnPrefab('farm_soil').Transform:SetPosition(p.x,0,p.z)end;geometry=A.Geometry(tiles,slots,DEFS);assert(A.Valid(board,geometry))")
  before=[Counter(L.globals().board[i] for i in range(1+t*9,10+t*9)) for t in range(2)]
  L.execute("board,report=A.Regularize(board,geometry);assert(A.Valid(board,geometry));board,second=A.Regularize(board,geometry);assert(A.Valid(board,geometry));assert(not A.Better(report.after,second.after))")
  after=[Counter(L.globals().board[i] for i in range(1+t*9,10+t*9)) for t in range(2)]
  self.assertEqual(before,after)
