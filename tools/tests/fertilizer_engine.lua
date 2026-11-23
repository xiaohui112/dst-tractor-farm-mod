-- 原版 FarmingManager / Fertilizer / FiniteUses / Stackable / Container / InventoryItem
-- 与 EntityScript 存读档真实方法；场景、网络、湿度和物理为引擎桩。
dofile(TESTS..'/irrigator_engine.lua')
package.preload.containers=function()return {}end
local Container=dofile(REF..'/container.lua')
local InventoryItem=dofile(REF..'/inventoryitem.lua')
local Stackable=dofile(REF..'/stackable.lua')
local NativeFertilizer=dofile(REF..'/fertilizer.lua')
local NativeFiniteUses=dofile(REF..'/finiteuses.lua')
Persistence=dofile(REF..'/entity_persistence.lua')
NativeDeploy=dofile(REF..'/fertilizer_deploy.lua')
BottleReturn=dofile(REF..'/fertilizer_bottle_return.lua')
Fertilizer=require('aom_fertilizer')
math.clamp=Clamp;MAXUINT=4294967295
function GetGameModeProperty()return false end
function TheWorld:PushEvent(name,data)
 if self.events[name] then self.events[name](self,data) end
end
for _,grid in ipairs(GRIDS)do
 function grid:SetDataAtPoint(x,z,n)self:SetDataAtIndex(self:GetIndex(x,z),n)end
