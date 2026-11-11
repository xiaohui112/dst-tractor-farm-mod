# Age of Machines · 农机时代

《饥荒联机版》拖拉机与农场挂件 Mod。包含开垦、播种、洒水、施肥、除草和收割六类挂件，农业操作沿用原版组件与数值。

**当前为开发版本，世界物体与挂件动画已完成 Windows 编译并接入，人物驾驶姿势与骑乘显示尚需接入。没有完成 DST 实机与联机验收。** 已完成的行为回归不能代替游戏内验证。

## 下载

- [当前 Mod 安装包](AgeOfMachines.zip)
- [Windows 动画编译包](AgeOfMachines-Windows-Animation-Kit.zip)：包含当前 Mod、三个 SCML 工程、全部引用图片、批处理脚本和中文说明。

Windows 动画编译：完整解压编译包，在 Steam 安装 `Don't Starve Mod Tools`，双击 `Build-Animations.cmd`。需要时把完整工具目录中的 `scml.exe` 拖入提示窗口，编译成功后取得 `Animation-Results.zip`。详见[动画编译步骤](docs/13-动画文件制作.md)。

## 当前功能

- 原版骑乘动作上下车，F 切换作业，上车默认关闭、下车自动关闭。
- 根据车辆经过的地块触发作业，停车不重复扣料，作业速度随挂件变化。
- 开垦机铺农田、按原版规则生成杂物、铲除并保留概率掉落、确认清理后整理坑位。
- 播种支持顺序、随机和巨大化配比规划。
- 洒水机出厂空罐、默认容量 40 次水壶用量，支持水壶和冰块补水、旧存档迁移、按实时水分浇满与实际消耗结算。
- 《兰花草》真实 FMOD 音频包已包含；客户端音乐独立运行，音效异常不影响洒水。
- 收割台美术源工程保留车头独立挂点。

具体操作和实现范围以[操作流程](docs/09-操作流程.md)、[开垦机](docs/11-犁头实现方案.md)、[洒水机](docs/12-洒水挂件实现方案.md)为准。早期方案和 `TASKS.md` 保留设计历史，可能与当前实现存在差异。

## 目录

| 路径 | 内容 |
|---|---|
| `mod/AgeOfMachines/` | Mod 运行文件、图标、音乐与已编译的世界动画 |
| `美术交付/2026-11-11-v1/` | PNG、SCML 工程和美术预览 |
| `assets/audio/` | 音频源素材、FMOD 工程与构建校验记录 |
| `tools/` | 素材构建、Windows 编译交付打包、自检与行为测试 |
| `tools/api-ref/` | 原版脚本参考及测试夹具，来源见目录内说明，不随 Mod 安装包分发 |
| `docs/` | 操作说明、技术方案及验证边界 |

## 开发验证

需要 Python 3.9 或更高版本。安装开发依赖后运行：

```bash
python -m pip install -r requirements-dev.txt
python tools/selfcheck.py
```

当前基线为 **109 项 Lua 5.1 行为回归通过**，另检查三个真实动画包的 BILD/ANIM/KTEX 结构、动画名及符号。测试执行真实 Lua 模块及部分原版组件，地图、实体、网络和声音底层使用测试桩。

重新生成 Windows 动画交付包：

```bash
python tools/package_windows_animation.py
```

音乐的构建工程、编译记录和检查工具已入库；FMOD Designer、Wine、Steam Mod Tools 等工具本身不包含在仓库内。后续音频重建参见[洒水机文档](docs/12-洒水挂件实现方案.md)。
