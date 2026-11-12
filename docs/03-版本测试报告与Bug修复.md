# 0.5.1 版本测试报告与Bug修复

整理日期：2026-11-12。测试对象为`mod/Tractor`的0.5.1运行实现，包含40个Lua文件；安装包为根目录Tractor.zip。本次仅重整文档，沿用上一轮对相同运行代码执行的发布自检，复核安装包和当前源码一致，不宣称重新完成了DST实机测试。

## 1. 结果与证据

| 项目 | 结果 |
|---|---|
| 发布模式 | `selfcheck.py --release`，success=true |
| 检查分类 | 17类全部passed，failures与warnings均为空 |
| 行为回归 | Lua 5.1，386项；0失败、0错误、0跳过 |
| 包文件 | 64个运行源文件，加INSTALL-MANIFEST.json |
| ZIP | CRC通过，无重复/额外/缺失条目，全部源文件与清单逐字节匹配 |
| 归档大小 | 94,641,428字节 |
| 安装包SHA-256 | `13919345afdf5550f8bc4e8807256b5b7db9bc902eb128ad5408c1aa63b93c6a` |
| 实际安装/部署 | 未自动覆盖游戏mods目录；未发布工坊 |

证据副本：[严格自检](evidence/0.5.1-selfcheck-validation.json)、[安装包校验](evidence/0.5.1-install-validation.json)、[包内运行清单](evidence/0.5.1-runtime-manifest.json)。原生成位置为`outputs/selfcheck-validation.json`、`outputs/install-validation.json`，该目录不提交；本报告保存稳定副本，避免只引用本机临时输出。

本机检查读取Steam安装内的游戏脚本，用于原版路径、组件和资源核验；没有把这种源码检查当成启动游戏的证据。报告中没有原执行时长与网络延迟测量，本文不补造。

## 2. 自动覆盖矩阵

以下数量为当前各测试文件的方法数，总计386；同一测试中还有子场景，如109套布局×4旋转，不能据此把386项换算成真实玩家场次。

| 测试文件（tools/tests） | 项数 | 重点 |
|---|---:|---|
| test_attachment_animations.py | 14 | 工作动画启停、结果FX、末份材料、客户端/专服边界 |
| test_audit_regressions.py | 13 | 全布局原版邻坑破坏、旧v2、迁移与作业异常 |
| test_dashboard.py / test_dashboard_assets.py | 12 / 2 | 原版控件、RPC、表盘、资源与只读客户端 |
| test_drive_pass.py | 15 | 持续作业、经过网格、缺料/燃料与费用 |
| test_driver_visual.py | 12 | 原版骑乘时间线、驾驶build与角色显示接口 |
| test_fertilizer_flow.py | 37 | 实时养分、选肥、次数、切换、缺料与失败 |
| test_giant_farming.py | 21 | 配比约束、坐标、保存、缺料、失败及两轮流程 |
| test_harvester_flow.py | 21 | 普通采摘、巨大产物拆分、保护及原版掉落 |
| test_install_package.py | 2 | 归档清单、源码一致性与损坏拒绝 |
| test_irrigator_flow.py | 24 | 实时水分、逐剂、雨水、返还及零油保护 |
| test_irrigator_music.py / test_music_tending.py | 12 / 9 | 运行音频、失败降级、范围与植物安抚 |
| test_landclearer_flow.py | 22 | 铺地、清理、九坑、邻坑保护及跨轮 |
| test_lifecycle_flow.py | 26 | 货仓、修理、装料、保存和迁移 |
| test_localized_names.py | 6 | 本地化和原版名称 |
| test_mouse_interaction.py | 6 | 骑乘左右键、原版动作及其他目标不受影响 |
| test_native_riding.py | 26 | 原版Rideable/Rider、骑乘状态与速度 |
| test_plan_preview.py | 7 | 预览旋转确认、库存/场地重验、权限与清理 |
| test_plough_pickup.py | 10 | 开垦拾取、叠堆、仓满及计划保留 |
| test_pond_refill.py | 11 | 水源、骑手、距离、满罐和零额外费用 |
| test_release_checks.py | 6 | 缺依赖/跳过阻断、路径、旧包保留、共享资源 |
| test_review_regressions.py | 11 | 0.5.1四个修复及原因/参数完整快照 |
| test_vehicle_damage.py | 6 | 原版近战/例外伤害、残骸及维修 |
| test_vehicle_motion.py | 8 | 四档尺寸、移动显示与发动机音频 |
| test_weeder_flow.py | 18 | DIG筛选、作物保护、掉落和未完成 |
| test_work_cargo.py | 10 | 原版库存归属、满仓、产物叠堆与存档 |
| test_world_equipment.py | 19 | 独立设备、挂卸、权限、维修和保存 |

