-- 网络只传稳定原因码和参数；语言、文案不参与业务判断。
local L=require("aom_locale").Text
local PLAN_MESSAGES = {
    PLANNING="正在规划巨大化布局，请稍候",
    FARM_TOO_LARGE="连通农田超过64块，请分区播种",
    MISSING_SEEDS="配比种子不足，请补齐当前方案所需种子后按 F 继续",
    NEED_PLOW="请换开垦机，准备好全部计划地块的坑位",
    NEXT_TILE="本格已完成，请驾驶到相邻的计划地块",
    COMPLETE="本轮配比已完成；收获后请在播种面板重规划并确认下一轮",
    FOREIGN_CROP="计划区域已有其他作物或杂草，请先清理",
    PLANT_MISSING="计划中的作物缺失，请检查地块并重新规划",
    SEASON_CHANGED="季节已变化，请检查作物并重新选择播种策略",
    INVALID_LAND="计划区域无法耕种，请换一片连续空地",
    FAILED="播种失败，种子已退回，计划进度保持不变",
    LOW_NUTRIENTS="初始养分不足，请先给计划地块补肥",
    BLOCKED_MOUND="计划坑位被占用，请清理后重新作业",
    CARGO_FULL="拖拉机仓库已满，请腾出空间后按 F 继续作业",
    NO_BALANCED_COMBO="现有种子与农田无法组成互补巨大化配比，请调整种子或扩大农田",
    NO_FAMILY="现有库存和地皮未找到合适巨大化布局，请调整种子或农田范围",
}
local WORK_MESSAGES={
    IVY_THREAT="附近有成熟刺针旋花，请先换除草机清理，再收割",
    NO_FUEL="燃料不足，请加油后继续驾驶；按 F 恢复作业",
    FAILED="本格作业未完成，请检查地块后按 F 重试",
    NO_ATTACHMENT="请先安装挂件",
    BROKEN_ATTACHMENT="开垦机已损坏并卸载，请维修后重新挂载",
    BROKEN_WEEDER="除草机已损坏并卸载，请维修后重新挂载",
    BROKEN_IRRIGATOR="洒水机已损坏并卸载，请维修后重新挂载",
    BROKEN_FERTILIZER="施肥机已损坏并卸载，请维修后重新挂载",
    BROKEN_HARVESTER="收割机已损坏并卸载，请维修后重新挂载",
    BROKEN_SEEDER="播种机已损坏并卸载，请维修后重新挂载",
    BROKEN_CHASSIS="底盘耐久已耗尽，拿起齿轮点击底盘图标修理后按 F 继续",
    DESTROYED="拖拉机已损毁",
    UNCLEARABLE_WEED="本格有无法用铲子清理的杂草、残渣或枯株，已暂停除草",
    WEEDING_INCOMPLETE="本格除草尚未完成，已保留实际进度，请检查后按 F 重试",
    HARVEST_INCOMPLETE="本格收割或巨大作物拆分尚未完成，已保留实际进度，请检查后按 F 重试",
    PROTECTED_CROP="本格有作物，已保留原状；收获后再开垦",
    BLOCKED_MOUND="地块或坑位被占用，本格未完成，请清理后按 F 重试",
    CARGO_FULL="拖拉机仓库已满，请腾出空间后按 F 继续作业",
    UNCLEARABLE_DEBRIS="本格有无法用铲子清理的杂物，已停止开垦",
    CLEARING_INCOMPLETE="杂物尚未清理干净，保留坑位并停止开垦",
    CANNOT_PLOW="这块地无法铺成农田，请换可开垦地块",
    NO_WORKER="需要驾驶员执行杂物铲除",
    MOISTURE_UNAVAILABLE="无法读取原版土壤水分，已暂停洒水，请检查版本兼容",
    NUTRIENTS_UNAVAILABLE="无法读取原版农田养分，已暂停施肥",
    FERTILIZER_FAILED="本格施肥未完成，已保留实际进度，请检查后按 F 重试",
    WATER_FAILED="本格补水未能完成，已保留实际浇水进度，请检查后按 F 重试",
}
local EMPTY_MESSAGES={seeder="种子不足，请补充后按 F 继续作业",
    irrigator="水箱已空：车尾靠近池塘，右键池塘补水5秒，再按 F 继续",
    fertilizer="肥料不足，请补充后按 F 继续作业"}
WORK_MESSAGES.WORK_ERROR="作业回调异常，已保留实际进度并停工；检查日志后按 F 重试"
WORK_MESSAGES.DETACH_BLOCKED="配件已损坏，附近无空地；驶到空地后右键卸载并维修"
PLAN_MESSAGES.PLAN_OUTDATED="旧配比布局已更新，请检查已有作物，切换播种策略后重新规划"
PLAN_MESSAGES.MOUNDS_TOO_CLOSE="坑位间距不兼容当前世界，请重新规划或检查其他模组"
PLAN_MESSAGES.PLAN_PENDING="请先查看绿色配比预览，点击确认后按 F 开始"
local M={}
function M.Text(code,detail)
    if not code or code=="" then return "" end
    if code=="EMPTY" then return L(EMPTY_MESSAGES[detail] or "本格作业暂停，请检查面板提示") end
    if code=="FERTILIZER_MISSING" then
        local names={L("生长素"),L("堆肥"),L("粪肥")};local missing={}
        for i in string.gmatch(detail or "123","%d") do missing[#missing+1]=names[tonumber(i)] end
        return L("缺少可补充%s的肥料，请补料后按 F 继续",table.concat(missing,require("aom_locale").Separator()))
    end
    return L(WORK_MESSAGES[code] or PLAN_MESSAGES[code] or "本格作业暂停，请检查面板提示")
end
-- 一个网络字符串携带完整快照；只按第一个分隔符拆开，不执行数据。
function M.Read(inst)
    local payload=inst._workstate_net and inst._workstate_net:value() or ""
    if type(payload)~="string" or payload=="" then return "","" end
    local split=string.find(payload,"|",1,true)
    local code=split and string.sub(payload,1,split-1) or payload
    if not string.match(code,"^[A-Z_]+$") then return "","" end
    return code,split and string.sub(payload,split+1) or ""
end
function M.Describe(inst)
    return M.Text(M.Read(inst))
end
function M.Set(inst,code,detail)
    code,detail=code or "",detail or ""
    if inst._workstate_net then
        inst._workstate_net:set(code~="" and (detail~="" and code.."|"..detail or code) or "")
    end
    return M.Text(code,detail)
end
-- 同一原因与参数仅在变化时喊话；主动重试可force再次提示。
function M.Report(inst,code,detail,player,force)
    local previous,old_detail=M.Read(inst)
    local text=M.Set(inst,code,detail)
    if force or previous~=(code or "") or old_detail~=(detail or "") then
        require("aom_feedback").Say(player or inst._rider,text)
    end
    return text
end
return M
