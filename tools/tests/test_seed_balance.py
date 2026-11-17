"""互补配比、预留坑、优先级与旧存档兼容；独立核对原版净变化。"""
import itertools,sys,unittest
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import seed_strategy_audit as audit
import test_giant_farming as giant

class BalancedSeedTests(unittest.TestCase):
 def make(self,stock,season='autumn',tiles=((0,0),)):
  w=giant.World();L=w.lua;L.globals().inst=w.make(stock,season)
  L.execute("D=require('aom_dynamic_farm');B=require('aom_seed_balance');inst.components.container.numslots=15;TheWorld.components.farming_manager.GetTileNutrients=function()error('unexpected soil nutrient read')end")
  for x,z in tiles:
   for row in (-1,0,1):
    for col in (-1,0,1):L.globals().SpawnPrefab('farm_soil').Transform.SetPosition(None,x*4+col*4/3,0,z*4+row*4/3)
  b=L.globals().D.Build(L.globals().inst,tiles[0][0]*4,tiles[0][1]*4)
  return w,b[0] if isinstance(b,tuple) else b
 def test_native_vectors_match_independent_restoration_arithmetic(self):
  w=giant.World();balance=w.lua.eval("require('aom_seed_balance')")
  for k in giant.CONSUME:
   self.assertEqual(list(balance.Vector(w.lua.globals().DEFS[k]).values()),giant.net({k:1}),k)
 def test_all_seasons_pattern_enumeration_matches_independent_multisets(self):
  for season in ('autumn','winter','spring','summer'):
   w=audit.world();L=w.lua
   crops,expected=audit.balanced_patterns(season)
   stocks=L.table_from({k:9 for k in crops});defs=L.globals().DEFS
   balance=L.eval("require('aom_seed_balance')")
   patterns,_=balance.Patterns(L.table_from(crops),stocks,defs,None)
   actual={tuple(int(p.counts[i]) for i in range(1,len(crops)+1)) for p in patterns.values()}
   self.assertEqual(actual,set(expected),season)
 def test_every_native_complementary_pair_preserves_four_four(self):
  cases=0
  for season in ('autumn','winter','spring','summer'):
   crops=[k for k in audit.RULES if season in audit.RULES[k]['seasons']]
   for a,b in itertools.combinations(crops,2):
    if any(x+y for x,y in zip(audit.RULES[a]['net'],audit.RULES[b]['net'])):continue
    with self.subTest(season=season,a=a,b=b):
     _,plan=self.make({a:100,b:100},season)
     self.assertEqual(plan.total,8)
     self.assertEqual(Counter(p.crop for p in plan.slots.values() if p.crop),{a:4,b:4})
     cases+=1
  self.assertGreater(cases,0)
  # 原版8级消耗还会形成4:8配比，不能把互补误写成始终1:1。
  weighted=0
  for season in ('autumn','winter','spring','summer'):
   crops=[k for k in audit.RULES if season in audit.RULES[k]['seasons']]
   for a,b in itertools.combinations(crops,2):
    choices=[(m+n,m,n) for m in range(4,17) for n in range(4,17) if m!=n and all(m*x+n*y==0 for x,y in zip(audit.RULES[a]['net'],audit.RULES[b]['net']))]
    if not choices:continue
    _,m,n=min(choices)
    with self.subTest(weighted=True,season=season,a=a,b=b):
     _,plan=self.make({a:m,b:n},season,((0,0),(1,0)))
     self.assertIsNotNone(plan);self.assertEqual(plan.total,m+n)
     self.assertEqual(Counter(p.crop for p in plan.slots.values() if p.crop),{a:m,b:n})
     weighted+=1
  self.assertGreater(weighted,0)
  _,plan=self.make({'carrot':8,'corn':8,'pepper':4},tiles=((0,0),(1,0),(0,1),(1,1)))
  self.assertIsNotNone(plan);self.assertEqual(plan.total,20)
 def test_monoculture_and_unbalanced_stock_do_not_spend_seeds(self):
  for stock in ({'potato':40},{'carrot':40,'corn':40},{'tomato':3,'potato':20}):
   w,plan=self.make(stock)
   self.assertIsNone(plan);self.assertEqual(w.lua.globals().inst.components.aom_attachment_store.GetSeedCount(w.lua.globals().inst.components.aom_attachment_store),sum(stock.values()))
 def test_global_balance_cannot_cancel_between_separate_tiles(self):
  w,b=self.make({'tomato':8,'potato':8},tiles=((0,0),(1,0)))
  slots=list(b.slots.values());p=next(p for p in slots[:9] if p.crop=='potato');q=next(p for p in slots[9:] if p.crop=='tomato')
  p.crop,q.crop=q.crop,p.crop
  self.assertFalse(w.lua.globals().D.Validate(b))
 def test_center_can_be_occupied_without_changing_four_four_counts(self):
  w,b=self.make({'tomato':40,'potato':40})
  for p,k in zip(b.slots.values(),['potato','potato','potato','potato','tomato','tomato',False,'tomato','tomato']):p.crop=k
  self.assertEqual(w.lua.globals().D.Validate(b),(True,8))
  self.assertEqual(Counter(p.crop for p in b.slots.values() if p.crop),{'tomato':4,'potato':4})
 def test_nutrient_balance_still_prevents_filling_a_ninth_plant(self):
  w,b=self.make({'tomato':40,'potato':40})
  next(p for p in b.slots.values() if not p.crop).crop='potato'
  self.assertFalse(w.lua.globals().D.Validate(b))
 def test_new_rule_marker_survives_save_and_load(self):
  w,b=self.make({'tomato':8,'potato':8},tiles=((0,0),(1,0)))
  L=w.lua;L.globals().inst._block=b
  L.execute("Block=require('aom_block_plan');data=Block.OnSave(inst);assert(data.nutrient_balanced);other=make_inst({},'autumn');Block.OnLoad(other,data);assert(other._block.nutrient_balanced and D.Validate(other._block))")
 def test_legacy_unbalanced_plan_keeps_locked_coordinates(self):
  w,b=self.make({'tomato':40,'potato':40});L=w.lua
  hole=next(i for i,p in b.slots.items() if not p.crop)
  b.slots[hole].crop='potato';b.nutrient_balanced=None;b.total=9;L.globals().filled_hole=hole
  self.assertEqual(L.globals().D.Validate(b),(True,9))
  L.globals().inst._block=b
  L.execute("Block=require('aom_block_plan');data=Block.OnSave(inst);other=make_inst({},'autumn');Block.OnLoad(other,data);assert(other._block and other._block.total==9 and not other._block.nutrient_balanced and other._block.slots[filled_hole].crop=='potato')")
 def test_compactness_precedes_tidy_weighted_score(self):
  w=giant.World();L=w.lua
  L.execute("A=require('aom_seed_layout');assert(A.Better({fragmentation=0,family=100,tidy=100000},{fragmentation=1,family=0,tidy=-100000}));assert(A.Better({fragmentation=0,family=99,tidy=100000},{fragmentation=0,family=100,tidy=-100000}));assert(not A.Better({fragmentation=1,family=0,tidy=-100000},{fragmentation=0,family=100,tidy=100000}))")

if __name__=='__main__':unittest.main()
