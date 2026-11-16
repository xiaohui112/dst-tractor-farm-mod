-- 只适配输入地图/实体/物料仓。规划及验证全部调用 Mod 原始模块。
package.path=MOD_SCRIPTS..'/?.lua;'..package.path
TUNING=NATIVE_CONSTANTS
WORLD_TILES={FARMING_SOIL=1}
FRAMES=1/30
function GetFarmTillSpacing()return TUNING.FARM_TILL_SPACING end
function Class(ctor)
 local c={};c.__index=c
 return setmetatable(c,{__call=function(cls,...)
  local instance=setmetatable({},cls);ctor(instance,...);return instance
 end})
end
-- 原版作物文件中与本页无关的生长/美术字段使用占位常量；同族/坑距常量均来自原版 tuning。
local environment=setmetatable({TUNING=setmetatable({}, {__index=function(_,key)return NATIVE_CONSTANTS[key] or 1 end}),FRAMES=1/30},{__index=_G})
local native=assert(loadstring(NATIVE_SOURCE));setfenv(native,environment)
local defs=native().PLANT_DEFS
package.preload['prefabs/farm_plant_defs']=function()return {PLANT_DEFS=defs}end
local function Key(x,z)return string.format('%.3f:%.3f',x,z)end
local Grid=require('aom_farm_grid')
local scene={}
TheWorld={state={season=INPUT.season},components={},Map={}}
for _,tile in ipairs(INPUT.tiles) do
 local cx,cz=tile[1]*4,tile[2]*4;local entities={};scene[Key(cx,cz)]=entities
 for row=0,2 do for col=0,2 do
  local x,z=PY_F32(cx+(col-1)*Grid.SPACING),PY_F32(cz+(row-1)*Grid.SPACING)
  local soil={prefab='farm_soil',components={}}
  function soil:IsValid()return true end
  function soil:HasTag(tag)return tag=='soil' end
  soil.Transform={GetWorldPosition=function()return x,0,z end}
  entities[#entities+1]=soil
 end end
end
TheSim={FindEntities=function(_,x,y,z,r,must,exclude)
 local out={};local radius=PY_F32(r);local r2=PY_RADIUS_SQ(r)
 local cx,cz=math.floor((x+2)/4)*4,math.floor((z+2)/4)*4
 local reach=math.ceil(radius/4)+1
 for dx=-reach,reach do for dz=-reach,reach do
  for _,v in ipairs(scene[Key(cx+dx*4,cz+dz*4)]or {})do
   local px,py,pz=v.Transform:GetWorldPosition()
   local ok=PY_DISTANCE_SQ(x,y,z,px,py,pz)<=r2
   for _,tag in ipairs(must or {})do if not v:HasTag(tag)then ok=false end end
   for _,tag in ipairs(exclude or {})do if v:HasTag(tag)then ok=false end end
   if ok then out[#out+1]=v end
  end
 end end
 return out
end}
function TheWorld.Map:GetTileAtPoint(x,_,z)return scene[Key(x,z)] and WORLD_TILES.FARMING_SOIL or 0 end
function TheWorld.Map:IsPassableAtPoint(x,_,z)return scene[Key(x,z)]~=nil end
function TheWorld.Map:GetEntitiesOnTileAtPoint(x,_,z)return scene[Key(x,z)] or {} end
function TheWorld.Map:GetTileCenterPoint(x,_,z)return math.floor((x+2)/4)*4,0,math.floor((z+2)/4)*4 end
-- 使用真正的挂件物料仓统计和种子识别代码，只有实体/容器访问为场景适配。
local container={numslots=15,slots={}}
function container:GetItemInSlot(slot)return self.slots[slot]end
for _,crop in ipairs(INPUT.crop_order) do
 local count=INPUT.seeds[crop] or 0
 if count>0 then
  local item={components={farmplantable={plant='farm_plant_'..crop}}}
  function item:IsValid()return true end
  item.components.stackable={StackSize=function()return count end}
  container.slots[#container.slots+1]=item
 end
end
local inst={components={},_seed_strategy=INPUT.strategy or 'GIANT',_aom_template_id=INPUT.template_id}
inst.components.aom_attachment_store=require('components/aom_attachment_store')(inst)
inst.components.aom_attachment_store:SetMaterialContainer(container)
local Dynamic=require('aom_dynamic_farm')
local Layout=require('aom_seed_layout')
local Packing=require('aom_seed_packing')
-- 这些包装仅报告进度；参数及所有返回值原样转交，不改变算法或预算。
local function Report(module,name,label)
 local original=module[name]
 module[name]=function(...)PY_PHASE(label);return original(...)end
end
Report(Layout,'Allocate','正在分析应季库存')
Report(Layout,'Regularize','正在整理整片排列')
Report(Packing,'Balanced','正在求解最大合法播种量')
Report(require('aom_seed_exact'),'Maximize','正在证明最大合法播种量')
local ticks=0
Dynamic._yield=function()
 ticks=ticks+1
 if ticks%16==0 and PY_CANCELLED() then error('__VERIFIER_CANCELLED__',0) end
end
PY_PHASE('正在扫描连通农田')
local plan,reason=Dynamic.Build(inst,INPUT.start[1]*4,INPUT.start[2]*4)
local valid,total=false,0
if plan then valid,total=Dynamic.Validate(plan,Dynamic._yield) end
Dynamic._yield=nil
return {plan=plan,reason=reason,valid=valid,total=total,defs=defs,ticks=ticks,construction=inst._aom_planning_task.last_report,catalog=require('aom_seed_catalog')}
