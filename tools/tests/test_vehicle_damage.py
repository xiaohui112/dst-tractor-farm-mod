"""执行本机原版 Health / Combat / CombatReplica / Rider 的承伤、索敌和残骸流程。"""
from pathlib import Path
import unittest
import test_lifecycle_flow as lifecycle

ROOT=Path(__file__).resolve().parents[2]


class VehicleDamageTests(unittest.TestCase):
    def setUp(self):
        engine=lifecycle.LifecycleFlowTests();engine.setUp();self.lua=engine.lua
        self.lua.execute('''
package.preload['util/sourcemodifierlist']=function()return dofile(REF..'/sourcemodifierlist.lua')end
package.preload['components/spdamageutil']=function()return dofile(REF..'/spdamageutil.lua')end
CommonHandlers={ResetHitRecoveryDelay=noop};TUNING.NONLETHAL_PERCENT=0
CanEntityBecomeCorpse=function()return false end;NotifyPlayerProgress=noop
IsRangedWeapon=function(item)return item and item:HasTag('rangedweapon')end
GetCreatureImpactSound=noop
TheNet.GetPVPEnabled=function()return false end
IsEntityDead=function(e)return e.components.health and e.components.health:IsDead()end
TheWorld.PushEvent=noop
local Health=dofile(REF..'/health.lua')
local Combat=dofile(REF..'/combat.lua')
local Replica=dofile(REF..'/combat_replica.lua')
function native_combat(e,maxhealth)
 function e:HasAnyTag(...)
  for _,tag in ipairs({...})do if self:HasTag(tag)then return true end end;return false
 end
 e.entity.IsValid=function()return e.valid end
 e.entity.IsVisible=function()return not e.hidden end
 e.IsInLimbo=function()return e.hidden end
 e.replica.health=setmetatable({},{__index=function()return noop end})
 e.replica.combat=Replica(e)
 e.components.combat=Combat(e)
 e.components.health=Health(e)
 e.components.health:SetMaxHealth(maxhealth)
 e.components.health.nofadeout=true
end
kit:Remove();t=SpawnPrefab('aom_tractor_chassis')
native_combat(t,600);t.components.combat.canattack=false
native_combat(player,150)
attacker=CreateEntity();attacker.prefab='hound';native_combat(attacker,100)
function ride()
 assert(ACTIONS.MOUNT.fn({doer=player,target=t}));player.sg:GoToState('mounted_idle')
end
function hp(e)return e.components.health.currenthealth end
''')

    def run_lua(self,s):self.lua.execute(s)

    def test_parked_vehicle_is_not_a_target_but_driver_remains_targetable(self):
        self.run_lua('''
assert(not attacker.components.combat:CanTarget(t))
assert(attacker.components.combat:CanTarget(player))
ride();assert(attacker.components.combat:CanTarget(player))
assert(not attacker.components.combat:CanTarget(t))
assert(t.components.combat.canattack==false and t:HasTag('peacefulmount'))
''')

    def test_native_melee_damage_hits_vehicle_and_stops_redirecting_after_dismount(self):
        self.run_lua('''
ride();player.components.combat:GetAttacked(attacker,40)
assert(hp(t)==560 and hp(player)==150 and t._health_net:value()==560)
player.components.rider:ActualDismount()
assert(player.components.combat.redirectdamagefn==nil)
player.components.combat:GetAttacked(attacker,40)
assert(hp(t)==560 and hp(player)==110)
''')

    def test_native_ranged_electric_darkness_and_pseudoprojectile_bypass_vehicle(self):
        self.run_lua('''
ride()
for _,stimuli in ipairs({'electric','darkness'})do
 player.components.combat:GetAttacked(attacker,10,nil,stimuli)
end
local weapon=CreateEntity();weapon.components.projectile={};weapon:AddTag('rangedweapon')
player.components.combat:GetAttacked(attacker,10,weapon)
attacker:AddTag('pseudoprojectile');player.components.combat:GetAttacked(attacker,10)
assert(hp(t)==600 and hp(player)==110)
''')

    def test_fatal_melee_leaves_persistent_wreck_cargo_and_equipment(self):
        self.run_lua('''
local tool=SpawnPrefab('aom_irrigator');assert(t:AttachAttachment(nil,tool))
assert(t.components.aom_attachment_store:AddWater(13)==13)
local cargo=SpawnPrefab('tomato_seeds');cargo.components.stackable:SetStackSize(7)
assert(t.components.container:GiveItem(cargo,1))
t:SetFuel(123);t.components.finiteuses:SetUses(456);ride()
player.components.combat:GetAttacked(attacker,600)
assert(hp(player)==150 and hp(t)==0 and not player.components.rider:IsRiding())
assert(t:IsValid() and t.persists and t._wreck_net:value() and t.animation=='death')
assert(t.tint[1]==.45 and not t.components.rideable.canride and not t._working)
assert(t.components.health.nofadeout and t.erode_task==nil)
assert(tool:IsValid() and tool.persists and require('aom_attachment_mount').Owner(tool)==nil)
assert(tool.components.finiteuses:GetUses()==113 and cargo.components.inventoryitem.owner==nil)
assert(cargo.components.stackable:StackSize()==7 and t:GetAttachment()==nil)
local saved=clone(t:GetSaveRecord());t:Remove()
local wreck=SpawnSaveRecord(saved)
assert(wreck._wreck_net:value() and wreck.persists and wreck.components.health:IsDead())
local gears=SpawnPrefab('gears');gears.components.stackable:SetStackSize(3)
assert(wreck:TryRepair(player,gears))
assert(wreck.components.health.currenthealth==200 and not wreck._wreck_net:value())
assert(wreck.components.finiteuses:GetUses()==456 and wreck._fuel:value()==123)
assert(wreck.components.container:GetItemInSlot(1)==nil and wreck:GetAttachment()==nil)
assert(gears.components.stackable:StackSize()==2 and wreck.components.rideable.canride)
assert(wreck.animation=='idle' and wreck.tint[1]==1)
assert(ACTIONS.MOUNT.fn({doer=player,target=wreck}))
''')

    def test_gears_repair_health_when_durability_full_and_stop_at_both_caps(self):
        self.run_lua('''
t.components.health:DoDelta(-50)
local gears=SpawnPrefab('gears');gears.components.stackable:SetStackSize(2)
assert(t:TryRepair(player,gears) and hp(t)==600 and t.components.finiteuses:GetUses()==1000)
assert(gears.components.stackable:StackSize()==1)
assert(not t:TryRepair(player,gears) and gears:IsValid())
''')

    def test_wreck_hammer_salvages_once_without_dropping_duplicate_cargo(self):
        self.run_lua('''
t.components.health:Kill();assert(t.persists and t.components.workable:CanBeWorked())
t.components.workable:WorkedBy(player,4);assert(not t:IsValid())
local counts={}
for _,v in ipairs(ENTITIES)do if v.valid and v.prefab then counts[v.prefab]=(counts[v.prefab] or 0)+1 end end
assert(counts.gears==1 and counts.transistor==1 and counts.boards==1 and counts.flint==2)
assert(not counts.aom_tractor_item)
''')


if __name__=='__main__':unittest.main()
