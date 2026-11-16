"""超过64块的真实Mod规划、局部预览、进度与取消；最优保持原上限。"""
import unittest
from test_giant_farming import World


class TemplateCapacityTests(unittest.TestCase):
 def setUp(self):
  self.w=World();self.L=self.w.lua
  self.L.execute('''
D=require('aom_dynamic_farm');Block=require('aom_block_plan');Preview=require('aom_template_preview')
tile_entities={}
function large_field(w,h)
 for z=0,h-1 do for x=0,w-1 do
  local list={};tile_entities[tkey(x*4,z*4)]=list
  for r=-1,1 do for c=-1,1 do local soil=SpawnPrefab('farm_soil');soil.Transform:SetPosition(x*4+c*4/3,0,z*4+r*4/3);list[#list+1]=soil end end
 end end
end
TheWorld.Map.GetEntitiesOnTileAtPoint=function(_,x,y,z)
 local out={};for _,v in ipairs(tile_entities[tkey(x,z)]or {})do if v:IsValid()then out[#out+1]=v end end;return out
end
function build_large(w,h)
 large_field(w,h);inst=make_inst({tomato=w*h*4,potato=w*h*4},'autumn')
 inst._seed_strategy='GIANT_TEMPLATE';inst._attachment_type='seeder';inst._aom_template_id='autumn-01'
 local b,why=D.Build(inst,0,0);assert(b,why);inst._block=b;return b
end
''')

 def test_entire_fields_beyond_old_tile_and_plant_limits(self):
  for w,h in [(9,9),(4,24),(16,16)]:
   with self.subTest(size=(w,h)):
    self.setUp();self.L.globals().W=w;self.L.globals().H=h
    self.L.execute('''local b=build_large(W,H)
assert(#b.tiles==W*H and #b.slots==W*H*9 and b.total==W*H*8 and D.Validate(b))
assert(b.construction.attempts<=b.construction.work_budget)
inst._seed_strategy='GIANT';local rejected,why=D.Build(inst,0,0)
assert(not rejected and why=='FARM_TOO_LARGE')
''')

 def test_preview_packet_is_bounded_moves_and_preserves_real_positions(self):
  self.L.execute('''local b=build_large(4,24)
local p=b.slots[1];p.x=p.x+.05
local payload=Preview.Encode(inst,0,0);assert(#payload<=Preview.MAX_BYTES)
local view=Block.Decode(payload);assert(view and view.total==768 and #view.slots<=Preview.MAX_POINTS)
local saw=false;for _,q in ipairs(view.slots)do if math.abs(q.x-p.x)<.0001 and math.abs(q.z-p.z)<.0001 then saw=true end end;assert(saw)
inst.z=92;local far=Block.Decode(Preview.Encode(inst,0,0));assert(far and #far.slots>0)
for _,q in ipairs(far.slots)do assert(q.cz>=72)end
assert(Block.Decode(payload..'x')==nil)
assert(Block.Decode(string.rep('x',Preview.MAX_BYTES+1))==nil)
assert(Block.Decode(payload:gsub(require('aom_seed_catalog').version,'wrong'))==nil)
''')

 def test_saved_large_plan_keeps_modules_progress_and_inventory_checks(self):
  self.L.execute('''local b=build_large(9,9)
Preview.Complete(b,1);Preview.Complete(b,1);assert(b.done==1)
local data=Block.OnSave(inst);local other=make_inst({},'autumn');Block.OnLoad(other,data)
assert(other._block and #other._block.tiles==81 and other._block.done==1)
assert(D.Validate(other._block));local state=Preview.Prepare(other._block)
assert(state.remaining.tomato+state.remaining.potato==647)
local targets,why=D.Targets(other,32,32);assert(not targets and why=='MISSING_SEEDS')
''')

 def test_only_current_complete_module_is_rechecked_before_sowing(self):
  self.L.execute('''local b=build_large(9,9);local calls=0;local scan=D.Scan
D.Scan=function(...)calls=calls+1;return scan(...)end
local targets=D.Targets(inst,32,32);assert(targets and #targets==8 and calls==1)
tile_entities[tkey(32,32)][1]:Remove()
local targets,why=D.Targets(inst,32,32);assert(not targets and why=='NEED_PLOW')
''')

 def test_async_template_scan_can_cancel_before_reading_whole_field(self):
  self.L.execute('''large_field(9,9);inst=make_inst({tomato=324,potato=324},'autumn')
inst._seed_strategy='GIANT_TEMPLATE';inst._attachment_type='seeder';inst._working=true
local calls=0;local scan=D.Scan;D.Scan=function(...)calls=calls+1;return scan(...)end
local queue={};inst.DoTaskInTime=function(_,_,fn)queue[#queue+1]=fn end
D.Start(inst,0,0);assert(calls==0 and #queue==1)
D.Cancel(inst,'PLAN_RESET');table.remove(queue,1)();assert(calls==0 and not inst._block)
''')

 def test_paused_large_job_resumes_and_rechecks_changed_inventory(self):
  self.L.execute('''large_field(9,9);inst=make_inst({tomato=324,potato=324},'autumn')
inst._seed_strategy='GIANT_TEMPLATE';inst._attachment_type='seeder';inst._working=true;inst._aom_template_id='autumn-01'
local cpu=0;os.clock=function()return cpu end
local scan=D.Scan;D.Scan=function(...)cpu=cpu+.005;return scan(...)end
local queue={};inst.DoTaskInTime=function(_,delay,fn)queue[#queue+1]={delay=delay,fn=fn}end
D.Start(inst,0,0);table.remove(queue,1).fn();local job=inst._aom_dynamic_job;assert(job)
D.Cancel(inst,'WORK_STOPPED');assert(inst._aom_suspended_job==job)
local other=make_inst({tomato=320,potato=320},'autumn');inst.components.aom_attachment_store=other.components.aom_attachment_store
D.Start(inst,0,0);assert(inst._aom_dynamic_job==job)
local steps=0;while not inst._block and #queue>0 do steps=steps+1;assert(steps<20000);table.remove(queue,1).fn()end
assert(inst._block and inst._block.total==640 and #inst._block.tiles==81)
assert(inst.components.aom_attachment_store:GetSeedCount()==640 and inst._block.done==0)
''')

 def test_sparse_geometry_has_identical_edges_and_metrics(self):
  self.L.execute('''local A=require('aom_seed_layout');local tiles={{x=0,z=0},{x=4,z=0},{x=0,z=4},{x=8,z=0}}
local slots,board={},{};for _,t in ipairs(tiles)do for s=0,8 do slots[#slots+1]={x=t.x+(s%3-1)*4/3,z=t.z+(math.floor(s/3)-1)*4/3};board[#board+1]=s==4 and false or 'potato' end end
local old=A.Geometry(tiles,slots,DEFS);local sparse=A.Geometry(tiles,slots,DEFS,nil,true)
assert(#old.edges==#sparse.edges)
for i,e in ipairs(old.edges)do local f=sparse.edges[i];assert(e.a==f.a and e.b==f.b and e.horizontal==f.horizontal)end
assert(A.Metrics(board,old).tidy==A.Metrics(board,sparse).tidy)
''')


