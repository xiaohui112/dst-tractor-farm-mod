# 当前验证状态与复现

本页区分最新发布验证、历史实验和待实机验收。旧Bug修复和版本优化归[开发日志](02-开发进度.md)，原始数据保留evidence；不把不同版本、规则或预算下的结果混成一次测试。

## 最新发布：0.5.23

[安装与完整自检记录](evidence/0.5.23-game-install-validation.json)记录698项Lua 5.1行为回归、18项发布检查，0失败、0警告、0跳过；98个发布文件在源码、ZIP和本机安装逐字节一致，游戏未由脚本重启，未上传GitHub。当前只重整文档，不重新生成同字节运行包。

播种耐久新增6项测试：三策略逐格计费、暂停/读档续种、顺序缺种补种、最后1点完成整格、最后一颗回调报错、失败重试与新轮。3项旧测试从每颗扣费更新为整格扣费。相关40项初测及更新后的46项通过，完整698项最终通过。见[专项测试](evidence/seeder-durability-0.5.23/专项测试.txt)、[更新预期测试](evidence/seeder-durability-0.5.23/更新预期测试.txt)和[发布输出](evidence/seeder-durability-0.5.23/发布输出.txt)。

## 几何与数量性能：0.5.22

[冻结复测报告](evidence/grid-spacing-0.5.22/结果.md)覆盖原48场景两轮，全部完成数量证明且数量无回退；新坑位测试覆盖真实开垦、225坑有效性、旧田重整、保护已有作物与正负/大坐标。网页22项、CP-SAT/浮点模型14项通过；网页中包含76组同源对照，不等于76个独立实机验收。

| 秋季输入 | 策略 | 数量 | 总墙钟中位数 | 数量CPU中位数 |
|---|---|---:|---:|---:|
| 5×5，大蒜/洋葱/辣椒各100 | 最优 | 225 | 2.930秒 | 1.411秒 |
| 5×5，九种应季各40 | 最优 | 225 | 6.242秒 | 4.881秒 |
| 7×7，九种应季各40 | 最优 | 340 | 5.078秒 | 2.336秒 |
| 7×7，九种应季各40 | 模版 | 330 | 3.683秒 | 1.833秒（准备/选配） |

最优三轮、模版一轮，最终复测同机有并发完整回归；这些是离线测量，不能称为游戏等待或首种耗时。0.5.23只改执行成本，未将这批性能重标为0.5.23的新测速。

## 历史证据使用范围

| 证据 | 用途与限制 |
|---|---|
| [0.5.13](evidence/0.5.13-seed-optimization-report.md) | 当时1162场景和分阶段计时；不是当前版本1162场景重跑 |
| [0.5.17](evidence/0.5.17-planner-optimization-report.md) | 调度、缓存与构造优化历史；其中规划日志后来已取消 |
| [0.5.18](evidence/0.5.18-strategy-report.md)、[0.5.19](evidence/0.5.19-template-capacity-report.md) | 模版/大田能力与当时慢例 |
| [CP-SAT对照](evidence/cpsat-native-float32-2026-11-16/结论.md) | 旧快照存在Lua/原版几何模型差异，不能直接比较求解器优劣 |
| [FindEntities修复](evidence/native-query-fix-2026-11-16/结果.md) | 0.5.21原版查询统一后的48场景结果 |
| [0.5.22](evidence/grid-spacing-0.5.22/结果.md) | 新坑距、当前几何和大田离线基线 |

## 复现命令与验收边界

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tools/tests -v
python3 tools/selfcheck.py --release
python3 tools/package_mod.py --verify-only
python3 tools/seed_strategy_audit.py --suite all --jobs 4 --case-seconds 30 --output outputs/seed-regression.json
```

网页独立测试在 `web/giant-seed-verifier` 运行 `python3 -m unittest discover -s tests -v`，前端作物显示运行 `node --test tests/test_crop_display.cjs`。不同Python解释器需各自安装依赖，勿复制其它平台二进制包。

测试引擎桩能验证回调、物料、存档、原版查询模拟和布局，不证明真实客户端画面/FPS、联机同步、真实引擎查询或完整生长巨大化。待验收包括重启后的新坑位、完整生长与压力、多人/专服、其他Mod兼容。数量证明继续运行不代表固定延迟承诺；回归30秒中断仅属于工具，不改变游戏策略。