发布检查还覆盖语法、modinfo、禁止运行目录源PNG、动画/驾驶/音乐资源、公共模块、受限环境、模块引用、游戏路径/全局、配方原料、局部函数及危险模式。

## 3. 0.5.1修复记录

| 问题 | 修复后的行为 | 回归 |
|---|---|---|
| 收获后自动重置并更换起点/方向/配比，隐式跳过确认 | GetTargets不创建/重置计划；完成索引原样保存；下一轮显式预览与确认，confirmed缺省不当成true | 远处40单位、换库存、旋转/存档保留、跨两轮种植 |
| 特效或耐久回调报错跳过收费及停机 | 底盘、配件、特效独立保护；已发生改动记账一次，扣应计燃料并停采样；清理临时归属 | 特效、两种耐久分别/同时异常、停止动画异常、重试不复制 |
| 开垦机NEXT_TILE误停而播种机继续 | 两者统一为可继续提示，区域外零消耗，驶回继续 | 两类设备区域外/返回 |
| 模板不兼容误报缺种 | 分开保留材料、模板和场地错误，失败不覆盖已有预览 | 坑距改变、地形阻挡、种子不足及失败旋转 |

维护改动：原因与参数由单个_workstate_net载荷同步，客户端通过Status.Read/Describe使用；统一驾驶层耐久检查，定义表保留纯数据；明确洒水模块边界和旧注释。本次文档重整将这些规则合入现行方案。

## 4. 已保留的0.5.0修复

- 重算109套自动布局，修复原坑距过小及跨格邻坑破坏；测试执行原版CollapseSoilAtPoint。
- 新田随机残渣避开邻格土坑，开垦收本次格边新掉落而不取邻格旧物。
- 卸载受阻的零耐久洒水/施肥设备仍禁止重开作业。
- 观察原版回调真实副作用，异常后恢复临时方法/标签并按实际进度收费；已产出的异常采摘记录picked避免复制。
- 旧打包车找不到落点时保留原库存归属、保存与重试，不提前移除或重复展开。
- 发布缺少Lua依赖、警告或跳过均拒绝打包；失败不替换旧安装包。
- 四档驾驶包共享build/贴图，原动画字节保持；此前测得减少1,918,194字节，不能用原始贴图大小夸大压缩包收益。

## 5. 原DSH复查的误判纠正

| 原主张 | 按实现核对后的结论 |
|---|---|
| 洒水/施肥不检查燃料、可扣负数 | 错误；专属模块在有缺口时检查油，ConsumeFuel拒绝不足，SetFuel钳制下限 |
| 洒水仅一剂，驾驶limit需改4 | 错误；WaterTile内部for循环已补满，外层一次代表整格，不代表一剂 |
| assets/audio没有FSB，音乐未接 | 错误；运行FEV/FSB位于mod/Tractor/sound，已有结构/事件/PCM及归档校验；实机听感仍未验收 |
| 共用dirty事件本身必然丢更新 | 未成立；原版也用组事件，共用不等于故障，拆事件也不提供跨字段原子性 |
| 原因/参数两字段必然错位 | 当时没有真实网络复现；仍采纳完整快照建议，0.5.1已单载荷 |
| 三个洒水模块重复实现 | 没有重复补满算法，分别是批次编排、单剂/网格适配、兼容转发；现已明确职责 |
| WorkTile重复、文档重复编号 | 有效维护建议；耐久检查已统一，现行文档已按主题和设备重整 |

旧逐项分析保存在[原27号记录](history/2026-11-12-文档重整前/27-复查与优化建议.md)，不再作为独立现行规范。

## 6. 未完成的验证及复跑

未完成DST客户端、真实双人/专服、其他Mod组合、大田多车长时压测。实体、渲染、网络、输入及部分地图接口存在桩；自动回归不能证明真实同步时序、最终画面、声音或性能。实机清单见[开发进度](02-开发进度.md)。

仓库根目录执行：

```sh
python3 -m pip install -r requirements-dev.txt
python3 tools/selfcheck.py --release
python3 tools/package_mod.py
python3 tools/package_mod.py --verify-only
```

package_mod内部会再次执行严格自检，成功后原子生成包并核对清单。开发者可只执行package_mod完成发布流水线；已有包仅核对用--verify-only。本机额外通过PYTHONPATH=/tmp/pylua加载Lua依赖，这是本机路径，不是其他环境的安装要求。
