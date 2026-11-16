"""固定模版与最优模式：真实Lua入口、库存、坐标及跨策略状态。"""
import itertools
import unittest
from collections import Counter
from test_giant_farming import World

class TemplateStrategyTests(unittest.TestCase):
 def setUp(self):
  self.w=World();self.L=self.w.lua
  self.L.execute("D=require('aom_dynamic_farm');B=require('aom_block_plan')")
 def field(self,tiles):
  for tx,tz in tiles:
   for dx in (-1,0,1):
    for dz in (-1,0,1):self.L.globals().SpawnPrefab('farm_soil').Transform.SetPosition(None,tx*4+dx*4/3,0,tz*4+dz*4/3)
 def plan(self,stock,tiles,mode='GIANT_TEMPLATE',season='spring',template_id=None):
  self.field(tiles);inst=self.w.make(stock,season);inst._seed_strategy=mode;inst._aom_template_id=template_id
  result=self.L.globals().D.Build(inst,tiles[0][0]*4,tiles[0][1]*4)
  return inst,result[0]if isinstance(result,tuple)else result
 def test_two_tile_full_ratio_and_equal_templates(self):
  for stock in ({'dragonfruit':6,'tomato':12},{'carrot':6,'corn':6,'potato':6}):
   with self.subTest(stock=stock):
    self.setUp();inst,p=self.plan(stock,[(0,0),(1,0)])
    self.assertEqual(p.total,18);self.assertTrue(self.L.globals().D.Validate(p)[0])
    self.assertEqual(dict(Counter(s.crop for s in p.slots.values()if s.crop)),stock)
    self.assertEqual(inst.components.aom_attachment_store.GetSeedCount(inst.components.aom_attachment_store),18)
 def test_low_inventory_templates_and_single_center_gap(self):
  for stock,tiles,count in [({'dragonfruit':4,'tomato':8},[(0,0),(1,0)],12),({'carrot':4,'corn':4,'potato':4},[(0,0),(1,0)],12),({'tomato':4,'potato':4},[(0,0)],8)]:
   self.setUp();_,p=self.plan(stock,tiles);self.assertEqual(p.total,count)
   if len(tiles)==1:self.assertFalse(p.slots[5].crop)
 def test_reference_squares_keep_exact_crop_positions_for_all_alternatives(self):
  specs=[(['_CCCC_']+['ACBBCA']*4+['_CCCC_'],{'A':['durian','garlic'],'B':['pomegranate','onion'],'C':['eggplant','potato']}),(['_BBBB_']+['BACCAB']*4+['_BBBB_'],{'A':['dragonfruit'],'B':['carrot'],'C':['durian','garlic']}),(['_BBBB_']+['DCAACD']*4+['_BBBB_'],{'A':['watermelon'],'B':['eggplant','potato'],'C':['pomegranate','onion'],'D':['asparagus','corn']})]
  for template_id,(grid,roles) in zip(('spring-12','spring-08','spring-04'),specs):
   for values in itertools.product(*roles.values()):
    self.setUp();mapping=dict(zip(roles,values));stock=dict(Counter(mapping[c]for row in grid for c in row if c!='_'))
    _,p=self.plan(stock,[(0,0),(1,0),(0,1),(1,1)],template_id=template_id)
    self.assertEqual(p.total,32);self.assertEqual(len(p.construction.modules),1)
    for point in p.slots.values():
     col=round((point.x-point.cx)/(4/3))+1+int(point.cx/4)*3
     row=round((point.z-point.cz)/(4/3))+1+int(point.cz/4)*3
     self.assertEqual(point.crop,mapping.get(grid[row][col],False),(stock,row,col))
 def test_strategy_cache_is_separate_and_old_mode_remains_optimal(self):
  inst,p=self.plan({'tomato':8,'potato':8},[(0,0)])
  second=self.L.globals().D.Build(inst,0,0);self.assertTrue(second.construction.cache_hit);self.assertEqual(second.construction.template_prepare_seconds,0);self.assertEqual(second.construction.template_select_seconds,0)
  inst._seed_strategy='GIANT';optimal=self.L.globals().D.Build(inst,0,0)
  self.assertTrue(optimal.optimal);self.assertFalse(bool(optimal.construction.cache_hit))
  self.assertEqual(optimal.strategy,'GIANT')
 def test_saved_template_and_legacy_optimal_plan_resume_without_replanning(self):
  inst,p=self.plan({'dragonfruit':6,'tomato':12},[(0,0),(1,0)]);inst._block=p
  saved=self.L.globals().B.OnSave(inst);self.assertEqual(saved.strategy,'GIANT_TEMPLATE')
  inst._block=None;self.L.globals().B.OnLoad(inst,saved);self.assertEqual(inst._block.strategy,'GIANT_TEMPLATE');self.assertEqual(inst._block.total,18)
  saved.strategy=None;self.L.globals().B.OnLoad(inst,saved);self.assertEqual(inst._block.strategy,'GIANT')
 def test_insufficient_or_out_of_season_inventory_does_not_fake_giants(self):
  for stock in ({'tomato':3,'potato':3},{'dragonfruit':6,'tomato':12}):
   self.setUp();_,p=self.plan(stock,[(0,0),(1,0)],season='winter');self.assertIsNone(p)

if __name__=='__main__':unittest.main()
