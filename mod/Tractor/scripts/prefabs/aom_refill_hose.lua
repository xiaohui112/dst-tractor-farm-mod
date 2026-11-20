-- 短时网络软管，无物理、库存与农业作用。
local assets={Asset("ANIM","anim/aom_refill_hose.zip")}
local function fn()
    local inst=CreateEntity()
    inst.entity:AddTransform();inst.entity:AddAnimState();inst.entity:AddNetwork()
    inst.AnimState:SetBank("aom_refill_hose");inst.AnimState:SetBuild("aom_refill_hose")
    inst.AnimState:PlayAnimation("idle",true)
    inst.AnimState:SetOrientation(ANIM_ORIENTATION.OnGround)
    inst:AddTag("FX");inst:AddTag("NOCLICK");inst:AddTag("NOBLOCK")
    inst.persists=false;inst.entity:SetPristine()
    if not TheWorld.ismastersim then return inst end
    inst.SetEnds=function(self,x,y,z,px,py,pz)
        local dx,dz=px-x,pz-z
        local length=math.sqrt(dx*dx+dz*dz)
        self.Transform:SetPosition((x+px)/2,(y+py)/2,(z+pz)/2)
        self.Transform:SetRotation(math.atan2(-dz,dx)*180/math.pi)
        self.AnimState:SetScale(length*150/64,1,1)
    end
    inst:DoTaskInTime(11,inst.Remove)
    return inst
end
return Prefab("aom_refill_hose",fn,assets)
