-- 执行原版 Pickable/Workable 和巨大产物掉落回调；实体、库存及地图底层为桩。
local Pickable=dofile(REF..'/pickable.lua')
local Giant=dofile(REF..'/oversized_harvest.lua')
EntityScript={is_instance=function(v)return type(v)=='table' and v.Transform~=nil end}
EQUIPSLOTS={HANDS='hands'}
local base_spawn=SpawnPrefab
function attach_loot(v,loot)
 v.components.lootdropper={loot=loot}
 local d=v.components.lootdropper
 function d:GenerateLoot()
  local result={};for i,name in ipairs(self.loot)do result[i]=name end;return result
 end
 function d:SpawnLootPrefab(name)
  local item=SpawnPrefab(name);item.Transform:SetPosition(v.Transform:GetWorldPosition());return item
 end
 function d:DropLoot()
  for _,name in ipairs(self.loot)do self:SpawnLootPrefab(name)end
 end
end
function giant(crop,x,z,suffix)
 local v=CreateEntity();v.prefab=crop..'_oversized'..(suffix or '')
 v.tags.oversized_veggie=true;v.tags.heavy=true
 v.Transform:SetPosition(x or 0,0,z or 0)
 v.components.inventoryitem={owner=nil}
 v:AddComponent('workable')
 v.components.workable:SetWorkAction(ACTIONS.HAMMER)
 v.components.workable:SetWorkLeft(1)
 v.components.workable:SetOnFinishCallback(Giant.Finish)
 attach_loot(v,suffix=='_rotten' and {'spoiled_food'} or Giant.MakeLoot(v,crop))
 return v
end
function SpawnPrefab(name)
 for crop in pairs(DEFS)do
  if name==crop..'_oversized' then return giant(crop)end
 end
 return base_spawn(name)
end
function crop(cropname,x,z,oversized)
 local v=CreateEntity();v.prefab='farm_plant_'..cropname
 v.tags.farm_plant=true;v.components.farmplantstress={}
 v.Transform:SetPosition(x or 0,0,z or 0)
 v.components.pickable=Pickable(v)
 v.components.pickable:SetUp(nil)
 v.components.pickable.use_lootdropper_for_product=true
 v.components.pickable.remove_when_picked=true
 attach_loot(v,oversized and {cropname..'_oversized'} or {cropname,cropname..'_seeds'})
 return v
end
function start_harvester()
 inst=make_flow_inst({},'autumn');inst._attachment_type='harvester';inst._working=true
 inst.components.container.slots[1]=SpawnPrefab('aom_harvester')
 function inst:DoPeriodicTask()return {Cancel=function()end}end
 return inst
end
function give_driver_inventory(carry_giant)
 local inv={items={},GetEquippedItem=function()return nil end}
 inst._rider.components.inventory=inv
 function inv:GiveItem(item)
  self.items[#self.items+1]=item
  if not item:HasTag('oversized_veggie') or carry_giant then
   item.components.inventoryitem.owner=inst._rider;item.tags.INLIMBO=true
  end
 end
 function inv:DropItem(item,all,randomdir,pt)
  assert(item.components.inventoryitem.owner==inst._rider)
  item.components.inventoryitem.owner=nil;item.tags.INLIMBO=nil
  item.Transform:SetPosition(pt:Get());return item
 end
 return inv
end