class TemplatePreviewClientTests(unittest.TestCase):
 def setUp(self):
  from test_dashboard import DashboardTests
  fixture=DashboardTests();fixture.setUp();self.L=fixture.lua

 def test_native_hud_refreshes_nearby_modules_and_completed_markers(self):
  self.L.execute('''
attach('aom_seeder');t:CycleSeedStrategy(player)
local catalog=require('aom_seed_catalog');local spec
for _,s in ipairs(catalog.templates)do if s.id=='autumn-01'then spec=s end end
local v=spec.variants[1];local recipe
for _,r in ipairs(spec.recipes)do if r.needs.potato then recipe=r end end
local slots,tiles,modules={}, {},{}
for z=0,23 do for x=0,3 do
 tiles[#tiles+1]={x=x*4,z=z*4}
 modules[#modules+1]={id=spec.id,symmetry=v.symmetry,origin={x=x*4,z=z*4},crops=recipe.map}
 for s=0,8 do slots[#slots+1]={x=x*4+(s%3-1)*4/3,z=z*4+(math.floor(s/3)-1)*4/3,cx=x*4,cz=z*4,crop=recipe.map[v.cells[s+1]]or false,index=#slots+1}end
end end
t._block={dynamic=true,strategy='GIANT_TEMPLATE',total=768,done=0,season='autumn',tiles=tiles,slots=slots,completed={},construction={modules=modules}}
local Block=require('aom_block_plan');local Preview=require('aom_template_preview')
Block.Sync(t);assert(t._plan_net:value():sub(1,3)=='D6;');hud:Refresh(t)
assert(#hud._plan_markers>0 and #hud._plan_markers<=Preview.MAX_POINTS)
local first=hud._plan_markers[1];assert(first.y==0 and first.layer==LAYER_BACKGROUND)
assert(Block.RecordPlanted(t,slots[1]));Block.Sync(t);hud:Refresh(t);assert(not first:IsValid())
local old=hud._plan_markers[1]
player.Transform:SetPosition(0,0,92);require('aom_drive').TrackTravel(t);hud:Refresh(t)
assert(not old:IsValid() and #hud._plan_markers>0)
for _,marker in ipairs(hud._plan_markers)do assert(marker.z>=72-4/3)end
local last=hud._plan_markers[1];hud:Refresh(nil);assert(not last:IsValid())
''')


if __name__=='__main__':unittest.main()
