"""网页没有独立播种器：大田仍由Mod计算和校验。"""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import runner


class LargeTemplateTests(unittest.TestCase):
 def test_large_field_and_per_strategy_limits(self):
  data={'width':9,'height':9,'season':'autumn','seeds':{'tomato':324,'potato':324}}
  r=runner.run({**data,'strategy':'GIANT_TEMPLATE','template_id':'autumn-01'})
  self.assertEqual((r['count'],len(r['tiles'])),(648,81))
  self.assertEqual(r['checks']['family_passed'],648)
  self.assertTrue(r['checks']['complete_templates'])
  rejected=runner.run({**data,'strategy':'GIANT'})
  self.assertEqual(rejected['reason'],'FARM_TOO_LARGE')
  self.assertEqual(runner.metadata()['strategy_limits'],{'GIANT':64,'GIANT_TEMPLATE':None})

 def test_wide_field_and_sparse_canvas_have_no_old_32_or_1024_limit(self):
  data=runner.normalize({'strategy':'GIANT_TEMPLATE','width':33,'height':1,'seeds':{}})
  self.assertEqual(len(data['tiles']),33)
  data=runner.normalize({'strategy':'GIANT_TEMPLATE','width':33,'height':33,'seeds':{}})
  self.assertEqual(len(data['tiles']),1089)
  r=runner.run({'strategy':'GIANT_TEMPLATE','width':10000,'height':1,'tiles':[[9999,0]],'start':[9999,0],'seeds':{'tomato':4,'potato':4}})
  self.assertEqual(r['count'],8)
  self.assertEqual(r['tiles'],[{'x':39996,'z':0}])


if __name__=='__main__':unittest.main()