end
for _,overlay in pairs(GRIDS[4].grid)do overlay.UpdateOverlay=function()end end
local base_create=CreateEntity
local base_spawn=SpawnPrefab
MATERIALS={}
function engine_entity()
 local e=base_create();e.children={};e.events={};e.replica={};e.persists=true
 e.SoundEmitter={KillAllSounds=function()end,PlaySound=function()end}
 e.AnimState.IsCurrentAnimation=function()return false end
 function e:AddChild(child)self.children[child]=true;child.parent=self end
 function e:RemoveChild(child)self.children[child]=nil;child.parent=nil end
 function e:RemoveFromScene()self.hidden=true end
 function e:ReturnToScene()self.hidden=false end
 function e:ListenForEvent(event,fn,source)
  source=source or self;source.events[event]=source.events[event] or {}
  source.events[event][#source.events[event]+1]={fn=fn,owner=self}
 end
 function e:RemoveEventCallback(event,fn,source)
  local list=(source or self).events[event] or {}
  for i=#list,1,-1 do if list[i].fn==fn then table.remove(list,i)end end
 end
 function e:PushEvent(event,data)
  local callbacks={};for i,cb in ipairs(self.events[event] or {})do callbacks[i]=cb end
  for _,cb in ipairs(callbacks)do cb.fn(cb.owner,data)end
  local ii=self.components.inventoryitem
  if event=='stacksizechange' and ii and ii.owner then ii.owner:PushEvent(event,data)end
 end
 function e:Remove()
  if not self.valid then return end
  local ii=self.components.inventoryitem
  if ii then ii:OnRemoveEntity() end
  self.valid=false;self:PushEvent('onremove')
 end
 function e:GetSaveRecord()
  local data,refs=Persistence.GetPersistData(self)
  return {prefab=self.prefab,data=data},refs
 end
 return e
end
function add_inventoryitem(e)
 local c=setmetatable({inst=e,cangoincontainer=true},{__index=InventoryItem})
 -- 湿度/温度/落地表现属于引擎表面；物品归属的真实方法保留。
 for _,name in ipairs({'SetLanded','InheritMoisture','SetTemperature','DiluteMoisture','DiluteTemperature'})do c[name]=function()end end
 c.GetMoisture=function()return 0 end;c.IsWet=function()return false end;c.GetTemperature=function()return nil end
 e.components.inventoryitem=c
 return c
end
function new_container(owner,slots)
 return setmetatable({inst=owner,slots={},numslots=slots or 9,acceptsstacks=true,ignorespoverflow=true,openlist={},opencount=0},{__index=Container})
end
function material(name,nutrients,count,uses,bottle)
 MATERIALS[name]={nutrients=nutrients,count=1,uses=uses,bottle=bottle,stack=count~=nil}
 local e=SpawnPrefab(name)
 if count then e.components.stackable:SetStackSize(count)end
 return e
end
function SpawnPrefab(name,...)
 local def=MATERIALS[name]
 if not def and name~='messagebottleempty' then return base_spawn(name,...)end
 local e=engine_entity();e.prefab=name;add_inventoryitem(e)
 if not def then return e end
 e.components.fertilizer=NativeFertilizer(e)
 e.components.fertilizer:SetNutrients(def.nutrients)
 if def.uses then
  e.components.finiteuses=NativeFiniteUses(e)
  e.components.finiteuses:SetMaxUses(def.uses);e.components.finiteuses:SetUses(def.uses)
 end
 if def.stack then
  e.components.stackable=setmetatable({inst=e,stacksize=1,maxsize=40},{__index=Stackable})
  e.components.stackable.SetIgnoreMaxSize=function(_,ignore)assert(not ignore)end
 end
 if def.bottle then e.components.fertilizer.onappliedfn=BottleReturn end
 return e
end
function SpawnSaveRecord(record,newents)
 local e=SpawnPrefab(record.prefab)
 Persistence.SetPersistData(e,record.data,newents or {})
 return e
end
local original_inst=inst
inst=engine_entity();inst.prefab='aom_tractor_chassis'
inst._fuel=original_inst._fuel;inst._workstatus=original_inst._workstatus
inst._workstate_net=original_inst._workstate_net;inst._rider_net=original_inst._rider_net
inst.components.finiteuses=original_inst.components.finiteuses
inst.components.container=new_container(inst)
inst.components.container.itemtestfn=function(_,item,slot)
 if slot==1 then return item.attachment_type~=nil end
 return item.attachment_type==nil and item.components.fertilizer~=nil
end
inst.components.container.slots[1]=SpawnPrefab('aom_fertilizer')
-- 独立挂点不随货物容器重载而丢失，设备存档由生命周期测试覆盖。
inst._fixture_attachment=inst.components.container.slots[1]
inst.GetAttachment=function(self)return self._fixture_attachment end
inst.components.aom_attachment_store=require('components/aom_attachment_store')(inst)
store=inst.components.aom_attachment_store;store:SetMaterialContainer(inst.components.container)
inst._attachment_type='fertilizer'
inst._fertilizeruses_net={set=function(self,v)self.v=v end,value=function(self)return self.v or 0 end}
inst._fertilizerstock_net={set=function(self,v)self.v=v end,value=function(self)return self.v or '' end}
inst:ListenForEvent('itemget',Fertilizer.Watch);inst:ListenForEvent('itemlose',Fertilizer.Watch)
inst:ListenForEvent('stacksizechange',Fertilizer.Sync)
inst:ListenForEvent('aom_load_changed',Fertilizer.Watch)
farmer=engine_entity();farmer.Transform=driver_transform(inst);farmer.components.inventory=new_container(farmer,12)
inst._rider=farmer
function set_nutrients(a,b,c,x,z)
 local tx,tz=TheWorld.Map:GetTileCoordsAtPoint(x or 0,0,z or 0)
 FM:SetTileNutrients(tx,tz,a,b,c)
end
function nutrients(x,z)return FM:GetTileNutrients(TheWorld.Map:GetTileCoordsAtPoint(x or 0,0,z or 0))end
function add_stock(item,slot)assert(inst.components.container:GiveItem(item,slot))return item end
function hold(item,slot)assert(farmer.components.inventory:GiveItem(item,slot));return item end
function count_prefab(owner,name)
 local c=owner.components.inventory or owner.components.container
 local n=0
 for _,e in pairs(c.slots)do if e.prefab==name then n=n+(e.components.stackable and e.components.stackable:StackSize() or 1)end end
 return n
end
function start_fertilizer()
 function inst:DoPeriodicTask(_,fn)return {fn=fn,Cancel=function()end}end
 Drive.SetWorking(inst,true)
end
