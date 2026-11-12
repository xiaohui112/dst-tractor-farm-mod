# 原版源码参考片段

2026-11-12审查修复：配比回归不再把邻坑破坏设为空，109套布局×四种旋转实际执行`till_map.lua`中的原版CollapseSoilAtPoint，并验证相邻新田随机杂物保护。完整发布基线记录于`outputs/selfcheck-validation.json`，不等于实机验收。

2026-11-12驾驶仪表补充：`widget_badge.lua`、`widget_button.lua`、`widget_imagebutton.lua`、`widget_uianim.lua`、`widget_nineslice.lua`从本机游戏scripts.zip的widgets目录逐字节提取，只作行为测试，不打入Mod。`native_ui_contract.json`记录控件SHA及当前游戏可用的UI贴图/动画引用。

2026-11-12车体承伤验证补充：`health.lua`、`combat.lua`、`combat_replica.lua`、`spdamageutil.lua` 逐字节提取自本机DST的 `Contents/data/databundles/scripts.zip` 对应 `scripts/components/`。只供Lua行为测试，不随Mod打包；与既有 `rider.lua` 一起验证原版承伤、索敌及特殊伤害例外。死亡测试执行原版nofadeout行为。

`till_map.lua` 摘录当前原版 `components/map.lua` 的 `CollapseSoilAtPoint`，用于验证 1.25 原版间距下普通九宫格不会互相破坏；来源链接写在文件头。此前测试中的空地图回调不能覆盖这个问题。

这些文件从公开镜像 `https://github.com/zhuyifei1999/dst-scripts` 复制而来，
仅用于让开发者对照原版实现，**不参与 Mod 运行**，不要打包进创意工坊。

| 文件 | 用途 |
|---|---|
| `farmtiller.lua` | 园艺锄挖土坑的完整逻辑（我们逐行对齐） |
| `terraformer.lua` | 园艺耕地机铺农田地皮的核心（`Terraform(pt, doer)`） |
| `farmplantable.lua` | 种子如何种进土坑（`Plant(target, planter)`） |
| `farm_soil.lua` | 土坑 prefab 的 tag 语义（`soil` / `NOCLICK` / `NOBLOCK`） |

## 骑牛流程参考（2026-11-11）

