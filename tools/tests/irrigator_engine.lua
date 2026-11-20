-- 跑完整原版 farming_manager、finiteuses、EntityScript 保存/加载方法；地图/实体是桩。
dofile(TESTS..'/landclearer_engine.lua')
TUNING.WATERINGCAN_USES=40;TUNING.WATERINGCAN_WATER_AMOUNT=25
TUNING.SOIL_MAX_MOISTURE_VALUE=100
TUNING.SOIL_MIN_DRYING_TEMP=0;TUNING.SOIL_MAX_DRYING_TEMP=100
TUNING.SOIL_MIN_TEMP_DRY_RATE=1;TUNING.SOIL_MAX_TEMP_DRY_RATE=1
TUNING.SOIL_RAIN_MOD=1;TUNING.SOIL_MOISTURE_UPDATE_TIME=5
TheWorld.state.wetness=0
function Clamp(v,a,b)return math.max(a,math.min(b,v))end
bit={lshift=function(n,b)return n*2^b end,rshift=function(n,b)return math.floor(n/2^b)end,
 band=function(n,b)if b==255 then return n%256 end;error('unexpected bit mask')end}
GRIDS={}
function DataGrid()
 local g={grid={}}
 function g:GetIndex(x,z)return x..':'..z end
 function g:GetDataAtPoint(x,z)return self.grid[self:GetIndex(x,z)]end
 function g:GetDataAtIndex(i)return self.grid[i]end
 function g:SetDataAtIndex(i,n)self.grid[i]=n end
 function g:Save()return self.grid end
 function g:Load(data)self.grid=data end
 GRIDS[#GRIDS+1]=g;return g
end
function TheWorld.Map:GetSize()return 100,100 end
TheWorld.components.worldsettingstimer={AddTimer=function()end,StopTimer=function()end,StartTimer=function()end}
TheWorld.events={}
function TheWorld:ListenForEvent(name,fn)self.events[name]=fn end
function TheWorld:DoPeriodicTask()return {Cancel=function()end}end
local old_class=Class
Class=function(ctor)
 local c=old_class(ctor);c.WatchWorldState=function()end;return c
end
package.preload['prefabs/weed_defs']=function()return {WEED_DEFS={}}end
local NativeManager=dofile(REF..'/farming_manager.lua')
FM=NativeManager(TheWorld);TheWorld.components.farming_manager=FM
Class=old_class
TheWorld.events.worldmapsetsize()
function soil(x,z,n,active)
 local key=GRIDS[2]:GetIndex(x/4,z/4)
 GRIDS[2]:SetDataAtIndex(key,n)
 GRIDS[1]:SetDataAtIndex(key,100*65536+100*256+100)
 GRIDS[4]:SetDataAtIndex(key,active~=false and {UpdateMoisture=function()end} or nil)
end
function moisture(x,z)return GRIDS[2]:GetDataAtPoint(x/4,z/4)end
for x=0,12,4 do soil(x,0,0)end
local Persistence=dofile(REF..'/entity_persistence.lua')
function IsTableEmpty(t)return next(t)==nil end
function save_water(item)return Persistence.GetPersistData(item)end
function reload_water(data)
 local item=SpawnPrefab('aom_irrigator')
 Persistence.SetPersistData(item,data,{})
 return item
end
Irrigator=require('aom_irrigator');Soil=require('aom_soil_moisture')
inst=make_flow_inst({},'autumn')
inst._rider_net={set=function()end}
tank=SpawnPrefab('aom_irrigator');inst.components.container.slots[1]=tank
inst._attachment_type='irrigator';store=inst.components.aom_attachment_store
tank.components.finiteuses:SetUses(0)
function fill(n)store:AddWater(n)end
function water_count()return store:GetWater()end
function start_water()
 inst.Transform.GetRotation=function()return 0 end
 function inst:DoPeriodicTask(period,fn)return {Cancel=function()end,fn=fn}end
 Drive.SetWorking(inst,true)
end
function watercan(n,prefab)
 local item=CreateEntity();item.prefab=prefab or 'wateringcan'
 item:AddComponent('finiteuses');item.components.finiteuses:SetUses(n)
 item.components.fillable={};return item
end
