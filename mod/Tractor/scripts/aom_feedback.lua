-- 鼠标动作失败交给原版actionfailed；持续作业/RPC使用同一人物talker。
local L=require("aom_locale").Text
local M={}
local REASONS={
    GENERIC="操作未完成，请检查后重试。",
    INVALID_TARGET="目标已失效，请重新选择。",
    NOT_DRIVING="请先驾驶拖拉机。",
    BUSY="现在无法操作，请稍后再试。",
    TOO_FAR="距离太远，请靠近一些。",
    DESTROYED="拖拉机已损毁，请先用齿轮修理。",
    NO_ATTACHMENT="请先安装挂件",
    OCCUPIED="请先卸载当前配件",
    IN_USE="配件正由另一辆拖拉机使用。",
    BROKEN="配件已损坏，请用燧石维修后挂载",
    NO_DROP_SPACE="附近没有卸载空间，请驶到空地再试。",
    DISMOUNT_FIRST="请先下车再进行这项操作。",
    DETACH_FIRST="请先卸载配件，再用燧石维修。",
    REPAIR_FULL="已经修好了，不需要继续维修。",
    REPAIR_GEARS="拖拉机需要用齿轮修理。",
    REPAIR_FLINT="挂件需要用燧石修理。",
    NO_ACTIVE_ITEM="请先拿起要使用的物品。",
    FUEL_FULL="油箱已满，不需要继续加油。",
    WRONG_FUEL="这种物品不能作为拖拉机燃料。",
    WRONG_LOAD="请装入当前挂件需要的物料。",
    SEEDS_FULL="种袋已满！",
    FERTILIZER_FULL="肥料仓已满！",
    WATER_ITEM="需要水壶或冰块。",
    WATER_FULL="水箱已满。",
    WATER_FAILED="无法补水。",
    WATER_CAN="需要有效的水壶。",
    WATER_EMPTY="水壶已空，请先装水。",
    POND_UNAVAILABLE="池塘现在无法取水。",
    POND_TOO_FAR="请驾驶拖拉机靠近池塘。",
    REFILLING="正在补水（5秒）；移动或下车中止",
    NEED_SEEDER="请先挂载播种机并选择配比策略。",
    STORAGE_BLOCKED="现在无法打开货仓，请稍后再试。",
}
function M.Text(reason)return L(REASONS[reason] or REASONS.GENERIC)end
function M.Reason(text)
    for code,value in pairs(REASONS)do if text==L(value) then return code end end
    return "GENERIC"
end
function M.Say(player,text,duration,noanim)
    if TheWorld and TheWorld.ismastersim==false or not player
        or player.IsValid and not player:IsValid()
        or player.HasTag and (player:HasTag("playerghost") or player:HasTag("mime"))
        or player.components and player.components.health and player.components.health:IsDead() then return false end
    local talker=player.components and player.components.talker
    if not talker or type(text)~="string" or text=="" then return false end
    talker:Say(text,duration,noanim)
    return true
end
local function Register(character,action)
    character.ACTIONFAIL=character.ACTIONFAIL or {}
    local messages=character.ACTIONFAIL[action.id]
    if type(messages)~="table" then messages={};character.ACTIONFAIL[action.id]=messages end
    for reason in pairs(REASONS)do messages[reason]=M.Text(reason)end
end
function M.InstallActions(actions)
    STRINGS.CHARACTERS=STRINGS.CHARACTERS or {}
    STRINGS.CHARACTERS.GENERIC=STRINGS.CHARACTERS.GENERIC or {}
    for _,character in pairs(STRINGS.CHARACTERS)do
        for _,action in ipairs(actions)do Register(character,action)end
    end
    for _,action in ipairs(actions)do
        if not action._aom_failure_wrapped then
            local original=action.fn
            local current=action
            action.fn=function(act)
                -- 兼容其他Mod在本文件之后新增的角色文案表。
                local character=act.doer and STRINGS.CHARACTERS[string.upper(act.doer.prefab or "")]
                if character and not (character.ACTIONFAIL and character.ACTIONFAIL[current.id]) then Register(character,current)end
                local ok,reason=original(act)
                if ok then return ok end
                return false,REASONS[reason] and reason or "GENERIC"
            end
            action._aom_failure_wrapped=true
        end
    end
end
return M
