-- 引擎桩；骑乘组件、原版动作、Mod prefab 与 HUD 均执行真实 Lua。
function Class(base, ctor, props)
    if type(base) == 'function' then props=props;ctor=base;base=nil end
    local c={_ctor=ctor,_base=base};c.__index=c
    setmetatable(c,{__index=base,__call=function(cls,...)
        local values={}
        local o=setmetatable({}, {
            __index=function(t,k) local v=values[k];if v~=nil then return v end;return cls[k] end,
            __newindex=function(t,k,v)local old=values[k];values[k]=v;if props and props[k] then props[k](t,v,old) end end,
        })
        ctor(o,...);return o
    end})
    return c
end
function noop()end
function net(v)return {set=function(self,x)v=x end,value=function()return v end}end
net_float=function()return net(0)end;net_bool=function()return net(false)end
net_entity=function()return net(nil)end;net_string=function()return net('')end
function Vector3(x,y,z)return {x=x,y=y,z=z,Get=function()return x,y,z end}end
function GetTime()return 0 end
FRAMES=1/30
function GetModConfigData()return nil end
function math.clamp(v,a,b)return math.min(b,math.max(a,v))end
GLOBAL=_G;TheWorld={ismastersim=true,state={season='autumn'},Map={IsPassableAtPoint=function()return true end}};TheSim={FindEntities=function()return {} end}
TheNet={IsDedicated=function()return false end}
KEY_F=102;CONTROL_ATTACK=1;POST_FNS={}
TheInput={down={},keydown={},keyup={},IsKeyDown=function(self,k)return self.down[k]end,
    AddKeyDownHandler=function(self,k,fn)self.keydown[k]=fn end,
    AddKeyUpHandler=function(self,k,fn)self.keyup[k]=fn end}
