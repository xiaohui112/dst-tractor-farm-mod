"""实际原版动作选择器/BufferedAction 串联仓库与下车；验证接管范围。"""
import unittest
import test_lifecycle_flow as lifecycle


class MouseInteractionTests(unittest.TestCase):
    def setUp(self):
        engine=lifecycle.LifecycleFlowTests();engine.setUp();self.lua=engine.lua
        self.lua.execute('''
t=deploy_kit(kit,0,0,player)
assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
picker=make_mouse_picker(player)
''')

    def run_lua(self,source):self.lua.execute(source)

    def test_held_cargo_is_not_dropped_or_used_by_vehicle_clicks(self):
        self.run_lua('''
local item=SpawnPrefab('rocks');item.components.stackable:SetStackSize(5);player.active_item=item
assert(picker:GetLeftClickActions(nil,player)[1]:Do())
assert(t.components.container:IsOpenedBy(player))
assert(picker:GetLeftClickActions(nil,player)[1]:Do())
assert(not t.components.container:IsOpenedBy(player))
assert(picker:GetRightClickActions(nil,player)[1]:Do())
assert(item:IsValid() and item.components.stackable:StackSize()==5 and player.active_item==item)
assert(player.sg.current=='dismount')
''')

    def test_native_action_filters_still_block_mouse_actions(self):
        self.run_lua('''
picker.actionfilter=function()return false end
assert(#picker:GetLeftClickActions(nil,player)==0 and #picker:GetRightClickActions(nil,player)==0)
assert(not t.components.container:IsOpenedBy(player) and player.components.rider:IsRiding())
''')

    def test_right_click_pond_still_fills_instead_of_dismounting(self):
        self.run_lua('''
assert(t:AttachAttachment(nil,SpawnPrefab('aom_irrigator')))
local pond=CreateEntity();pond.prefab='pond';pond:AddTag('pond');pond.Transform:SetPosition(4,0,0)
local WaterSource=dofile(REF..'/watersource.lua');pond.components.watersource=WaterSource(pond)
function player:GetPhysicsRadius()return .5 end
function pond:GetPhysicsRadius()return 1.5 end
function pond:is_a(kind)return kind==EntityScript end
function pond:CollectActions(kind,doer,actions,right)
 assert(kind=='SCENE');SCENE_HOOKS.watersource(self,doer,actions,right)
end
local click=picker:GetRightClickActions(Vector3(4,0,0),pond)[1]
assert(click.action==ACTION_DEFS.AOM_POND_REFILL and click:Do())
assert(t.components.aom_attachment_store:GetWater()==40 and player.components.rider:IsRiding())
''')

    def test_other_targets_walking_and_other_mounts_keep_original_click_handlers(self):
        self.run_lua('''
local passed={};local probe={inst=player}
function probe:GetLeftClickActions(position,target)passed.target=target;return {'left'}end
function probe:GetRightClickActions(position,target)passed.target=target;return {'right'}end
require('aom_mouse_input').WrapPicker(probe,ACTION_DEFS.AOM_STORAGE)
local other=make_player()
assert(probe:GetLeftClickActions(nil,other)[1]=='left' and passed.target==other)
assert(probe:GetRightClickActions(nil,other)[1]=='right' and passed.target==other)
t:RemoveTag('aom_tractor')
assert(probe:GetRightClickActions(nil,player)[1]=='right')
t:AddTag('aom_tractor');player.components.rider:ActualDismount()
assert(probe:GetLeftClickActions(nil,player)[1]=='left')
assert(probe:GetRightClickActions(nil,t)[1]=='right')
''')

    def test_client_hover_actions_do_not_read_server_components(self):
        self.run_lua('''
TheWorld.ismastersim=false
local tc,pc=t.components,player.components;t.components={};player.components={}
local left=picker:GetLeftClickActions(nil,player)[1]
local right=picker:GetRightClickActions(nil,player)[1]
assert(left.action==ACTION_DEFS.AOM_STORAGE and right.action==ACTIONS.DISMOUNT)
t.components=tc;player.components=pc
''')

    def test_localized_context_labels_and_text_hint_without_extra_buttons(self):
        self.run_lua('''
GetModConfigData=function(name)if name=='LANGUAGE' then return 'en' end end
dofile(MOD..'/modmain.lua');picker=make_mouse_picker(player)
local click=picker:GetLeftClickActions(nil,player)[1]
assert(STRINGS.ACTIONS.AOM_STORAGE[click.action.strfn(click)]=='Open storage')
assert(click:Do())
assert(STRINGS.ACTIONS.AOM_STORAGE[click.action.strfn(click)]=='Close storage')
local hud=HUD(player);hud:Refresh(t)
assert(hud.storagebutton==nil and hud.dismountbutton==nil)
assert(hud.lines==nil and string.find(hud.badges.cargo:GetTooltip(),'clicking the tractor also works',1,true))
''')


if __name__=='__main__':unittest.main()
