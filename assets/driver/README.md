# 早期驾驶室源素材

此目录保留三视图、座位锚点、SVG/SCML及Windows合成来源，供追溯原版人物时间线。它不是0.5.4当前五视图/八向/四档资源的独立构建规范。

当前资源位于`assets/directional-v2`及`mod/Tractor/anim`：驾驶bank各自只有动画，驾驶室build与贴图共享；人物build和皮肤继续使用原版。构建入口及依赖见[资源与开发工具链](../../docs/04-资源与开发工具链.md)，人物显示逻辑见[aom_driver_visual](../../mod/Tractor/scripts/aom_driver_visual.lua)。

`tractor-views.png`和`aom_tractor_cabin`是旧三视图来源；`seat-layout.json`保存旧方向座位参数。修改后不能仅导入一个旧驾驶ZIP覆盖现行四档资源，应走当前构建及发布校验。

原详细说明保存在[历史快照](../../docs/history/2026-11-12-文档重整前/auxiliary/assets/driver/README.md)。人物皮肤、遮挡与联机仍需DST实机验收。
