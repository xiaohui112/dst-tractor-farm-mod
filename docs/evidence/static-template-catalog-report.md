# 静态模版目录接入与回归报告

日期：2026-11-16。范围为当前Mod源码和网页，不是新版本发布、安装包或DST实机生长/FPS/多人验收。modinfo仍为0.5.18，本轮未改写Tractor.zip或本机Steam安装。

## 目录及转录

[逐格目录](../template-catalog/README.md)、[转录核对记录](../template-catalog/REVIEW.md)、[唯一目录源码](../template-catalog/catalog.json)保存36个四季原图条目及2个独立18株程序方案。28项原图九宫格与2项18株启用；7项错位及1项含非巨大化作物的示例禁用。五张原图及其SHA-256保留在目录和坐标夹具中。18株不冒充截图；spring-12和spring-15原图重复仍分别登记；两组双地皮16株与一组四地皮32株不按库存合并。

每条布局只有角色格子这一份几何定义，`_`为必要空坑。构建器自动统计库存和每地皮组成，展开每个角色的明确OR、求原版适宜季节交集，预生成去重的旋转/镜像及角色坑位。一个角色只选一种作物，不因养分相同扩大替换范围。

本轮直接查看原图并逐格放大核对；这不代表用户已经人工签收。autumn-09精确为CAAAAC/CBBBBC/CC__CC；spring-02的作物朝向与autumn-01相反。autumn-10的32株番茄＋土豆/茄子按原图留四角，模版策略采用完整目录定义；最优策略原有通用4＋4中心空坑规则未改。

## 运行职责及约束

- `aom_seed_catalog.lua`是构建产物，运行时直接require；不在游戏中展开原图OR和几何变换。
- `aom_seed_template_data.lua`无任务状态，提供静态候选、实际坑位筛选、完整模版逐坑重建验收。相同矩形的真实坑距几何及同布局/规则的检查在本次任务中复用。
- `aom_seed_templates.lua`有自己的整块选配，最多120000次候选比较、48轮构造与64轮整块替换。内部坑位不变。全田候选先比株数，再比留空集中、整齐及固定编号/方向/位置。不固定小模版优先。同一全田候选复用评分。
- `aom_seed_packing.lua`继续独立进行最大数量证明和固定数量排列优化。`aom_seed_initial.lua`保留原有通用几何初始构造，另外用共享静态候选独立构造更好的合法下界；不调用模版策略入口，不把失败当作无解，不以截止时间交付少播结果。目录变化仍可能改变下界和搜索耗时。
- 结果与计时位于设备本轮`_aom_planning_task`，模版不借用最优模块的`last_report`。缓存区分策略、目录版本、锁定编号、库存、季节、原版规则和真实坐标；换起点命中时重建本轮地皮索引。
- 模版存档保存编号、世界原点、方向和角色选择，加载时逐坑复核。缺少完整模块记录的旧模版计划丢弃后重新规划，不消耗种子；旧GIANT最优存档继续兼容。

网页继续经`lua_bridge.lua`调用Mod。新增锁定编号；显示并导出实际模版编号、原点、方向和角色作物。元数据和源码指纹包含新增Lua文件。[网页验收截图](static-catalog-web-square.png)保存autumn-10四角留空的实际结果。本机新服务地址为http://127.0.0.1:8879/。

## 三层验证及数量回归

1. 转录层：五张来源图、逐项分类和格子表，见目录核对记录。
2. 执行层：[336组坐标夹具](../template-catalog/coordinate-fixtures.json)覆盖全部启用条目的作物选择及去重方向。真实Lua逐坑比对，并用独立坐标变换公式反查原始格子；删除指定作物或填错角色不能作为完整块通过。
3. 合法性层：构建器和独立Python检查按当前原版定义验证库存、季节、逐地皮零净养分、同族距离、真实坑距与密度；真实Mod仍最终复验。变形后的实际坑距冲突不能只凭标准坐标放行。

最终源码两种策略各1162例均完成：模版0非法，最优0非法/0中断，最优播种数量与0.5.18逐例相同。严格目录与旧版自由替换不同：模版56例较少、2例更多，其余不变，未宣称模板结果是全田最大。相同库存下锁定spring-11得到两个16株块，锁定spring-12得到一个32株块。

扩展矩阵264例为四季×1/2/3/5/7/8边长×4/10/20/40/99库存×两种策略，另含缺角/L形/环形。模版132/132完成；最优118/132完成，其余14例仍在30秒测试墙钟上限内未完成证明。与0.5.18是完全相同的14例，没有新增或解决超时；双方完成的最优案例播种数量逐例一致。测试截止不进入游戏算法，不把未完成计为通过。

