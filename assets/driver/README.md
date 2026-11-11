# 驾驶室源素材

`tractor-views.png` 是基于现有红色拖拉机参考图生成的三视图，车窗为透明开口。由 `tools/make_driver_art.py` 裁分为前斜视、侧视、后斜视，并生成驾驶室内壁/座椅的 SVG 层、可编译 SCML 与座位参数。

- `aom_tractor_cabin/aom_cabin_front/`：车身、车门、窗框、屋顶等前景遮挡，三帧。
- `aom_tractor_cabin/aom_cabin_back/`：驾驶室内壁和座椅后景，三帧，保留 SVG 源文件。
- 两个 `aom_driver_attachment_*` 符号：运行时覆盖为当前挂件，不硬画进车身。
- `seat-layout.json`：每个视角的颈部定位点和人物矩阵缩放。坐标为 ANIM 的 Y 向下坐标，不是 SCML 的 Y 向上坐标。

三个方向组 `side/upside/downside` 与原版骑乘动画的朝向位相交，左右镜像由原版六向渲染处理。原版 `mount/dismount/idle_loop/run_*` 等动画的帧率、帧数、帧事件和人物相对动作保留。

角色贴图和皮肤不在本目录。Windows 合成器从用户安装的游戏读取 `player_mount*.zip` 中 `wilsonbeefalo` bank 的动画及牛 build 的符号列表，移除牛的图形，保留人物元素并套入车辆图层。不会修改游戏原文件，也不把角色外观固定为某个人物。

当前为源工程，需 Windows 生成 `aom_tractor_driver.zip` 后启用。人物定位、复杂帽子的边缘、联机显示仍待 DST 实机验收。