TheFrontEnd={};PAUSED=false
function IsPaused()return PAUSED end
TUNING={};STRINGS={NAMES={},RECIPE_DESC={}};TECH={SCIENCE_ONE=1,SCIENCE_TWO=2}
ACTIONS={MOUNT={},DISMOUNT={},RUMMAGE={},HAMMER={}}
Asset=noop;MakeObstaclePhysics=noop;SetPhysicsAttacker=noop;MakeInventoryPhysics=noop
MakeInventoryFloatable=noop;MakeHauntableLaunch=noop
function Prefab(name,fn)return {name=name,fn=fn}end
function MakePlacer()return {}end
function State(t)return t end
function StateGraph(name,states,events,initial)return {states=states,initial=initial}end
local NativeFiniteUses=dofile(REF..'/finiteuses.lua')
local NativeRider=dofile(REF..'/rider.lua')
local NativeRideable=dofile(REF..'/rideable.lua')
SCENE=dofile(REF..'/riding_actions.lua')
package.path=SCRIPTS..'/?.lua;'..package.path
-- 骑乘不涉及规划器与农业引擎；作业封装仍加载真实模块。
package.preload['prefabs/farm_plant_defs']=function()return {PLANT_DEFS={}}end
function CreateEntity()
    local e={components={},replica={},tags={},events={},valid=true,x=0,y=0,z=0}
    function e:IsValid()return self.valid end
    function e:AddTag(k)self.tags[k]=true end
    function e:RemoveTag(k)self.tags[k]=nil end
    function e:HasTag(k)return self.tags[k] or false end
    function e:ListenForEvent(k,fn,source)
        source=source or self;source.events[k]=source.events[k] or {}
        table.insert(source.events[k],{owner=self,fn=fn})
    end
    function e:RemoveEventCallback(k,fn,source)
        local list=(source or self).events[k] or {}
        for i=#list,1,-1 do if list[i].fn==fn then table.remove(list,i)end end
    end
    function e:PushEvent(k,data)
        for _,cb in ipairs(self.events[k] or {})do cb.fn(cb.owner,data)end
        if k=='dismount' then self.sg:GoToState('dismount')end
    end
    function e:DoPeriodicTask(period,fn)
        local task={Cancel=function(self)self.cancelled=true end,fn=fn}
        self.last_periodic=task;return task
    end
    e.DoTaskInTime=e.DoPeriodicTask
    -- 原版EntityScript静态时钟；暂停停音用例另以独立队列验证调度。
    e.DoStaticPeriodicTask=e.DoPeriodicTask
    e.entity={AddTransform=noop,AddAnimState=noop,AddSoundEmitter=noop,AddNetwork=noop,SetPristine=noop,
        owner=e,SetParent=function(_,parent)e.parent=parent and parent.owner end}
    e.Transform={SetPosition=function(_,x,y,z)e.x=x;e.y=y;e.z=z end,
        GetWorldPosition=function()
            if not e.parent then return e.x,e.y,e.z end
            local px,py,pz=e.parent.Transform:GetWorldPosition()
            local angle=0;local node=e.parent
            while node do angle=angle+(node.rotation or 0);node=node.parent end
            angle=angle*math.pi/180
            return px+e.x*math.cos(angle)+e.z*math.sin(angle),py+e.y,pz-e.x*math.sin(angle)+e.z*math.cos(angle)
        end,SetRotation=function(_,r)e.rotation=r end,
        GetRotation=function()return e.rotation or 0 end,SetSixFaced=function()e.facing_count=6 end,SetFourFaced=function()e.facing_count=4 end,
        SetScale=function(_,x,y,z)e.transform_scale={x,y,z}end,
        GetScale=function()return unpack(e.transform_scale or {1,1,1})end,SetEightFaced=function()e.facing_count=8 end}
    e.visual_builds={};e.visual_symbols={}
    e.AnimState={SetBank=function(_,name)e.bank=name end,SetBuild=function(_,name)e.build=name end,OverrideSymbol=noop,ClearOverrideSymbol=noop,HideSymbol=noop,ShowSymbol=noop,
        SetScale=function(_,x,y,z)e.anim_scale={x,y,z}end,GetScale=function()return unpack(e.anim_scale or {1,1,1})end,
        SetMultColour=function(_,r,g,b,a)e.tint={r,g,b,a}end,
        PlayAnimation=function(_,name,loop)e.animation=name;e.animation_loop=loop;e.animation_queue={} end,
        PushAnimation=function(_,name,loop)table.insert(e.animation_queue,{name=name,loop=loop})end,
        IsCurrentAnimation=function(_,name)return e.animation==name end,
        AddOverrideBuild=function(_,name)e.visual_builds[name]=true end,
        ClearOverrideBuild=function(_,name)e.visual_builds[name]=nil end}
    e.AnimState.OverrideSymbol=function(_,name,build,symbol)e.visual_symbols[name]={build=build,symbol=symbol}end
    e.AnimState.ClearOverrideSymbol=function(_,name)e.visual_symbols[name]=nil end
    e.AnimState.GetSymbolPosition=function()return 0,0,0,false end
    e.SoundEmitter={KillAllSounds=noop,KillSound=noop,PlaySound=noop};e.DynamicShadow={SetSize=noop}
    e.Physics={Teleport=function(_,x,y,z)e.Transform:SetPosition(x,y,z)end,
        SetActive=function(_,active)e.physics_active=active end}
    function e:FacePoint()end
    function e:AddChild(child)child.parent=self end
    function e:RemoveChild(child)child.parent=nil end
    function e:RemoveFromScene()self.hidden=true end
    function e:ReturnToScene()self.hidden=false end
    function e:Remove()self:PushEvent('onremove');self.valid=false end
    function e:GetSaveRecord()local data={};if self.OnSave then self:OnSave(data)end;return {prefab=self.prefab,data=data}end
    function e:SetStateGraph(name)
        local graph=dofile(SCRIPTS..'/stategraphs/'..name..'.lua')
        self.sg={current=nil,HasStateTag=function()return false end}
        function self.sg:GoToState(state)
            self.current=state
            for _,s in ipairs(graph.states)do if s.name==state and s.onenter then s.onenter(e)end end
        end
        self.sg:GoToState(graph.initial)
    end
    function e:AddComponent(name)
        local c={}
        if name=='rideable' then c=NativeRideable(self)
        elseif name=='rider' then
            self.replica.rider={SetRiding=function(_,v)e.client_riding=v end,SetMount=function(_,v)e.client_mount=v end,
                SetSaddle=noop,IsRiding=function()return e.client_riding end,GetMount=function()return e.client_mount end}
            c=NativeRider(self)
        elseif name=='health' then
            c.currenthealth=100;c.maxhealth=100
            c.SetMaxHealth=function(_,n)c.maxhealth=n;c.currenthealth=n end
            c.SetVal=function(_,n)c.currenthealth=n end
            c.IsDead=function()return self.dead or c.currenthealth<=0 end;c.GetPercent=function()return c.currenthealth/c.maxhealth end
        elseif name=='combat' then c={canattack=true,HasTarget=function()return false end}
        elseif name=='locomotor' then c.SetExternalSpeedMultiplier=noop
        elseif name=='finiteuses' then c=NativeFiniteUses(self)
        elseif name=='workable' then c.SetWorkAction=noop;c.SetWorkLeft=noop;c.SetOnFinishCallback=noop
        elseif name=='container' then
            c.WidgetSetup=noop;c.GetNumSlots=function()return 15 end;c.GetItemInSlot=function()return nil end
            c.IsOpenedBy=function()return self.opened or false end
            c.Close=function()self.opened=false end
            self.replica.container={IsOpenedBy=function()return self.opened or false end,GetItemInSlot=c.GetItemInSlot}
        elseif name=='aom_attachment_store' then c=require('components/aom_attachment_store')(self)
        elseif name~='inspectable' and name~='inventoryitem' then error('unexpected component '..name)end
        self.components[name]=c
    end
    return e
