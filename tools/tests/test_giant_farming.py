"""在 Lua 5.1 中执行真实规划/作业/物料仓代码；引擎地图和实体为可观察桩。
运行：PYTHONPATH=/tmp/pylua python3 -m unittest discover -s tools/tests -v
这些是行为回归测试，不代替 DST 客户端与联机验收。
"""
from pathlib import Path
import unittest
from collections import Counter, defaultdict
from lupa.lua51 import LuaRuntime

ROOT=Path(__file__).resolve().parents[2]
CONSUME={'carrot':[4,0,0],'corn':[0,4,0],'potato':[0,0,4],'tomato':[2,2,0],
 'asparagus':[0,4,0],'eggplant':[0,0,4],'pumpkin':[4,0,0],'watermelon':[0,2,2],
 'dragonfruit':[0,0,8],'durian':[0,8,0],'garlic':[0,8,0],'onion':[8,0,0],
 'pepper':[0,0,8],'pomegranate':[8,0,0]}
SEASONS={'carrot':'autumn winter spring','corn':'autumn spring summer','potato':'autumn winter spring',
 'tomato':'autumn spring summer','asparagus':'winter spring','eggplant':'autumn spring',
 'pumpkin':'autumn winter','watermelon':'spring summer','dragonfruit':'spring summer',
 'durian':'spring','garlic':'autumn winter spring summer','onion':'autumn spring summer',
 'pepper':'autumn summer','pomegranate':'spring summer'}

def as_dict(t):return {k:v for k,v in t.items()}
def net(ratio):
 out=[0,0,0]
 for crop,n in ratio.items():
  c=CONSUME[crop];restore=sum(c)//c.count(0)
  for i in range(3):out[i]+=n*(-c[i] if c[i] else restore)
 return out