## 计时

以下为最终1162例单进程CPU秒统计；数量阶段与排列/校验阶段分开。多进程回归及机器负载影响实际速度，不外推到游戏等待或FPS。

| 策略 | 数量CPU中位数 | 数量CPU P95 | 数量CPU最大 | 排列/校验CPU中位数 |
|---|---:|---:|---:|---:|
| 最优 | 0.0129 | 1.4130 | 24.8102 | 0.0380 |
| 模版 | 0.0125 | 0.0908 | 0.8520 | 0.0002 |

缓存优化前后1162例模版逐坑结果完全一致；数量CPU中位数约0.0284→0.0125秒。此处是不同轮本机观察，不是严格受控性能实验。0.5.18旧自由替换模式中位数约0.0032秒；当前严格目录选配没有取得对旧模式的全面提速，增加的完整全田比较有开销。已消除运行时重复展开、同矩形重复建几何、重复全田评分，并保留相同完整输入的结果缓存。

仍未在30秒内完成的最优矩阵用例：

| 用例 | 中断时目标 | 数量阶段已用CPU秒 |
|---|---:|---:|
| autumn/square-3/all-40/GIANT | 81 | 29.493 |
| autumn/square-5/all-20/GIANT | 170 | 29.085 |
| autumn/square-7/all-20/GIANT | 170 | 28.786 |
| autumn/square-8/all-20/GIANT | 170 | 28.494 |
| autumn/ring-7/all-40/GIANT | 216 | 26.446 |
| spring/square-3/all-10/GIANT | 81 | 28.802 |
| spring/square-3/all-20/GIANT | 81 | 29.052 |
| spring/square-5/all-10/GIANT | 100 | 29.373 |
| spring/square-7/all-10/GIANT | 100 | 29.764 |
| spring/square-8/all-10/GIANT | 100 | 29.658 |
| summer/square-3/all-10/GIANT | 80 | 29.242 |
| summer/square-5/all-20/GIANT | 160 | 29.330 |
| summer/square-7/all-20/GIANT | 160 | 29.261 |
| summer/square-8/all-20/GIANT | 160 | 29.366 |

## 行为、网页与证据口径

完整自检18类检查通过，672项行为通过、0失败/警告/跳过。该完整自检在最后任务内缓存优化前启动；最终源码另以20项定向Lua行为、336组坐标、两种各1162例和264例矩阵、最终语法/模块/局部函数/源码指纹检查覆盖缓存改动。没有把早期完整自检报告说成最终源码逐文件签名。

网页完整18项测试通过（含最优76组、模版64组逐坑一致）；最终缓存源码又通过4项目录/锁定测试，9项图标测试通过。浏览器实际操作了16株锁定、32株锁定、库存和田形修改，最终32株截图使用最终缓存源码重生成。未重启或操作DST客户端。

- [最优1162例及源码SHA](static-catalog-optimal-all.json.gz)、[计时CSV](static-catalog-optimal-all.timings.csv)、[旧版数量对比](static-catalog-optimal-comparison.json)。
- [模版1162例及源码SHA](static-catalog-template-all.json.gz)、[计时CSV](static-catalog-template-all.timings.csv)、[旧版数量变化](static-catalog-template-comparison.json)。
- [264例矩阵及中断状态](static-catalog-matrix.json.gz)、[计时CSV](static-catalog-matrix.timings.csv)、[矩阵对比](static-catalog-matrix-comparison.json)。
- [完整自检](static-catalog-selfcheck.json)、[最终静态检查](static-catalog-final-static.json)、[网页/定向/坐标验证及最终来源](static-catalog-web-validation.json)。

复现：

```sh
PYTHONPATH=/tmp/pylua python3 tools/build_seed_catalog.py --check
PYTHONPATH=/tmp/pylua python3 tools/selfcheck.py --release
PYTHONPATH=/tmp/pylua python3 tools/seed_strategy_audit.py --suite all --jobs 3 --case-seconds 60 --output outputs/catalog-optimal.json
PYTHONPATH=/tmp/pylua python3 tools/seed_strategy_matrix.py --suite template-all --jobs 2 --case-seconds 30 --output outputs/catalog-template.json
PYTHONPATH=/tmp/pylua python3 tools/seed_strategy_matrix.py --suite matrix --jobs 4 --case-seconds 30 --output outputs/catalog-matrix.json
PYTHONPATH=/tmp/pylua python3 -m unittest discover -s web/giant-seed-verifier/tests
```