end
function SpawnPrefab(name)local e=CreateEntity();e.prefab=name;return e end
TRACTOR_PREFAB=dofile(SCRIPTS..'/prefabs/aom_tractor_chassis.lua')
function make_tractor()
    local t=TRACTOR_PREFAB.fn();t.prefab=TRACTOR_PREFAB.name;return t
end
function make_player()
    local p=CreateEntity();p:AddTag('player');p:AddComponent('health');p:AddComponent('combat');p:AddComponent('rider')
    p.components.pinnable={};p.sg={GoToState=function(self,s)self.current=s end,
        HasStateTag=function(self,s)return s=='busy' and (self.current=='mount' or self.current=='dismount')end}
    p.components.playercontroller={inst=p,IsEnabled=function()return not p.input_blocked end,
        IsControlPressed=function(self,control)return control==CONTROL_ATTACK and TheInput.down[KEY_F]end,
        OnControl=function(self,control,down)if down and control==CONTROL_ATTACK then p.attacks=(p.attacks or 0)+1 end end}
    if POST_FNS['components/playercontroller'] then POST_FNS['components/playercontroller'](p.components.playercontroller)end
    return p
end
-- 装配层与面板 RPC，客户端不提供可伪造的目标参数。
RPCS={};ACTION_HANDLERS={};SCENE_HOOKS={}
ACTION_DEFS={}
function AddAction(id,label,fn)local a={id=id,label=label,fn=fn};ACTION_DEFS[id]=a;return a end
function AddComponentAction(kind,name,fn)SCENE_HOOKS[name]=fn end
function AddModRPCHandler(ns,name,fn)RPCS[name]=fn end
function GetModRPC(ns,name)return name end
function ActionHandler(action,state)return {action=action,state=state}end
function AddStategraphActionHandler(sg,handler)table.insert(ACTION_HANDLERS,handler)end
SG_POST_FNS={}
function AddStategraphPostInit(name,fn)SG_POST_FNS[name]=fn end
function AddClassPostConstruct(path,fn)POST_FNS[path]=fn end
AddRecipe2=noop;AddDeconstructRecipe=noop;Ingredient=noop
-- 原版是 require 模块，不能用虚构的 GLOBAL.containers 掩盖加载错误。
containers=nil
package.preload.containers=function()return {params={}}end
dofile(MOD..'/modmain.lua')
MOD_RPC={aom_rpc={AOM_TOGGLE_WORK='AOM_TOGGLE_WORK',AOM_SEED_MODE='AOM_SEED_MODE'}}
function SendModRPCToServer(id,...)RPCS[id](CLIENT_PLAYER,...)end
function press_f(player)
    CLIENT_PLAYER=player;ThePlayer=player;TheInput.down[KEY_F]=true
    TheInput.keydown[KEY_F]()
    player.components.playercontroller:OnControl(CONTROL_ATTACK,true)
end
function release_f(player)
    TheInput.down[KEY_F]=false;TheInput.keyup[KEY_F]()
    player.components.playercontroller:OnControl(CONTROL_ATTACK,false)
end
dofile(MOD..'/../../tools/tests/dashboard_widgets.lua')
HUD=require('widgets/aom_hud')
