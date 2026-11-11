-- 实际运行原版 Terraformer、Workable、FiniteUses、农场杂物 prefab；仅模拟地图和实体引擎。
package.preload.worldtiledefs=function()return {turf={}}end
local Terraformer=dofile(REF..'/terraformer.lua')
local Workable=dofile(REF..'/workable.lua')
local FiniteUses=dofile(REF..'/finiteuses.lua')
TheWorld.ismastersim=true
TILE_SCALE=4
TUNING.FARM_PLOW_DRILLING_DEBRIS_MIN=2
TUNING.FARM_PLOW_DRILLING_DEBRIS_MAX=4
TUNING.FARM_SOIL_DEBRIS_LOOT_CHANCE=.25
ACTIONS.CHOP={id='CHOP'};ACTIONS.MINE={id='MINE'};ACTIONS.HAMMER={id='HAMMER'}
function GetTime()return 0 end
function Asset()end
function Prefab(name,fn)return {name=name,fn=fn}end
MakeInventoryPhysics=function()end
GLOBAL=_G
local base_spawn=SpawnPrefab
NATIVE_PREFABS={};TRACE={};TILE_WRITES=0;TURF_DROPS=0;LUCK=true;LOOT_CHOICE='flint'
function HandleDugGround()TURF_DROPS=TURF_DROPS+1 end
function CreateEntity()
 local e=base_spawn('__engine_entity')
 e.entity={AddTransform=function()end,AddAnimState=function()end,AddNetwork=function()end,SetPristine=function()end}
 e.AnimState={SetBank=function()end,SetBuild=function()end,SetScale=function()end,PlayAnimation=function()end,
 OverrideSymbol=function()end,PushAnimation=function()end}
 function e:AddTag(t)self.tags[t]=true end
 function e:RemoveTag(t)self.tags[t]=nil end
 function e:Hide()self.hidden=true end
 function e:Show()self.hidden=false end
 function e:PushEvent(name,data)
  if name=='onterraform' then TRACE[#TRACE+1]='terraform_event' end
 end
 function e:DoTaskInTime()return {Cancel=function()end}end
 function e:ListenForEvent()end
 function e:GetPosition()local x,y,z=self.Transform:GetWorldPosition();return Vector3(x,y,z)end
 function e:AddComponent(name)
  local c={}
  if name=='terraformer' then c=Terraformer(self)
  elseif name=='workable' then c=Workable(self)
  elseif name=='finiteuses' then c=FiniteUses(self)
  elseif name=='lootdropper' then
   c.SpawnLootPrefab=function(_,name)
    local drop=SpawnPrefab(name)
    drop.Transform:SetPosition(e.Transform:GetWorldPosition())
    TRACE[#TRACE+1]='loot:'..name
    return drop
   end
  elseif name~='inventoryitem' and name~='inspectable' then error('unexpected component '..name)end
  self.components[name]=c
 end
 return e
end
require('aom_common').TAG={ATTACHMENT='aom_attachment',TRACTOR='aom_tractor'}
local prefab=dofile(REF..'/farm_soil_debris.lua');NATIVE_PREFABS[prefab.name]=prefab
for _,p in ipairs({dofile(SCRIPTS..'/prefabs/aom_attachments.lua')})do NATIVE_PREFABS[p.name]=p end
local native_spawn=function(name)
 local p=NATIVE_PREFABS[name]
 local e=p and p.fn() or base_spawn(name)
 e.prefab=name
 if name=='farm_soil_debris' then TRACE[#TRACE+1]='debris'
 elseif name=='farm_soil' then TRACE[#TRACE+1]='mound'
 else
  if not p then e.components.inventoryitem={};e.tags.NOBLOCK=true end
 end
 return e
end
SpawnPrefab=native_spawn
function TryLuckRoll(worker,chance,formula)
 assert(worker and worker.components and chance==.25)
 TRACE[#TRACE+1]='loot_roll'
 return LUCK
end
LuckFormulas={LootDropperChance={}}
function weighted_random_choice(weights)
 assert(weights.twigs==40 and weights.rocks==25 and weights.flint==20 and weights.nitre==10 and weights.goldnugget==5)
 return LOOT_CHOICE
end
TheWorld.components.undertile={GetTileUnderneath=function()return nil end}
function TheWorld.Map:SetTile(tx,tz,tile)
 TILES[tkey(tx*4,tz*4)]=tile;TILE_WRITES=TILE_WRITES+1;TRACE[#TRACE+1]='tile'
end
function TheWorld.Map:CanPlowAtPoint(x,y,z)return TILES[tkey(x,z)]~=-1 end
function TheWorld.Map:CanTillSoilAtPoint(x,y,z)
 if self:GetTileAtPoint(x,y,z)~=1 then return false end
 for _,v in ipairs(ENTITIES)do
  if v.valid and not (v:HasTag('NOBLOCK') or v:HasTag('FX') or v:HasTag('player') or v.components.inventoryitem)
   and (v.x-x)^2+(v.z-z)^2<.999 then return false end
 end
 return true
end
function make_flow_inst(counts,season)
 local inst=make_inst(counts,season)
 inst.ListenForEvent=function()end
 inst._aom_terraformer=nil
 local tool=NATIVE_PREFABS.aom_landclearer.fn();tool.prefab='aom_landclearer'
 inst.components.container.slots[1]=tool
 local worker=CreateEntity();worker:AddTag('player')
 worker.Transform=inst.Transform
 inst._rider=worker
 inst._seed_strategy='SEQUENTIAL'
 return inst
end
function count_entities(name)
 local n=0;for _,v in ipairs(ENTITIES)do if v.valid and v.prefab==name then n=n+1 end end;return n
end
function count_trace(name)
 local n=0;for _,v in ipairs(TRACE)do if v==name then n=n+1 end end;return n
end
function force_debris(count,positions)
 local original=math.random
 local i=0
 math.random=function(a,b)
  if a==2 and b==4 then return count end
  if a then return 1 end
  i=i+1;return positions[(i-1)%#positions+1]
 end
 return function()math.random=original end
end