以下文件取自原版脚本公开镜像 [vietnd69/dst-scripts](https://github.com/vietnd69/dst-scripts)，仅供本地行为测试，不随 Mod 打包：

| 本地文件 | 原版来源 | 用途 |
|---|---|---|
| `rider.lua` | [components/rider.lua](https://github.com/vietnd69/dst-scripts/blob/main/components/rider.lua) | 完整组件；验证上车、下车事件、实际下车与骑乘中存档 |
| `rideable.lua` | [components/rideable.lua](https://github.com/vietnd69/dst-scripts/blob/main/components/rideable.lua) | 完整组件；验证可骑标签、座位占用及 riderchanged 事件 |
| `riding_actions.lua` | [componentactions.lua](https://github.com/vietnd69/dst-scripts/blob/main/componentactions.lua) 的 `rideable / rider` 与 [actions.lua](https://github.com/vietnd69/dst-scripts/blob/main/actions.lua) 的 `MOUNT.fn / DISMOUNT.fn` 原文摘录 | 保留原版动作的提示规则与执行检查；外加测试模块包装 |

动画状态参考 [SGwilson.lua](https://github.com/vietnd69/dst-scripts/blob/main/stategraphs/SGwilson.lua) 的 `mount / dismount`。测试只模拟引擎表面，不验证动画表现或真实网络同步。


## 开垦完整流程参考（2026-11-11）

`farm_plow_debris.lua` 是原版 `prefabs/farm_plow.lua` 的杂物生成回调原文摘录（外部 Finished 仅在测试中提供空桩，用作生成规则对照）。`farm_soil_debris.lua`、`workable.lua`、`finiteuses.lua` 为原版完整模块，来源为 [原版脚本公开镜像](https://github.com/vietnd69/dst-scripts)。原有 `terraformer.lua` 一并用于流程测试。

这些文件只供本地测试，不进入 Mod 安装包。流程测试执行真实组件和原版杂物 prefab，但地图、实体底层、运气和掉落选择仍使用测试桩。


## 洒水完整流程参考（2026-11-11）

`farming_manager.lua` 为原版土壤管理器完整镜像，`entity_persistence.lua` 为 `EntityScript:GetPersistData`、`LoadPostPass`、`SetPersistData` 原文摘录，来源参考 [土壤管理器](https://github.com/vietnd69/dst-scripts/blob/main/components/farming_manager.lua) 与 [实体存读档](https://github.com/vietnd69/dst-scripts/blob/main/entityscript.lua)。结合原有 `finiteuses.lua` 执行真实空/满罐保存、组件先加载再迁移的生命周期，以及原版实时土壤加水钳制规则。仅测试用，不随 Mod 打包。


## 施肥完整流程参考（2026-11-11）

新增 `fertilizer.lua`、`stackable.lua`、`container.lua`、`inventoryitem.lua`，分别来自原版镜像对应 components 文件；`soil_amender.lua` 为 prefab 原文，`fertilizer_bottle_return.lua` 为其返空瓶回调原文摘录。`fertilizer_deploy.lua` 为 `standardcomponents.lua` 中 MakeDeployableFertilizer 的部署回调原文摘录，用于单份效果对照。来源：[原版组件](https://github.com/vietnd69/dst-scripts/tree/main/components)、[soil_amender](https://github.com/vietnd69/dst-scripts/blob/main/prefabs/soil_amender.lua)、[standardcomponents](https://github.com/vietnd69/dst-scripts/blob/main/standardcomponents.lua)。

测试实际执行相关方法；地图、实体、湿度/温度、库存/网络底层使用桩。这些参考文件不随 Mod 打包。

## 收割与巨大作物拆分参考（2026-11-11）

`pickable.lua` 来自 [原版组件镜像](https://github.com/vietnd69/dst-scripts/blob/main/components/pickable.lua)，保留完整组件。`oversized_harvest.lua` 为 [prefabs/veggies.lua](https://github.com/vietnd69/dst-scripts/blob/main/prefabs/veggies.lua) 中 `oversized_onfinishwork` 与 `oversized_makeloots` 的原文摘录，仅增加测试导出。测试执行原版采摘、工作组件、巨大产物掉落函数；地图、植物实体、库存与掉落实体创建使用桩，不替代实机验证，不随Mod打包。

## 放置与完整生命周期参考（2026-11-11）

`deployable.lua`、`fuel.lua` 取自同一原版镜像的对应components文件，`prefabutil.lua` 为原版工具模块完整代码。完整流程执行真实MakePlacer/Deployable、自定义校验、容器/库存归属、有限次数和实体持久化方法；测试桩不再提供GLOBAL.containers，使用require模块接口。源地址：[Deployable](https://github.com/vietnd69/dst-scripts/blob/main/components/deployable.lua)、[Fuel](https://github.com/vietnd69/dst-scripts/blob/main/components/fuel.lua)、[PrefabUtil](https://github.com/vietnd69/dst-scripts/blob/main/prefabutil.lua)。仅作测试依据，不进入Mod安装包。

## 池塘水源参考（2026-11-12）

`watersource.lua` 取自本机 Steam《饥荒联机版》`Contents/data/databundles/scripts.zip` 中的 `scripts/components/watersource.lua` 原文，仅用于回归测试，不进入 Mod 安装包。测试执行原版可用状态与 watersource 标签联动、Use 回调；池塘取水和结冰规则对照同包的 `scripts/prefabs/pond.lua`、`scripts/components/fillable.lua`。

## 鼠标动作参考（2026-11-12）

`playeractionpicker.lua`、`bufferedaction.lua` 来自同一本机游戏脚本包的 `scripts/components/playeractionpicker.lua` 和 `scripts/bufferedaction.lua` 原文。测试实际执行左右键选择、动作过滤/排序、缓冲动作构造与 Do 校验，再串联 Mod 容器和原版下车组件。仅供测试，不随 Mod 分发。

## 植物音乐安抚参考（2026-11-12）

`farmplanttendable.lua`、`farmplantstress.lua` 和依赖 `sourcemodifierlist.lua` 来自同一本机脚本包相应 components 与 util 文件原文；`farm_plant_tending.lua` 摘录 `scripts/prefabs/farm_plants.lua` 的 `on_happiness_changed` 和 `ontendto` 原文。范围、周期对照 `scripts/prefabs/phonograph.lua` 和 `scripts/tuning.lua`。仅用于执行原版安抚、压力分类和开心特效回归，不随 Mod 分发。
