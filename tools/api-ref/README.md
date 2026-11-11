# 原版源码参考片段

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
