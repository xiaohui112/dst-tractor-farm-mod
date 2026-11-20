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
assert(t.components.aom_attachment_store:GetWater()==100 and t._refilling_net:value())
assert(player.components.rider:IsRiding())
local clock=GetTime;GetTime=function()return t._aom_pond_refill.started+5 end
require('aom_pond_refill').Update(t);GetTime=clock
assert(t.components.aom_attachment_store:GetWater()==400 and not t._refilling_net:value())
assert(player.components.rider:IsRiding())
''')

    def test_right_click_open_sea_only_offers_filtering_from_nearby_land(self):
        self.run_lua('''
assert(t:AttachAttachment(nil,SpawnPrefab('aom_irrigator')))
TheWorld.Map.IsOceanAtPoint=function(_,x)return x>1 end
TheWorld.Map.IsPassableAtPoint=function(_,x)return x<=1 end
function DynamicPosition(point)return {GetPosition=function()return point end}end
local function sea(x)
 local point=Vector3(x,0,0);point.is_a=function(_,class)return class==Vector3 end
 return picker:GetRightClickActions(point,nil)
end
assert(#sea(4)==0)
local action=sea(2)[1]
assert(action and action.action==ACTION_DEFS.AOM_SEA_REFILL)
assert(action:Do() and t._refilling_net:value() and #sea(2)==0)
require('aom_pond_refill').Cancel(t)
player.Transform:SetPosition(1.5,0,0)
assert(#sea(2)==0)
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
assert(hud.lines==nil and hud.badges.cargo:GetTooltip()=='Cargo: 0/15 slots'..string.char(10)..'Total items 0 (including stacks)')
''')


if __name__=='__main__':unittest.main()
