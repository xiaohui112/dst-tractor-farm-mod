"""直接删除挂件后释放挂点，兼容旧失效引用并隔离旧设备事件。"""
import unittest
import test_world_equipment as world


class AttachmentRemovalTests(unittest.TestCase):
    setUp=world.WorldEquipmentTests.setUp
    run_lua=world.WorldEquipmentTests.run_lua

    def test_delete_each_working_attachment_immediately_releases_slot_and_stops(self):
        self.run_lua('''
ride()
for _,name in ipairs({'aom_landclearer','aom_seeder','aom_irrigator','aom_fertilizer','aom_weeder','aom_harvester'})do
 local item=equipment(name);assert(act(item));t:SetWorking(true)
 local task=t._worktask;assert(task and t._working)
 require('aom_attachment_animation').Success(t)
 local effects=item._aom_work_effects or {}
 item:Remove()
 -- 删除事件完成即已同步；不通过GetAttachment或定时任务触发清理。
 assert(t._aom_attachment==nil and t._attachment:value()==nil and t._atttype_net:value()=='',name)
 assert(not t._working and not t._workstatus:value() and t._worktask==nil)
 assert(t._watched_attachment==nil and t._tooluses_net:value()==0 and t._toolmax_net:value()==0)
 assert(not item._aom_visual_parent and not item._aom_parent_removed)
 for _,fx in ipairs(effects)do assert(not fx:IsValid())end
 local replacement=equipment('aom_weeder');assert(act(replacement) and t:GetAttachment()==replacement)
 replacement:Remove()
end
''')

    def test_delete_parked_attachment_then_mount_other_equipment(self):
        self.run_lua('''
local item=equipment('aom_irrigator');assert(t:AttachAttachment(nil,item))
item.components.finiteuses:SetUses(40);assert(t._water_net:value()==40)
item:Remove()
assert(t._aom_attachment==nil and t._water_net:value()==0 and t._watermax_net:value()==0)
ride();local next=equipment('aom_landclearer');assert(act(next))
assert(t:GetAttachment()==next and t._atttype_net:value()=='plow')
''')

    def test_remove_callbacks_accept_native_source_argument_and_either_order(self):
        self.run_lua('''
ride()
for _,reverse in ipairs({false,true})do
 local item=equipment('aom_irrigator');assert(act(item));t:SetWorking(true)
 require('aom_attachment_animation').Success(t);local fx=item._aom_stream;assert(fx)
 local function native_push(self,event,data)
  -- 原版先复制回调列表，参数为事件源；不依赖测试桩的监听者参数。
  local callbacks={};for _,cb in ipairs(self.events[event] or {})do callbacks[#callbacks+1]=cb.fn end
  if reverse then for i=#callbacks,1,-1 do callbacks[i](self,data)end
  else for _,fn in ipairs(callbacks)do fn(self,data)end end
 end
 item.PushEvent=native_push
 item:Remove()
 assert(t._aom_attachment==nil and t._atttype_net:value()=='' and not t._working)
 assert(not fx:IsValid() and not item._aom_effect_task)
 local next=equipment('aom_harvester');assert(act(next));next.PushEvent=native_push
 next.components.finiteuses:SetUses(17);assert(t._tooluses_net:value()==17)
 next:Remove()
end
''')

    def test_detached_old_device_removal_does_not_clear_replacement_or_watchers(self):
        self.run_lua('''
ride();local old=equipment('aom_seeder');assert(act(old));assert(t:DetachAttachment(player))
local next=equipment('aom_harvester');assert(act(next));t:SetWorking(true)
old:Remove()
assert(t:GetAttachment()==next and t._attachment:value()==next and t._atttype_net:value()=='harvester')
assert(t._working and t._watched_attachment==next)
next.components.finiteuses:SetUses(17);assert(t._tooluses_net:value()==17)
local ground=equipment('aom_landclearer');ground:Remove();assert(t:GetAttachment()==next and t._working)
''')

    def test_old_invalid_reference_recovers_at_right_click_without_update_tick(self):
        self.run_lua('''
ride();local old=equipment('aom_irrigator');assert(act(old));t:SetWorking(true)
old.valid=false -- 模拟旧实现遗留失效引用/未收到onremove事件。
local next=equipment('aom_landclearer');assert(act(next))
assert(t:GetAttachment()==next and t._atttype_net:value()=='plow' and not t._working)
assert(t._watched_attachment==next and t._water_net:value()==0)
''')

    def test_old_invalid_reference_recovers_for_server_attach_and_detach(self):
        self.run_lua('''
local old=equipment('aom_seeder');assert(t:AttachAttachment(nil,old));old.valid=false
local next=equipment('aom_weeder');assert(t:AttachAttachment(nil,next))
assert(t:GetAttachment()==next)
next.valid=false;assert(not t:DetachAttachment(nil))
assert(t._aom_attachment==nil and t._attachment:value()==nil and t._atttype_net:value()=='')
local last=equipment('aom_harvester');assert(t:AttachAttachment(nil,last))
t:Remove();assert(last:IsValid() and Mount.Owner(last)==nil and last.persists)
''')

    def test_save_and_getter_clear_old_invalid_reference_without_saving_ghost_type(self):
        self.run_lua('''
local old=equipment('aom_fertilizer');assert(t:AttachAttachment(nil,old));old.valid=false
local data={};t:OnSave(data)
assert(data.aom_attachment_record==nil and data.attachment_type==nil)
assert(t:GetAttachment()==nil and t._atttype_net:value()=='' and t._watched_attachment==nil)
local next=equipment('aom_weeder');assert(t:AttachAttachment(nil,next));next.valid=false
assert(t:GetAttachment()==nil and t._attachment:value()==nil and t._tooluses_net:value()==0)
''')

    def test_delete_vehicle_after_legacy_invalid_tool_never_touches_stale_components(self):
        self.run_lua('''
ride();local item=equipment('aom_irrigator');assert(act(item));t:SetWorking(true)
item.valid=false -- 旧版挂件已被删除，但车上仍保存引用。
item.Physics.SetActive=function()error('native crash: stale Physics reference')end
item.Transform.GetWorldPosition=function()error('native crash: stale Transform reference')end
t:Remove()
assert(not t:IsValid() and not player.components.rider:IsRiding())
assert(not t._working and t._worktask==nil and t._aom_attachment==nil)
''')

    def test_delete_vehicle_and_attachment_in_either_order_for_every_tool(self):
        self.run_lua('''
for _,driving in ipairs({false,true})do
 for _,tool_first in ipairs({false,true})do
  for _,name in ipairs({'aom_landclearer','aom_seeder','aom_irrigator','aom_fertilizer','aom_weeder','aom_harvester'})do
   t=SpawnPrefab('aom_tractor_chassis');local item=equipment(name)
   assert(t:AttachAttachment(nil,item));if driving then ride();t:SetWorking(true)end
   if tool_first then item:Remove();t:Remove()
   else t:Remove();assert(item:IsValid() and item.persists and Mount.Owner(item)==nil);item:Remove()end
   assert(not t:IsValid() and not item:IsValid() and not t._working and not t._worktask)
   assert(not player.components.rider:IsRiding())
  end
 end
end
''')


if __name__=='__main__':unittest.main()
