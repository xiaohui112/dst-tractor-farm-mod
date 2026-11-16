"""网页锁定、坐标复现与输入边界，规划始终调用Mod。"""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import runner
class TemplateCatalogWebTests(unittest.TestCase):
 def test_all_native_full_grid_combinations_are_available_without_a_picture_recipe(self):
  # 独立用游戏作物定义枚举需求，不读取目录的recipes来生成预期。
  import itertools
  defs=runner.metadata()['crops']
  for season in ('autumn','winter','spring','summer'):
   crops=[c for c in defs if season in c['seasons']]
   for weights in ((6,12),(6,6,6)):
    choices=itertools.permutations(crops,2) if len(weights)==2 else itertools.combinations(crops,3)
    for values in choices:
     if any(sum(n*c['nutrient_net'][i] for c,n in zip(values,weights)) for i in range(3)):continue
     stock={c['id']:n for c,n in zip(values,weights)}
     with self.subTest(season=season,stock=stock):
      r=runner.run({'strategy':'GIANT_TEMPLATE','season':season,'width':2,'height':1,'seeds':stock})
      self.assertEqual(r['count'],18);self.assertEqual(r['used'],stock)
      self.assertTrue(r['valid']);self.assertTrue(r['checks']['complete_templates'])
 def test_catalog_comes_from_mod_and_lock_survives_roundtrip(self):
  meta=runner.metadata();self.assertEqual(len(meta['templates']),30)
  self.assertIn('aom_seed_catalog.lua',runner.MODULES)
  base={'strategy':'GIANT_TEMPLATE','template_id':'autumn-09','season':'autumn','width':2,'height':1,'seeds':{'garlic':4,'onion':4,'potato':8}}
  r=runner.run(base);self.assertEqual(r['count'],16);self.assertTrue(r['checks']['complete_templates'])
  self.assertEqual(r['input']['template_id'],'autumn-09');self.assertEqual([m['id'] for m in r['template_modules']],['autumn-09'])
  self.assertEqual(r['template_modules'][0]['symmetry'],0)
  self.assertEqual(r['template_modules'][0]['origin'],{'x':0,'z':0})
  repeat=runner.run(r['input']);self.assertEqual(r['slots'],repeat['slots'])
 def test_lock_rejects_disabled_unknown_or_optimal_strategy(self):
  for strategy,id in [('GIANT_TEMPLATE','autumn-03'),('GIANT_TEMPLATE','unknown'),('GIANT','autumn-09')]:
   with self.subTest(strategy=strategy,id=id),self.assertRaises(ValueError):runner.normalize({'strategy':strategy,'template_id':id})
 def test_same_stock_can_reproduce_two_pairs_or_one_square(self):
  base={'strategy':'GIANT_TEMPLATE','season':'spring','width':2,'height':2,'seeds':{'garlic':8,'onion':8,'potato':16}}
  for id,count in [('spring-11',2),('spring-12',1)]:
   r=runner.run({**base,'template_id':id});self.assertEqual(r['count'],32);self.assertEqual(len(r['template_modules']),count)
 def test_picture32_corner_holes_and_single8_center_hole_are_distinct(self):
  r=runner.run({'strategy':'GIANT_TEMPLATE','template_id':'autumn-10','width':2,'height':2,'seeds':{'tomato':16,'potato':16}})
  self.assertEqual(r['count'],32);self.assertEqual(len(r['template_modules']),1)
  self.assertEqual({(p['x'],p['z']) for p in r['slots'] if not p['crop']},{(runner.f32(x),runner.f32(z)) for x,z in ((-4/3,-4/3),(-4/3,4+4/3),(4+4/3,-4/3),(4+4/3,4+4/3))})
  single=runner.run({'strategy':'GIANT_TEMPLATE','template_id':'autumn-01','width':1,'height':1,'seeds':{'tomato':4,'potato':4}})
  self.assertEqual([(p['x'],p['z']) for p in single['slots'] if not p['crop']],[(0,0)])
if __name__=='__main__':unittest.main()