class World:
 def __init__(self):
  self.lua=LuaRuntime(unpack_returned_tuples=True)
  L=self.lua
  defs={}
  for crop,c in CONSUME.items():
   defs[crop]=L.table_from({'nutrient_consumption':L.table_from(c),'nutrient_restoration':L.table_from({i+1:True for i,n in enumerate(c) if n==0}),'good_seasons':L.table_from({s:True for s in SEASONS[crop].split()}),'family_min_count':4,'family_check_dist':4})
  L.globals().DEFS=L.table_from(defs)
  L.globals().SCRIPTS=str(ROOT/'mod/AgeOfMachines/scripts')
  L.execute('''
package.path=SCRIPTS.."/?.lua;"..package.path
package.preload["prefabs/farm_plant_defs"]=function()return {PLANT_DEFS=DEFS}end
AOM_ATTACHMENT_TYPE={PLOW='plow',SEEDER='seeder',IRRIGATOR='irrigator',FERTILIZER='fertilizer',WEEDER='weeder',HARVESTER='harvester'}
package.preload.aom_common=function()return {TYPE=AOM_ATTACHMENT_TYPE,STATUS={},WORK_TICK=.5,FUEL_PER_TICK=1}end
TUNING={FARM_PANT_OVERCROWDING_MAX_PLANTS=10};WORLD_TILES={FARMING_SOIL=1};ACTIONS={DIG={id='DIG'}}
function Class(ctor)local c={};c.__index=c;return setmetatable(c,{__call=function(cls,...)local o=setmetatable({},cls);ctor(o,...);return o end})end
function Vector3(x,y,z)return {x=x,y=y,z=z,Get=function()return x,y,z end}end
ENTITIES={};TILES={};PLANT_FAIL=false
function center(v)return math.floor((v+2)/4)*4 end
function tkey(x,z)return center(x)..':'..center(z)end
function SpawnPrefab(name)
 local v={prefab=name,valid=true,x=0,z=0,components={},tags={}}
 if name=='farm_soil' then v.tags.soil=true elseif string.sub(name,1,11)=='farm_plant_' then v.tags.farm_plant=true elseif string.sub(name,1,5)=='weed_' then v.tags.weed=true end
 function v:IsValid()return self.valid end
 function v:HasTag(t)return self.tags[t]end
 function v:Remove()self.valid=false end
 v.Transform={GetWorldPosition=function()return v.x,0,v.z end,SetPosition=function(self,x,y,z)v.x=x;v.z=z end}
 ENTITIES[#ENTITIES+1]=v;return v
end
TheSim={FindEntities=function(self,x,y,z,r,must,exclude)
 local out={}
 for _,v in ipairs(ENTITIES)do
  local ok=v.valid and (v.x-x)^2+(v.z-z)^2<=r*r
  for _,tag in ipairs(must or {})do if not v:HasTag(tag)then ok=false end end
  for _,tag in ipairs(exclude or {})do if v:HasTag(tag)then ok=false end end
  if ok then out[#out+1]=v end
 end
 return out
end}
TheWorld={state={season='autumn'},components={},Map={}}
function TheWorld.Map:GetTileCenterPoint(x,y,z)return center(x),0,center(z)end
function TheWorld.Map:GetTileAtPoint(x,y,z)local v=TILES[tkey(x,z)];return v==nil and 1 or v end
function TheWorld.Map:GetTileCoordsAtPoint(x,y,z)return center(x)/4,center(z)/4 end
TheWorld.components.farming_manager={GetTileNutrients=function()return 100,100,100 end}
function TheWorld.Map:IsPassableAtPoint(x,y,z)return TILES[tkey(x,z)]~=-1 end
function TheWorld.Map:GetEntitiesOnTileAtPoint(x,y,z)
 local out={};for _,v in ipairs(ENTITIES)do if v.valid and tkey(v.x,v.z)==tkey(x,z)then out[#out+1]=v end end;return out
end
function TheWorld.Map:CanTillSoilAtPoint(x,y,z)
 if self:GetTileAtPoint(x,y,z)~=1 then return false end
 for _,v in ipairs(ENTITIES)do if v.valid and (v.x-x)^2+(v.z-z)^2<.999 then return false end end
 return true
end
function TheWorld.Map:CollapseSoilAtPoint()end
function make_seed(crop,n)
 local item={prefab=crop..'_seeds',valid=true,components={}}
 function item:IsValid()return self.valid end
 function item:Remove()self.valid=false end
 item.components.farmplantable={plant='farm_plant_'..crop}
 function item.components.farmplantable:Plant(soil,doer)
  if PLANT_FAIL then return false end
  local x,y,z=soil.Transform:GetWorldPosition();soil:Remove()
  SpawnPrefab('farm_plant_'..crop).Transform:SetPosition(x,y,z)
  item:Remove();return true
 end
 local count=n
 item.components.stackable={StackSize=function()return count end,Get=function(self,take)count=count-take;return make_seed(crop,take)end}
 return item
end
local Store=require('components/aom_attachment_store')
function make_inst(counts,season)
 TheWorld.state.season=season
 local inst={prefab='aom_tractor_chassis',_seed_strategy='GIANT',_attachment_type='plow',components={},x=0,z=0,_working=false,PushEvent=function()end}
 inst.Transform={GetWorldPosition=function()return inst.x,0,inst.z end}
 inst.components.finiteuses={used=0,Use=function(self,n)self.used=self.used+n end}
 inst.AnimState={IsCurrentAnimation=function()return false end}
 local function net(v)return {value=function()return v end,set=function(self,n)v=n end}end
 inst._workstatus=net(false);inst._workreason_net=net('');inst._planprogress_net=net('');inst._fuel=net(800)
 local c={slots={},numslots=9}
 function c:GetItemInSlot(i)return self.slots[i]end
 function c:RemoveItem(item)for k,v in pairs(self.slots)do if v==item then self.slots[k]=nil end end end
 function c:GiveItem(item)for i=2,9 do if not self.slots[i]then self.slots[i]=item;return true end end;error('container full')end
 local uses=60
 c.slots[1]={attachment_type='plow',IsValid=function()return true end,components={finiteuses={
 GetUses=function()return uses end,SetUses=function(_,n)uses=n end,Use=function(_,n)uses=uses-n end}}}
 inst.components.container=c
 inst._rider={components={},Transform=inst.Transform,PushEvent=function()end}
 local i=2;for crop,n in pairs(counts)do c.slots[i]=make_seed(crop,n);i=i+1 end
 inst.components.aom_attachment_store=Store(inst)
 inst.components.aom_attachment_store:SetMaterialContainer(c)
 inst._aom_terraformer={components={terraformer={Terraform=function(self,pt)TILES[tkey(pt.x,pt.z)]=1;return true end}}}
 return inst
end
Block=require('aom_block_plan');Drive=require('aom_drive');Farm=require('aom_farm_work');Seed=require('aom_seed_strategy')
function reset_world()ENTITIES={};TILES={};PLANT_FAIL=false end
function crop_count()local n=0;for _,v in ipairs(ENTITIES)do if v.valid and v:HasTag('farm_plant')then n=n+1 end end;return n end
''')
  self.block=L.globals().Block;self.drive=L.globals().Drive;self.farm=L.globals().Farm
 def make(self,counts,season='autumn'):
  return self.lua.globals().make_inst(self.lua.table_from(counts),season)
 def combo(self,ident):
  season=ident.split('-')[0]
  return next(c for _,c in self.block.BLOCKS[season].items() if c.id==ident)
 def bind(self,inst,c):
  self.block.OnLoad(inst,self.lua.table_from({'version':2,'combo_id':c.id,'season':c.id.split('-')[0],'x':0,'z':0,'rotation':0,'completed':self.lua.table()}))
 def prepare(self,inst):
  _,tiles=self.block.WorldSlots(inst._block)
  inst._attachment_type='plow'
  for _,tile in tiles.items():
   inst.x=tile.x;inst.z=tile.z
   self.drive.WorkHere(inst)
 def sow_all(self,inst,c):
  inst._attachment_type='seeder'
  _,tiles=self.block.WorldSlots(inst._block)
  for _,tile in tiles.items():
   inst.x=tile.x;inst.z=tile.z
   while True:
    result=self.drive.WorkHere(inst)
    ok=result[0] if isinstance(result,tuple) else result
    if not ok:break
  return inst._block.done

