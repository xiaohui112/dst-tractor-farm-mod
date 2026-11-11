农机时代 · Windows 动画编译包
生成日期：2026-11-11
适用：Windows 10 / 11，Steam 版 Don't Starve Mod Tools

你需要做的事：解压整个包 → 安装官方工具 → 双击编译脚本 → 把 Animation-Results.zip 发回来。
素材、目录结构和当前 Mod 已放好，不需要重新出图，也不用另外安装 Python。

一、解压到英文短路径

建议解压到：C:\AOM\
不要在压缩软件的预览窗口里直接运行脚本，必须先“全部提取”。
解压后的同一层应看到：

  Build-Animations.cmd        编译三个工程，成功后自动检查和收集
  Collect-Results.cmd         单独重新检查、收集已有产物
  README-zh-CN.txt            本说明
  Source-Manifest.json        源文件清单和 SHA-256
  Attachment-Preview.png      挂件装配参考图
  AgeOfMachines\             当前 Mod，含音频和图标
    modinfo.lua
    modmain.lua
    exported\
      aom_tractor_chassis\    .scml + body/attachment/attachment_front 图片
      aom_attachment_shared\ .scml + 六种挂件图片
      aom_attachment_symbols\.scml + 七组符号图片
    anim\                    编译结果目录，开始时不预放三个动画 ZIP

所有 PNG 都在各自工程内，目录不要拆散，也不要只复制 SCML。

二、安装 Don't Starve Mod Tools

1. 打开 Windows 上的 Steam，进入“库”。
2. 在筛选中勾选“工具”，搜索 Don't Starve Mod Tools 并安装。
3. 右键工具 → 管理 → 浏览本地文件。
4. 在安装目录搜索 scml.exe，通常在：

   C:\Program Files (x86)\Steam\steamapps\common\Don't Starve Mod Tools\mod_tools\scml.exe

如果 Steam 在 D 盘或别的库，使用实际安装路径。
不要只把 scml.exe 拷出来；它需要同一套工具中的 compiler_scripts、exported、Python 和贴图转换程序。
不要把 FMOD Designer 当作动画编译器，FMOD 负责的是声音。

三、开始编译

1. 双击本包的 Build-Animations.cmd。
2. 脚本会先找常见安装位置。
3. 找不到时，它会显示“Drag scml.exe into this window”：
   从资源管理器把 scml.exe 拖到黑色窗口里，按 Enter。
   也可以粘贴完整路径；带空格和引号都可以。
4. 等待依次显示：
   [1/3] Building tractor chassis...
   [2/3] Building attachment items...
   [3/3] Building attachment symbols...
5. 编译日志在本包的 logs 文件夹。
6. 三个工程编译后，脚本自动运行产物检查。

成功时应显示三行 OK，以及：

   SUCCESS: C:\AOM\Animation-Results.zip

脚本没有修改系统 PowerShell 执行策略，不需要管理员权限。
如果系统或组织策略禁止脚本运行，不要关闭安全设置，把拦截提示和日志发回来即可。

四、发回哪个文件

请把生成的 Animation-Results.zip 整个发回来。
其中包括：

  aom_tractor_chassis.zip
  aom_attachment_shared.zip
  aom_attachment_symbols.zip
  可能生成的独立 .tex 图集
  logs\
  Source-Manifest.json

检查脚本会打开三个 ZIP，确认里面有真实的 build.bin（BILD）和 anim.bin（ANIM），
并检查内置 TEX 的 KTEX 文件头。源素材中间包和 PLACEHOLDER 占位文件不会通过。

如果编译完后窗口关了，可以再双击 Collect-Results.cmd 检查和收集。
失败时请发 logs 文件夹；不要把 exported 目录下编译器生成的中间 ZIP 当成最终动画。

五、脚本找不到工具或需要手动执行时

打开 cmd，按实际路径分别执行：

"C:\Program Files (x86)\Steam\steamapps\common\Don't Starve Mod Tools\mod_tools\scml.exe" "C:\AOM\AgeOfMachines\exported\aom_tractor_chassis\aom_tractor_chassis.scml" "C:\AOM\AgeOfMachines"
"C:\Program Files (x86)\Steam\steamapps\common\Don't Starve Mod Tools\mod_tools\scml.exe" "C:\AOM\AgeOfMachines\exported\aom_attachment_shared\aom_attachment_shared.scml" "C:\AOM\AgeOfMachines"
"C:\Program Files (x86)\Steam\steamapps\common\Don't Starve Mod Tools\mod_tools\scml.exe" "C:\AOM\AgeOfMachines\exported\aom_attachment_symbols\aom_attachment_symbols.scml" "C:\AOM\AgeOfMachines"

每条命令有两个参数：SCML 文件路径，以及 Mod 根目录。
第二个参数不是 anim 文件夹。最终资源应进入 AgeOfMachines\anim\。
不是把 SCML 单独拖到 scml.exe 上就能完成整个流程。

工具参数依据：
https://github.com/kleientertainment/ds_mod_tools#usage

六、常见问题

找不到 PNG：
  请重新“全部提取”；检查 .scml 旁边的 body、attachment 等子目录是否保留。

找不到 Python / zipanim.py / export.py / TextureConverter：
  使用 Steam 安装的完整 Mod Tools 中的 scml.exe，不要复制单个可执行文件。
  可在 Steam 验证工具文件完整性。不要随意用 Python 3 替代工具自带版本。

ZIP 存在但检查不通过：
  可能是中间包、占位文件，或后续贴图/动画编译失败。发 logs 文件夹回来。

工具报告 Invalid number of arguments：
  按第五节保留两个带引号的完整参数，并把日志发回来核对工具版本。

七、本次交付范围与下一步

本包用于把现有三套世界物体/挂件美术编译成真实游戏资源。
这些素材当前包含 idle、work、death、idle_packed 以及六种挂件符号，
收割台保留独立车头图层 attachment_front。

编译成功不等于人物驾驶姿势已经接好：原版骑牛会隐藏底盘，
人物坐姿、骑乘中的车体显示、完整方向动画仍需后续接入和游戏验证。
你只需发回编译结果；后续覆盖项目、检查挂件符号和骑乘显示由我继续处理。

项目已接入本次 Windows 生成的三个真实世界动画。该包仍是供后续重新编译使用的工程包，
所以 anim 目录不预放这三个产物，避免旧文件被误认成新的编译结果。
当前 Mod 包已包含《兰花草》真实音频资源，不需要你再次编译音乐。
本包没有附带第三方工具二进制，需要从 Steam 安装官方 Mod Tools。
素材引用和包内容已在本机核对；批处理脚本尚未在真实 Windows 上执行。
