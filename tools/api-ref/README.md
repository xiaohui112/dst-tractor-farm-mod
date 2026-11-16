# 原版源码参考与测试输入

本目录用于`tools/tests`执行原版组件及选取的源码片段，**不参与Mod运行，不进入Tractor.zip**。运行实现位于`mod/Tractor`，当前验证结论见[版本测试报告](../../docs/03-版本测试报告与Bug修复.md)。

## 内容与用途

| 参考范围 | 代表文件 | 回归用途 |
|---|---|---|
| 农田与坑位 | terraformer、farmtiller、farm_soil、till_map | 铺地、原版邻坑破坏、土坑标签 |
| 腐烂与残株 | crop_remains | 本机r762172的farm_plants腐烂标记、MakePickable、SetupLoot、OnPicked、DIG与Growable阶段读取原文；验证采收/清理分工及真实产物 |
| 原版农业 | farming_manager、farmplantable、fertilizer、workable、pickable | 实时水肥、种植、DIG、采摘及真实掉落 |
| 库存与保存 | container、inventoryitem、stackable、finiteuses、entity_persistence | 归属、叠堆、用量及组件加载顺序 |
| 骑乘与承伤 | rider、rideable、riding_actions、health、combat、mount_timeline、ivy_defense | 上下车、骑乘状态、伤害例外、残骸及上车叫声帧及原版护田/根须回调 |
| 原版控件 | widget_badge/button/imagebutton/uianim/nineslice、widget_scale | 仪表、按钮及GetLooseScale数值多返回值契约 |
| 照料与交互 | farmplanttendable、farm_plant_tending、playeractionpicker、watersource | 植物安抚、鼠标动作与池塘取水 |
| 人物头顶反馈 | action_speech、bufferedaction | 本机r762172的GetActionFailString/OnActionFailed片段；原版失败原因传播、角色文案及talker调用 |
| 物品栏融合 | inventory_container | 本机r762172的PlayerHUD容器父节点选择及Inventorybar重建保留片段；验证单排货仓随背包布局保留 |
| 鼠标持有物品 | active_item | 本机r762172的Inventory.GetActiveItem；图标维修由服务端活动物品决定材料，不接收客户端物品参数 |
| 驾驶喊话定位 | speech_anchor | 本机r762172的GetTalkerOffset及FollowText.OnUpdate/SetOffset/SetScreenOffset/GetScreenOffset；复现骑乘偏移放大、头部跟随及上下车恢复 |

既有文件来源包含公开游戏脚本镜像及本机Steam的scripts.zip摘录，不应声称全部来自同一来源。准确来源、导出包装和版本依据查看各文件头及`native_ui_contract.json`；控件契约记录对应SHA。原逐轮来源说明见[历史记录](../../docs/history/2026-11-12-文档重整前/auxiliary/tools/api-ref/README.md)。

## 使用和更新规则

测试应尽量调用实际原版方法，以可观察引擎桩补齐Entity/Map/Network等底层；不能为了让布局测试通过而把CollapseSoilAtPoint替换为空实现。完整布局回归执行`till_map.lua`的原版邻坑破坏；具体布局数量以当前测试生成器及执行记录为准，不沿用旧版本固定套数。

更新参考源码时同时检查文件头、契约hash及测试接口；若从实际游戏提取，保留来源说明。缺少Lua依赖、游戏路径或发布检查跳过必须作为失败处理，不能据此写“兼容通过”。

执行真实组件仍不等于真实引擎：动画画面、输入分发、网络复制、听感和其他Mod组合，需要另做实机验收。目录中的旧源码也不是“未来游戏版本一定兼容”的保证。
