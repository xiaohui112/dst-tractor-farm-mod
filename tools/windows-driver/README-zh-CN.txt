拖拉机 · 驾驶室坐姿 Windows 编译包

本次只需生成新的驾驶动画，不需要再次编译之前的三个世界动画包。

1. 将整个包“全部提取”到英文短路径，例如 C:\AOM-Driver\，不要在 ZIP 预览中运行。
2. 保留已经安装的 Don't Starve Mod Tools 和饥荒联机版（Don't Starve Together）。
3. 双击 Build-Driver.cmd。
4. 提示找不到工具时，把完整 Mod Tools 目录里的 scml.exe 拖入黑色窗口，按 Enter。
5. 提示选择游戏时，在 Steam 右键“饥荒联机版”→ 管理 → 浏览本地文件，
   把包含 data 的游戏根文件夹拖进窗口，按 Enter。不要选择模组目录或游戏快捷方式。
6. 脚本先编译驾驶室三视图，再自动读取游戏自带 player_mount*.zip 中的骑牛姿势。
   它使用 Mod Tools 自带 Python 2.7，也兼容 Python 3，正常安装不需要你另装依赖。
7. 成功显示 SUCCESS: ...\Driver-Results.zip 后，把 Driver-Results.zip 发回来。

本包内容：
  AgeOfMachines\                    修改后的当前 Mod，已保留之前的三个已编译世界动画
  AgeOfMachines\exported\aom_tractor_cabin\  新的 SCML 与图层 PNG
  Build-Driver.cmd                  一键编译与合成
  Collect-Driver-Results.cmd        再次检查并收集结果
  driver_animation.py              原版骑乘动画合成器，Python 2.7 / 3 标准库
  seat-layout.json                 方向座位锚点、人物缩放参数
  Source-Manifest.json             本次源文件 SHA-256
  Driver-Pending.lua               未完成构建时的禁用清单

角色显示方法：
  原版角色的头、身体、衣服、帽子、皮肤继续由游戏提供，不把人物画死进拖拉机。
  只读取并复制原版骑牛动画的动作时间线，移除牛和牛鞍的绘制元素，加入拖拉机前后层。
  驾驶室内壁/座椅 → 人物 → 车窗框、车门、车身，是同一动画中的固定层次。
  前斜视、侧视、后斜视三套车体加镜像覆盖六个朝向。
  上下车仍由原版 MOUNT、DISMOUNT 和 SGwilson 状态机执行，动作帧数、帧率和事件保持。

本次生成的新资源：
  AgeOfMachines\anim\aom_tractor_driver.zip
  AgeOfMachines\scripts\aom_driver_visual_bank.lua
  AgeOfMachines\Driver-Build-Report.json

Driver-Results.zip 会包含上述文件、日志和来源清单。
必须连同 aom_driver_visual_bank.lua 一起替换，不能只拿一个 ZIP；它在成功时才启用新驾驶画面。
构建失败时保持未启用，不冒充编译完成。失败请发 logs 文件夹，里面有 cabin.log、driver.log。

如果脚本找不到 Mod Tools 自带 Python：
  在完整工具目录搜索 python.exe，然后把路径拖入提示窗口。
  常见位置为 mod_tools\buildtools\windows\Python27\python.exe。
  不需要管理员权限或修改 PowerShell 执行策略。

如果提示找不到 player_mount*.zip 或 beefalo_build.zip：
  确认选了客户端游戏根目录，并使用 Steam 验证游戏文件完整性。
  合成器同时支持 data\anim 下的独立资源和 data\databundles 中的动画归档。
  日志会列出缺失的动画或原版版本不支持之处，把日志发回来，不要随意改名伪造资源。

如果自行测试：
  先备份旧 Mod，再用构建完成后的完整 AgeOfMachines 文件夹替换游戏里的同名 Mod。
  重启客户端和服务器，让所有客户端使用同一版本。
  检查上下车、六个朝向、头部/帽子与窗框的遮挡、换挂件、死亡/移除清理。
  实际窗口内的位置和不同帽子的边缘仍需在游戏内验证，不能只以脚本成功代替视觉验收。

当前代码和素材已经完成；真实游戏原版动画只在你的 Windows 上读取并合成。
本机未安装 DST，尚未对最终合成画面进行实机验收。本包不分发原版角色贴图或工具程序。
