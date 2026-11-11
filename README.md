# 拖拉机（Tractor）

《饥荒联机版》拖拉机与农场挂件 Mod。包含开垦、播种、洒水、施肥、除草和收割六类挂件，农业操作沿用原版组件与数值。

**当前为开发版本：世界物体与挂件动画、驾驶室坐姿动画均已完成 Windows 编译并接入，仓库与安装包默认启用驾驶室动画。没有完成 DST 实机与联机验收**，已完成的行为回归不能代替游戏内验证。

## 名称约定

Mod 中文名为 **拖拉机**，英文名为 **Tractor**。默认跟随游戏语言，也可在 Mod 配置中手动选择中文或英文；旧存档已有语言设置继续生效。

| 配件名称 | 英文名称 |
|---|---|
| 开垦机 | Land Clearer |
| 播种机 | Seeder |
| 洒水机 | Irrigator |
| 施肥机 | Fertilizer Spreader |
| 除草机 | Weeder |
| 收割机 | Harvester |

制作菜单、物品与世界实体名称、驾驶面板标题和当前文档采用上述名称。`AgeOfMachines` 目录及交付包文件名、`aom_*` 内部 ID、动画和存档键保持兼容。

## 下载

- [当前 Mod 安装包](AgeOfMachines.zip)
- [Windows 驾驶室坐姿编译包](AgeOfMachines-Windows-Driver-Kit.zip)：复用游戏自带骑牛动作，生成六向驾驶室显示；运行 `Build-Driver.cmd`，发回 `Driver-Results.zip`。详见[驾驶室接入](docs/14-驾驶室坐姿接入.md)。
- [Windows 动画编译包](AgeOfMachines-Windows-Animation-Kit.zip)：包含当前 Mod、三个 SCML 工程、全部引用图片、批处理脚本和中文说明。

Windows 动画编译：完整解压编译包，在 Steam 安装 `Don't Starve Mod Tools`，双击 `Build-Animations.cmd`。需要时把完整工具目录中的 `scml.exe` 拖入提示窗口，编译成功后取得 `Animation-Results.zip`。详见[动画编译步骤](docs/13-动画文件制作.md)。

## 安装

把 `mod/AgeOfMachines` 放进游戏根目录的 `mods/`，最终路径应为 `mods/AgeOfMachines/modinfo.lua`。Windows 上可以直接运行安装脚本，它会自动定位 Steam 库里的游戏并逐文件校验 SHA-256：

```powershell
powershell -ExecutionPolicy Bypass -File tools/install_to_game.ps1
```

也可以解压 `AgeOfMachines.zip` 到 `mods/`。进游戏后在 `Mods` 勾选「拖拉机（Tractor）」，已有存档需要重启世界；联机时所有客户端使用同一版本。安装脚本已在 Windows 上实测：52 个文件、SHA-256 校验 0 差异，驾驶室动画 23.1 MiB 随包启用。

## 当前功能

- 原版骑乘动作上下车，F 切换作业，上车默认关闭、下车自动关闭。
- 驾驶室坐姿复用游戏自带骑牛时间线，人物 build、皮肤和帽子仍由原版维护；换挂件时车头/车尾符号同步更新。
- 根据车辆经过的地块触发作业，停车不重复扣料，作业速度随挂件变化。
- 开垦机铺农田、按原版规则生成杂物、铲除并保留概率掉落、确认清理后整理坑位。
- 播种支持顺序、随机和巨大化配比规划。
- 洒水机出厂空罐、默认容量 40 次水壶用量，支持水壶和冰块补水、旧存档迁移、按实时水分浇满与实际消耗结算。
- 施肥机按需补齐三类养分，支持多次用量、按实际次数装料、缺肥续作和整格结算。
- 除草机仅处理可DIG的杂草和园艺残渣，优先保护作物，清理后复查；50次耐久按实际作业地块扣除，支持燧石维修。
- 《兰花草》真实 FMOD 音频包已包含；客户端音乐独立运行，音效异常不影响洒水。
- 收割机美术源工程保留车头独立挂点。

具体操作和实现范围以[操作流程](docs/09-操作流程.md)、[开垦机](docs/11-开垦机实现方案.md)、[洒水机](docs/12-洒水机实现方案.md)、[施肥机](docs/14-施肥机实现与验证.md)为准。早期方案和 `TASKS.md` 保留设计历史，可能与当前实现存在差异。

## 目录

| 路径 | 内容 |
|---|---|
| `mod/AgeOfMachines/` | Mod 运行文件、图标、音乐与已编译的世界/驾驶动画 |
| `美术交付/2026-11-11-v1/` | PNG、SCML 工程和美术预览 |
| `assets/audio/` | 音频源素材、FMOD 工程与构建校验记录 |
| `assets/driver/` | 驾驶室 SCML 工程、坐姿布局与占位图 |
| `tools/` | 素材构建、Windows 编译交付打包、结果接入、安装、自检与行为测试 |
| `tools/api-ref/` | 原版脚本参考及测试夹具，来源见目录内说明，不随 Mod 安装包分发 |
| `docs/` | 操作说明、技术方案及验证边界 |

## 开发验证

需要 Python 3.9 或更高版本。Windows 上设置 `PYTHONUTF8=1`（测试文件按 UTF-8 读取），安装开发依赖后运行：

```bash
python -m pip install -r requirements-dev.txt
python tools/selfcheck.py
```

当前基线为 **177 项回归通过（含 Lua 5.1 行为、驾驶动画合成与构建测试）**，另检查四个真实动画包的 BILD/ANIM/KTEX 结构、动画名及符号。测试执行真实 Lua 模块及部分原版组件，地图、实体、网络和声音底层使用测试桩。

重新生成安装包与 Windows 交付包：

```bash
python tools/package_mod.py                    # AgeOfMachines.zip
python tools/package_windows_animation.py      # 世界动画编译包
python tools/package_windows_driver.py         # 驾驶室坐姿编译包
python tools/apply_driver_results.py           # 把 Driver-Results.zip 接进 mod/
```

`apply_driver_results.py` 先校验 ZIP CRC、BILD/ANIM/KTEX 签名、bank/build 名称和骑乘所需动画，全部通过才写入 `mod/AgeOfMachines`，校验失败不动现有文件。

音乐的构建工程、编译记录和检查工具已入库；FMOD Designer、Wine、Steam Mod Tools 等工具本身不包含在仓库内。后续音频重建参见[洒水机文档](docs/12-洒水机实现方案.md)。
