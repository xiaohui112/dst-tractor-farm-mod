"""独立枚举原版配比，检查目录漏项，而非只校验目录已有内容。"""
import itertools
import unittest
from collections import Counter
import seed_strategy_audit as audit
from build_seed_catalog import recipes_for, variants


def full_grid_stocks():
 for season in ('autumn','winter','spring','summer'):
  crops=sorted(c for c,d in audit.RULES.items() if season in d['seasons'])
  for weights in ((6,12),(6,6,6)):
   combos=itertools.permutations(crops,2) if len(weights)==2 else itertools.combinations(crops,3)
   for values in combos:
    if all(sum(n*audit.RULES[c]['net'][i] for c,n in zip(values,weights))==0 for i in range(3)):
     yield season,dict(zip(values,weights))


class FullGridCoverageTests(unittest.TestCase):
 def solve(self,stock,season,tiles,lock=None):
  w=audit.world();inst=w.make(stock,season)
  inst._seed_strategy='GIANT_TEMPLATE';inst._aom_template_id=lock
  for x,z in tiles:
   for s in range(9):w.lua.globals().SpawnPrefab('farm_soil').Transform.SetPosition(None,x*4+(s%3-1)*4/3,0,z*4+(s//3-1)*4/3)
  result=w.lua.eval("require('aom_dynamic_farm').Build")(inst,tiles[0][0]*4,tiles[0][1]*4)
  b=result[0] if isinstance(result,tuple) else result
  if b:
   self.assertTrue(w.lua.eval("require('aom_dynamic_farm').Validate")(b)[0])
   points=[{k:p[k] for k in ('x','z','cx','cz','crop')} for p in b.slots.values()]
   errors,_=audit.independent_check(dict(stock=stock,season=season,tiles=tiles),points)
   self.assertEqual(errors,[])
  return b

 def test_all_native_balanced_pairs_and_triples_fill_both_orientations_and_irregular_fields(self):
  fields=[[(0,0),(1,0)],[(0,0),(0,1)],
          [(-3,5),(-2,5)],[(5,-3),(5,-2)],
          [(0,0),(1,0),(1,1)],[(0,0),(0,1),(1,1),(1,2)]]
  for season,stock in full_grid_stocks():
   for tiles in fields:
    with self.subTest(season=season,stock=stock,tiles=tiles):
     b=self.solve(stock,season,tiles);self.assertIsNotNone(b)
     self.assertEqual(b.total,18)
     self.assertEqual(dict(Counter(p.crop for p in b.slots.values() if p.crop)),stock)

 def test_inventory_boundaries_do_not_hide_missing_full_grid_recipes(self):
  for season,stock in full_grid_stocks():
   lock='program-18-equal' if len(stock)==3 else 'program-18-ratio'
   for extra in (0,1):
    with self.subTest(season=season,stock=stock,extra=extra):
     b=self.solve({c:n+extra for c,n in stock.items()},season,[(0,0),(1,0)],lock)
     self.assertIsNotNone(b);self.assertEqual(b.total,18)
   for scarce in stock:
    with self.subTest(season=season,stock=stock,scarce=scarce):
     b=self.solve({c:n-(c==scarce) for c,n in stock.items()},season,[(0,0),(1,0)],lock)
     self.assertIsNone(b)

 def test_source_templates_cannot_opt_into_generated_substitutions(self):
  spec=dict(source='autumn',roles={'A':['carrot'],'B':['corn'],'C':['potato']},recipe_policy='balanced_vanilla')
  with self.assertRaises(AssertionError):recipes_for(spec,{'A':6,'B':6,'C':6},list(variants(['AAAAAA','BBBBBB','CCCCCC'])))


if __name__=='__main__':unittest.main()