class GiantFarmingTests(unittest.TestCase):
 def setUp(self):self.w=World()
 def test_load_action_uses_the_real_material_store_interface(self):
  w=self.w
  text=(ROOT/'mod/AgeOfMachines/modmain.lua').read_text()
  start=text.index('local AOM_LOAD = AddAction(')
  end=text.index('AOM_LOAD.distance',start)
  w.lua.execute('AddAction=function(id,label,fn)LoadAction=fn;return {} end')
  w.lua.execute(text[start:end])
  inst=w.make({});inst._attachment_type='seeder'
  item=w.lua.globals().make_seed('tomato',8)
  action=w.lua.table_from({'target':inst,'invobject':item})
  self.assertTrue(w.lua.globals().LoadAction(action))
  store=inst.components.aom_attachment_store
  self.assertEqual(store.GetSeedCount(store),8)
 def test_catalog_expands_or_and_preserves_exception(self):
  w=self.w
  self.assertEqual([len(w.block.BLOCKS[s]) for s in ['autumn','winter','spring','summer']],[21,4,72,14])
  self.assertEqual(as_dict(w.combo('autumn-01-01').ratio),{'tomato':4,'eggplant':4})
  self.assertEqual(as_dict(w.combo('spring-02-02').ratio),{'tomato':4,'potato':4})
  for ident in ['summer-05-01','summer-05-02']:
   c=w.combo(ident);self.assertEqual(list(c.not_giant.values()),['tomato']);self.assertEqual(len(as_dict(c.ratio)),5)
 def test_every_automatic_layout_balances_each_tile_and_family(self):
  w=self.w;active=0
  for season,combos in w.block.BLOCKS.items():
   for _,c in combos.items():
    if c.reference_only:
     self.assertTrue(c.id.startswith('winter-02-'));continue
    active+=1
    self.assertTrue(w.block.ValidateCombo(c,season))
    crops=Counter();tiles=defaultdict(Counter);points=[]
    for _,p in c.slots.items():
     if p.crop:
      crops[p.crop]+=1;tiles[(p.tx,p.tz)][p.crop]+=1;points.append((p.tx*4+p.x,p.tz*4+p.z,p.crop))
    self.assertEqual(dict(crops),as_dict(c.ratio))
    for ratio in tiles.values():self.assertLessEqual(sum(ratio.values()),10);self.assertEqual(net(ratio),[0,0,0])
    exempt=set(c.not_giant.values())
    for x,z,crop in points:
     if crop not in exempt:self.assertGreaterEqual(sum(crop==q and (x-a)**2+(z-b)**2<=16+1e-8 for a,b,q in points),4)
  self.assertEqual(active,109)
 def test_new_farm_tile_can_be_ploughed_without_existing_mounds(self):
  w=self.w
  self.assertTrue(w.farm.CanWorkAt('plow',0,0,0))
  self.assertTrue(w.farm.Plough(0,0,0,None,None))
  self.assertEqual(sum(v.prefab=='farm_soil' and v.valid for v in w.lua.globals().ENTITIES.values()),9)
  self.assertFalse(w.farm.CanWorkAt('plow',0,0,0))
 def test_landclearer_clears_debris_and_leaves_ready_field(self):
  """开垦机一次作业：清掉园艺残渣，并整出可直接播种的 3x3 坑位。"""
  w=self.w
  w.lua.execute("""
TILES[tkey(0,0)]=1
for i=1,3 do
  local d=SpawnPrefab('farm_soil_debris')
  d.valid=true; d.x=-1.0+i*0.9; d.z=1.2; d.prefab='farm_soil_debris'
  d.Transform={GetWorldPosition=function() return d.x,0,d.z end}
  function d:IsValid()return self.valid end
  function d:HasTag(t)return false end
  d.components={workable={GetWorkAction=function()return ACTIONS.DIG end,CanBeWorked=function()return true end,GetWorkLeft=function()return 1 end,WorkedBy=function(self,doer,n) d.valid=false end}}
end
""")
  self.assertGreaterEqual(sum(1 for v in w.lua.globals().ENTITIES.values() if v.prefab=='farm_soil_debris'),3)
  self.assertTrue(w.farm.Plough(0,0,0,w.lua.table_from({'PushEvent':w.lua.eval('function()end')}),None)[0])
  ents=list(w.lua.globals().ENTITIES.values())
  self.assertEqual(sum(1 for v in ents if v.prefab=='farm_soil_debris' and v.valid),0)
  self.assertEqual(sum(1 for v in ents if v.prefab=='farm_soil' and v.valid),9)
  self.assertTrue(w.farm.IsFieldReady(0,0,0))

 def test_eight_plant_layout_leaves_ninth_slot_empty(self):
  w=self.w;c=w.combo('autumn-01-02');inst=w.make(as_dict(c.ratio));w.bind(inst,c);w.prepare(inst)
  self.assertEqual(w.sow_all(inst,c),8)
  self.assertEqual(w.lua.globals().crop_count(),8)
  self.assertFalse(w.drive.WorkHere(inst)[0]);self.assertEqual(w.lua.globals().crop_count(),8)
 def test_failed_planting_returns_seed_without_committing(self):
  w=self.w;c=w.combo('autumn-01-02');inst=w.make(as_dict(c.ratio));w.bind(inst,c);w.prepare(inst)
  inst._attachment_type='seeder';w.lua.globals().PLANT_FAIL=True
  before=inst.components.aom_attachment_store.GetSeedCount(inst.components.aom_attachment_store)
  self.assertFalse(w.drive.WorkHere(inst)[0]);self.assertEqual(inst._block.done,0)
  self.assertEqual(inst.components.aom_attachment_store.GetSeedCount(inst.components.aom_attachment_store),before)
  self.assertEqual(w.lua.globals().crop_count(),0)
 def test_short_stock_never_falls_back_to_other_seeds(self):
  w=self.w;c=w.combo('autumn-01-02');inst=w.make({'tomato':4,'potato':4,'carrot':40});w.bind(inst,c);w.prepare(inst)
  # 丢失一个种子堆之后，即使有大量不相关种子也必须暂停。
  store=inst.components.aom_attachment_store
  for _,item in store.ListSeeds(store).items():
   if item.prefab=='potato_seeds':store.container.RemoveItem(store.container,item)
  inst._attachment_type='seeder'
  self.assertEqual(w.drive.WorkHere(inst),(False,'MISSING_SEEDS'))
  self.assertEqual(w.lua.globals().crop_count(),0)
 def test_incomplete_stock_does_not_start_plan(self):
  w=self.w;inst=w.make({'tomato':3,'potato':4,'carrot':40});inst._attachment_type='seeder'
  self.assertEqual(w.drive.WorkHere(inst),(False,'MISSING_SEEDS'));self.assertIsNone(inst._block)
 def test_saved_plan_resumes_at_exact_coordinates(self):
  w=self.w;c=w.combo('winter-01-01');inst=w.make(as_dict(c.ratio),'winter');w.bind(inst,c);w.prepare(inst)
  inst._attachment_type='seeder';self.assertTrue(w.drive.WorkHere(inst));self.assertEqual(inst._block.done,1)
  saved=w.block.OnSave(inst);other=w.make({},'winter');other.components.aom_attachment_store=inst.components.aom_attachment_store
  w.block.OnLoad(other,saved);self.assertEqual(other._block.done,1)
  other._attachment_type='seeder';other.x=100;other.z=100
  self.assertEqual(w.drive.WorkHere(other),(False,'NEXT_TILE'));self.assertEqual(other._block.done,1)
  self.assertEqual(w.sow_all(other,c),c.total)
 def test_season_change_pauses_instead_of_replacing_plan(self):
  w=self.w;c=w.combo('autumn-01-02');inst=w.make(as_dict(c.ratio));w.bind(inst,c);w.prepare(inst)
  w.lua.globals().TheWorld.state.season='winter';inst._attachment_type='seeder'
  self.assertEqual(w.drive.WorkHere(inst),(False,'SEASON_CHANGED'));self.assertEqual(inst._block.combo_id,c.id)
 def test_foreign_crop_in_reserved_space_blocks_sowing(self):
  w=self.w;c=w.combo('autumn-01-02');inst=w.make(as_dict(c.ratio));w.bind(inst,c);w.prepare(inst)
  blank=next(p for _,p in w.block.WorldSlots(inst._block)[0].items() if not p.crop)
  weed=w.lua.globals().SpawnPrefab('weed_firenettle');weed.Transform.SetPosition(weed.Transform,blank.x,0,blank.z)
  inst._attachment_type='seeder';self.assertEqual(w.drive.WorkHere(inst),(False,'FOREIGN_CROP'))
 def test_full_multi_tile_and_hexagonal_workflows(self):
  w=self.w
  for ident in ['autumn-10-02','winter-01-02','summer-05-01','spring-16-01']:
   with self.subTest(ident=ident):
    w.lua.globals().reset_world();c=w.combo(ident);inst=w.make(as_dict(c.ratio),ident.split('-')[0]);w.bind(inst,c);w.prepare(inst)
    self.assertEqual(w.sow_all(inst,c),c.total)
    self.assertEqual(w.lua.globals().crop_count(),c.total)
 def test_other_mod_nutrient_changes_disable_unsafe_layout(self):
  w=self.w;c=w.combo('autumn-01-02')
  w.lua.globals().DEFS.tomato.nutrient_consumption[1]=3
  self.assertFalse(w.block.ValidateCombo(c,'autumn')[0])
 def test_old_count_only_save_is_not_migrated_to_new_map(self):
  w=self.w;inst=w.make({});w.block.OnLoad(inst,w.lua.table_from({'combo_name':'old','done':8}));self.assertIsNone(inst._block)
 def test_missing_mound_does_not_consume_a_seed(self):
  w=self.w;c=w.combo('autumn-01-02');inst=w.make(as_dict(c.ratio));w.bind(inst,c);inst._attachment_type='seeder'
  self.assertEqual(w.drive.WorkHere(inst),(False,'NEED_PLOW'));self.assertEqual(inst._block.done,0)
 def test_initial_nutrients_are_checked_before_first_seed(self):
  w=self.w;c=w.combo('autumn-01-02');inst=w.make(as_dict(c.ratio));w.bind(inst,c);w.prepare(inst)
  w.lua.execute('TheWorld.components.farming_manager.GetTileNutrients=function()return 0,0,0 end')
  inst._attachment_type='seeder'
  self.assertEqual(w.drive.WorkHere(inst),(False,'LOW_NUTRIENTS'));self.assertEqual(inst._block.done,0)
 def test_occupied_mound_reports_blockage_instead_of_skipping(self):
  w=self.w;c=w.combo('autumn-01-02');inst=w.make(as_dict(c.ratio));w.bind(inst,c)
  w.lua.execute('TheWorld.Map.CanTillSoilAtPoint=function()return false end')
  self.assertEqual(w.drive.WorkHere(inst),(False,'BLOCKED_MOUND',False));self.assertEqual(inst._block.done,0)
 def test_harvested_completed_field_can_be_prepared_for_next_batch(self):
  w=self.w;c=w.combo('autumn-01-02');inst=w.make({'tomato':8,'potato':8});w.bind(inst,c);w.prepare(inst);w.sow_all(inst,c)
  w.lua.execute('for _,v in ipairs(ENTITIES)do if v:HasTag("farm_plant")then v:Remove()end end')
  inst._attachment_type='plow';inst.x=0;inst.z=0
  self.assertTrue(w.drive.WorkHere(inst));self.assertEqual(inst._block.done,0)
 def test_missing_planted_crop_pauses_without_sowing_replacement(self):
  w=self.w;c=w.combo('autumn-01-02');inst=w.make(as_dict(c.ratio));w.bind(inst,c);w.prepare(inst);inst._attachment_type='seeder'
  w.drive.WorkHere(inst)
  w.lua.execute('for _,v in ipairs(ENTITIES)do if v:HasTag("farm_plant")then v:Remove()end end')
  self.assertEqual(w.drive.WorkHere(inst),(False,'PLANT_MISSING'));self.assertEqual(inst._block.done,1)
 def test_actual_mound_positions_are_checked_for_family_distance(self):
  w=self.w;c=w.combo('winter-01-01');inst=w.make(as_dict(c.ratio),'winter');w.bind(inst,c);w.prepare(inst)
  slots=[p for _,p in w.block.WorldSlots(inst._block)[0].items() if p.crop]
  shifted=None
  for p in slots:
   for dx,dz in [(0.15,0),(-0.15,0),(0,.15),(0,-.15)]:
    pts=[(q.x+(dx if q.index==p.index else 0),q.z+(dz if q.index==p.index else 0),q.crop)for q in slots]
    if any(sum(crop==c2 and (x-a)**2+(z-b)**2<=16 for a,b,c2 in pts)<4 for x,z,crop in pts):shifted=(p,dx,dz);break
   if shifted:break
  self.assertIsNotNone(shifted)
  p,dx,dz=shifted
  soil=w.block.FindSoilAt(p.x,p.z);soil.Transform.SetPosition(soil.Transform,p.x+dx,0,p.z+dz)
  inst._attachment_type='seeder'
  self.assertEqual(w.drive.WorkHere(inst),(False,'NO_FAMILY'));self.assertEqual(inst._block.done,0)

if __name__=='__main__':unittest.main()
