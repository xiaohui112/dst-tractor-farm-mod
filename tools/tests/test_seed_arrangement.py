"""Pattern-first arrangement, independent mismatch oracle and hard constraints."""
from collections import Counter
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'web/giant-seed-verifier'))
sys.path.insert(0, str(ROOT / 'tools'))
import runner
import benchmark_seed_arrangement as benchmark


FIELDS = ('pattern_mismatch', 'line_cost', 'hole_cost', 'order_cost')


class PatternArrangementTests(unittest.TestCase):
 def test_center_hole_is_a_soft_preference_after_quantity_is_fixed(self):
  from test_giant_farming import World
  L = World().lua
  L.execute("""
local A=require('aom_seed_layout');local P=require('aom_seed_arrangement')
local tiles={{x=0,z=0}};local slots={}
for s=1,9 do
 local p={x=((s-1)%3-1)*1.3125,z=(math.floor((s-1)/3)-1)*1.3125}
 slots[s]=p;SpawnPrefab('farm_soil').Transform:SetPosition(p.x,0,p.z)
end
local g=A.Geometry(tiles,slots,DEFS);g.balanced=true
local corner={'potato','potato','potato','potato','tomato','tomato',false,'tomato','tomato'}
local center={'potato','potato','potato','potato',false,'tomato','tomato','tomato','tomato'}
assert(A.Valid(corner,g)and A.Valid(center,g))
assert(P.Metrics(center,g).hole_cost<P.Metrics(corner,g).hole_cost)
local result,report=A.Regularize(corner,g,nil,false,200)
assert(A.Valid(result,g)and not P.Better(report.before,report.after))
local same={pattern_mismatch=0,line_cost=0,hole_cost=0,order_cost=0}
local offcenter={pattern_mismatch=0,line_cost=0,hole_cost=2,order_cost=0}
assert(P.Better(same,offcenter))
local used={};for _,k in ipairs(result)do if k then used[k]=(used[k]or 0)+1 end end
assert(used.potato==4 and used.tomato==4)
""")

 def build(self, data):
  L, result = runner._execute(runner.normalize(data))
  self.assertTrue(result.valid)
  b = result.plan
  self.assertTrue(b.optimal)
  self.assertEqual(b.total, b.upper)
  points = [{k: p[k] for k in ('x', 'z', 'cx', 'cz', 'crop')} for p in b.slots.values()]
  mismatch = benchmark.pattern_metrics(points)['pattern_mismatch']
  self.assertAlmostEqual(b.arrangement.after.pattern_mismatch, mismatch)
  self.assertLessEqual(tuple(b.arrangement.after[k] for k in FIELDS), tuple(b.arrangement.before[k] for k in FIELDS))
  return L, b, points

 def test_screenshot_stays_uniform_and_quantity_is_proven(self):
  _, b, points = self.build({'width': 5, 'height': 5, 'seeds': {'carrot': 192, 'corn': 192, 'potato': 192}})
  self.assertEqual(b.total, 225)
  self.assertEqual(Counter(p['crop'] for p in points), {'carrot': 75, 'corn': 75, 'potato': 75})
  motifs = benchmark.pattern_metrics(points)
  self.assertEqual(motifs['mismatched_tiles'], 0)
  self.assertEqual(set(tuple(v) for v in motifs['patterns'].values()), {('carrot',) * 3 + ('corn',) * 3 + ('potato',) * 3})
  self.assertEqual(b.arrangement.trials, 0)
  self.assertFalse(b.arrangement.limited)

 def test_irregular_fields_and_scarce_inventory_keep_hard_conditions(self):
  names = {'L-full', 'T-full', 'U-full', 'ring-full', 'bridge-full', 'T-minimum', 'U-tails', 'ring-scarce', 'unequal-tails'}
  for case in benchmark.cases():
   if case['id'] not in names:
    continue
   with self.subTest(case=case['id']):
    L, b, _ = self.build(case['input'])
    L.globals().b = b
    L.execute("""
local A=require('aom_seed_layout');local P=require('aom_seed_arrangement')
local defs=require('prefabs/farm_plant_defs').PLANT_DEFS
local board={};for i,p in ipairs(b.slots)do board[i]=p.crop or false end
local g=A.Geometry(b.tiles,b.slots,defs);g.balanced=true
assert(A.Valid(board,g))
local snapshot={};for i,k in ipairs(board)do snapshot[i]=k end
local before=P.Metrics(board,g)
local result,report=A.Regularize(board,g,nil,false,80)
for t=1,#board/9 do
 local old,new={},{}
 for s=1,9 do local i=(t-1)*9+s;local a,c=snapshot[i]or '_',result[i]or '_';old[a]=(old[a]or 0)+1;new[c]=(new[c]or 0)+1 end
 for k,n in pairs(old)do assert(new[k]==n)end
end
assert(A.Valid(result,g)and not P.Better(before,report.after))
local fresh=P.Metrics(result,g)
for _,k in ipairs({'pattern_mismatch','line_cost','hole_cost','order_cost'})do assert(math.abs(fresh[k]-report.after[k])<1e-6)end
""")

 def test_family_check_blocks_a_prettier_illegal_pattern(self):
  from test_giant_farming import World
  L = World().lua
  L.execute("""
local A=require('aom_seed_layout');local P=require('aom_seed_arrangement')
-- Spatial hard-check fixture: four single carrots must face inward to be a family.
-- Nutrient balance is deliberately outside this geometry-only test.
local tiles,slots,board={}, {},{}
for z=0,1 do for x=0,1 do
 tiles[#tiles+1]={x=x*4,z=z*4}
 local center=(z==0 and 2 or 0)*3+(x==0 and 2 or 0)+1
 local n=0
 for s=1,9 do
  local p={x=x*4+((s-1)%3-1)*1.3125,z=z*4+(math.floor((s-1)/3)-1)*1.3125}
  slots[#slots+1]=p;SpawnPrefab('farm_soil').Transform:SetPosition(p.x,0,p.z)
  if s==center then board[#board+1]='carrot'else n=n+1;board[#board+1]=n<=4 and 'corn' or 'potato'end
 end
end end
local g=A.Geometry(tiles,slots,DEFS);assert(A.Valid(board,g))
local uniform={};for t=1,4 do for s=1,9 do uniform[#uniform+1]=s==1 and 'carrot' or s<=5 and 'corn' or 'potato'end end
assert(P.Metrics(uniform,g).pattern_mismatch==0 and not A.Valid(uniform,g))
local result,report=A.Regularize(board,g,nil,false,120)
assert(A.Valid(result,g)and report.after.pattern_mismatch>0)
assert(not P.Better(report.before,report.after))
""")

 def test_compactness_is_diagnostic_only_and_not_recomputed_per_candidate(self):
  L, b, _ = self.build({'width': 2, 'height': 1, 'seeds': {'tomato': 40, 'potato': 40}})
  L.globals().b = b
  L.execute("""
local A=require('aom_seed_layout');local P=require('aom_seed_arrangement')
local g=A.Geometry(b.tiles,b.slots,require('prefabs/farm_plant_defs').PLANT_DEFS);g.balanced=true
local board={};for i,p in ipairs(b.slots)do board[i]=p.crop or false end
local metrics=A.Metrics;local calls=0
A.Metrics=function(...)calls=calls+1;return metrics(...)end
A.Better=function()error('quantity comparator must not be used in final arrangement')end
local _,report=A.Regularize(board,g,nil,false,100)
assert(calls==2 and report.objective==P.VERSION)
local a={pattern_mismatch=0,line_cost=100,hole_cost=100,order_cost=100,family=1e9,fragmentation=1e9}
local c={pattern_mismatch=1,line_cost=-100,hole_cost=0,order_cost=0,family=0,fragmentation=0}
assert(P.Better(a,c))
""")

 def test_independent_mismatch_counts_nonadjacent_equal_compositions(self):
  # A different-composition middle tile must not hide disagreement across the field.
  L, b, _ = self.build({'width': 3, 'height': 1, 'seeds': {'carrot': 40, 'corn': 40, 'potato': 40}})
  L.globals().b = b
  L.execute("""
local A=require('aom_seed_layout');local P=require('aom_seed_arrangement')
local g=A.Geometry(b.tiles,b.slots,require('prefabs/farm_plant_defs').PLANT_DEFS)
local board={};for i,p in ipairs(b.slots)do board[i]=p.crop or false end
for s=1,9 do board[9+s]=false end
local last=A.Transform(A.Tile(board,3),1);for s=1,9 do board[18+s]=last[s]end
oracle_board=board;oracle_metrics=P.Metrics(board,g)
""")
  board = list(L.globals().oracle_board.values())
  points = [{**p, 'crop': board[i]} for i, p in enumerate([{k: p[k] for k in ('x','z','cx','cz')} for p in b.slots.values()])]
  expected = benchmark.pattern_metrics(points)['pattern_mismatch']
  self.assertGreater(expected, 0)
  self.assertAlmostEqual(L.globals().oracle_metrics.pattern_mismatch, expected)


if __name__ == '__main__':
 unittest.main()
