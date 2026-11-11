-- 完整 Mod 装配及原版组件链路；只模拟引擎实体、地图、网络、物理与血量表面。
-- 不提供 GLOBAL.containers，真实执行 MakePlacer、Deployable、Container、库存归属和存读档。
local C=require('containers')
function C.widgetsetup(c,prefab,data)
 local t=data or C.params[prefab]
 assert(t,'container definition missing: '..tostring(prefab))
 for k,v in pairs(t)do c[k]=v end
 c:SetNumSlots(#c.widget.slotpos)
end
function makereadonly()end
function removesetter()end
function GetGameModeProperty()return false end
function IsTableEmpty(t)return next(t)==nil end
function FunctionOrValue(v,...)return type(v)=='function' and v(...) or v end
function Vector3(x,y,z)return {x=x,y=y,z=z,Get=function()return x,y,z end}end
DEPLOYMODE={DEFAULT=1,CUSTOM=2,NONE=0}
DEPLOYSPACING={DEFAULT=1};DEPLOYSPACING_RADIUS={[1]=1}
FUELTYPE={BURNABLE='BURNABLE',NIGHTMARE='NIGHTMARE'}
ACTIONS.DIG={id='DIG'};ACTIONS.CHOP={id='CHOP'};ACTIONS.HAMMER.id='HAMMER'
ANIM_ORIENTATION={OnGround=1};TWOPI=2*math.pi;MAXUINT=4294967295
local Container=dofile(REF..'/container.lua')
local InventoryItem=dofile(REF..'/inventoryitem.lua')
local Workable=dofile(REF..'/workable.lua')
local Deployable=dofile(REF..'/deployable.lua')
local Fuel=dofile(REF..'/fuel.lua')
local Stackable=dofile(REF..'/stackable.lua')
local FarmPlantable=dofile(REF..'/farmplantable.lua')
Persistence=dofile(REF..'/entity_persistence.lua')
dofile(REF..'/prefabutil.lua')
ENTITIES={};TILES={};BLOCKS={};RECIPE_RECORDS={};REGISTRY={};GUID_COUNT=0
function center(x)return math.floor((x+2)/4)*4 end
function key(x,z)return center(x)..':'..center(z)end
TheWorld.Map={
 GetTileCenterPoint=function(_,x,y,z)return center(x),0,center(z)end,
 CanPlantAtPoint=function(_,x,y,z)return BLOCKS[key(x,z)]~=true end,
 GetEntitiesOnTileAtPoint=function(_,x,y,z)
  local out={};for _,v in ipairs(ENTITIES)do
   if v.valid and not v.hidden and key(v.x,v.z)==key(x,z)then out[#out+1]=v end
  end;return out
 end,
 GetTileAtPoint=function()return 1 end,
}
TheWorld.PushEvent=noop
TheSim={FindEntities=function(_,x,y,z,r,must,exclude)
 local out={};for _,v in ipairs(ENTITIES)do
  local ok=v.valid and not v.hidden and (v.x-x)^2+(v.z-z)^2<=r*r
  for _,tag in ipairs(must or {})do if not v:HasTag(tag)then ok=false end end
  for _,tag in ipairs(exclude or {})do if v:HasTag(tag)then ok=false end end
  if ok then out[#out+1]=v end
 end;return out
end}
local original_create=CreateEntity
local function replica()return setmetatable({},{__index=function()return noop end})end
function CreateEntity()
 local e=original_create();GUID_COUNT=GUID_COUNT+1;e.GUID=GUID_COUNT;e.persists=true
 ENTITIES[#ENTITIES+1]=e
 e.entity.SetCanSleep=noop;e.AnimState.SetLightOverride=noop;e.AnimState.SetOrientation=noop
 e.Physics.SetVel=noop
 function e:GetPosition()return Vector3(self.Transform:GetWorldPosition())end
 function e:RemoveFromScene()self.hidden=true;self.tags.INLIMBO=true end
 function e:ReturnToScene()self.hidden=false;self.tags.INLIMBO=nil end
 local original_add=e.AddComponent
 function e:AddComponent(name)
  local c
  if name=='container' then
   self.replica.container=replica();c=Container(self)
  elseif name=='inventoryitem' then
   c=setmetatable({inst=self,cangoincontainer=true,nobounce=true},{__index=InventoryItem})
   c.SetLanded=noop;c.InheritMoisture=noop;c.SetTemperature=noop
   c.DiluteMoisture=noop;c.DiluteTemperature=noop
   c.GetMoisture=function()return 0 end;c.IsWet=function()return false end;c.GetTemperature=function()return nil end
   self.replica.inventoryitem=replica()
  elseif name=='workable' then c=Workable(self)
  elseif name=='deployable' then c=Deployable(self)
  elseif name=='fuel' then c=Fuel(self)
  elseif name=='stackable' then
   c=setmetatable({inst=self,stacksize=1,maxsize=40},{__index=Stackable})
   c.SetIgnoreMaxSize=noop
  elseif name=='farmplantable' then c=FarmPlantable(self)
  elseif name=='placer' then c={}
  else original_add(self,name);c=self.components[name]end
  self.components[name]=c
  if name=='health' then
   c.maxhealth=100;c.currenthealth=100
   function c:SetMaxHealth(n)self.maxhealth=n end
   function c:SetVal(n)
    local before=self.currenthealth;self.currenthealth=n
    if before>0 and n<=0 then e.dead=true;e:PushEvent('death')end
   end
   function c:IsDead()return self.currenthealth<=0 end
   function c:GetPercent()return self.currenthealth/self.maxhealth end
   function c:OnSave()return {health=self.currenthealth}end
   function c:OnLoad(data)self:SetVal(data.health)end
  end
  return c
 end
 function e:GetSaveRecord()
  local data,refs=Persistence.GetPersistData(self)
  return {prefab=self.prefab,data=data},refs
 end
 local remove=e.Remove
 function e:Remove()
  if not self.valid then return end
  if self.components.inventoryitem then self.components.inventoryitem:OnRemoveEntity()end
  remove(self)
  for _,child in ipairs(ENTITIES)do if child.valid and child.parent==self then child:Remove()end end
 end
 return e
end
local function register(...)
 for _,p in ipairs({...})do if p and p.name then REGISTRY[p.name]=p end end
end
register(dofile(SCRIPTS..'/prefabs/aom_tractor_chassis.lua'))
register(dofile(SCRIPTS..'/prefabs/aom_attachments.lua'))
function SpawnPrefab(name)
 local def=REGISTRY[name]
 local e=def and def.fn() or CreateEntity();e.prefab=name
 if not def then
  if name=='farm_soil' then e:AddTag('soil')
  elseif string.sub(name,1,11)=='farm_plant_' then e:AddTag('farm_plant');e.components.farmplantstress={}
  else
   e:AddComponent('inventoryitem')
   if name=='charcoal' then e:AddComponent('fuel');e.components.fuel.fuelvalue=10 end
   if string.sub(name,-6)=='_seeds' then
    e:AddComponent('farmplantable');e.components.farmplantable.plant='farm_plant_'..string.sub(name,1,-7);e:AddTag('farmplantable')
   elseif name=='poop' then e.components.fertilizer={nutrients={0,0,8}};e:AddTag('fertilizer')end
   if name=='charcoal' or name=='flint' or name=='gears' or name=='poop' or string.sub(name,-6)=='_seeds' then e:AddComponent('stackable')end
  end
 end
 return e
end
function SpawnSaveRecord(record,newents)
 local e=SpawnPrefab(record.prefab)
 Persistence.SetPersistData(e,record.data,newents or {})
 Persistence.LoadPostPass(e,newents or {},record.data)
 return e
end
function AddRecipe2(name,ingredients,tech,data)RECIPE_RECORDS[name]=data end
dofile(MOD..'/modmain.lua')
function deploy_kit(kit,x,z,player)
 local ok=kit.components.deployable:Deploy(Vector3(x,0,z),player)
 if not ok then return nil end
 for i=#ENTITIES,1,-1 do local e=ENTITIES[i]
  if e.valid and e.prefab=='aom_tractor_chassis' and e.x==center(x) and e.z==center(z)then return e end
 end
end
function prompt(item,player,target)
 local actions={};SCENE_HOOKS.inventoryitem(item,player,target,actions,true);return actions
end
function clone(t)
 if type(t)~='table' then return t end
 local out={};for k,v in pairs(t)do out[k]=clone(v)end;return out
end
