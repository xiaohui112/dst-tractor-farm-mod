# 浏览器 Lua 5.1 迁移验证记录（2026-11-17）

本轮实现了纯静态页面的 Lua 5.1.5 WebAssembly 运行时、独立 Worker、规则快照、来源校验和原生对照模式。**没有修改 Mod 规划 Lua，也没有发布 GitHub Pages。**

源码快照指纹：`45ef311f4b2da6aba0d95721ef909e1a288c8bb813198009d01b402341370469`。包含 23 个逐字读取的 Mod 模块。运行时由 Emscripten 4.0.20 编译，Lua 官方源码包及产物哈希记录在 `static/runtime/runtime-build.json`。完整对照运行前后均检查源文件、快照、适配文件和运行时哈希，没有检测到变化。

## 自动验证

| 检查 | 结果 | 范围 |
|---|---|---|
| JS/WASM 与显示测试 | 20/20 | Lua 5.1 API、协程、float32 边界、输入拒绝、快照损坏、任务取消/替换、图标与画布 |
| 现有 Python 网页回归 | 24/24 | 本机运行器、原始 Mod 对照、库存边界、模版、HTTP、取消和错误输入 |
| 双运行时完整对照 | 182/182 | 最优 89 例；模版 93 例 |
| 用户大田专项 | 1/1 | 春季、6×8 去掉 F1、12 种应季作物各40 |
| 测试超时处理 | 符合预期 | 两个故意超时案例均记录 incomplete，退出码2，没有计入通过 |
| 页面静态契约 | 通过 | 61 个引用ID存在且无重复；资源使用相对路径；JS语法、diff空白检查通过 |

完整对照每种策略均包含四季×16种田形（64例）、固定随机留出12例、库存/断开起点/超限边界9例、大田4例；模版另含4例锁定图案。比较数量、上界、最优标志、逐坑作物与坐标、库存、扫描田块、模板模块、检查结果及排列指标。另从实际坑位独立检查同族、养分、应季和坑距，不将耗时作为相等条件。

原型阶段发现空坑 `false` 被结果序列化成 `null`，已修复适配器并新增保留空坑表示的测试。最终整套使用修复后的快照重跑，182例均无差异。规划模块本身未为此改变。

大田对照包括秋/冬/夏64块三种各192（两策略均576株）、春季47块三种各192（两策略均423株），以及锁定单格8株模版铺81块（648株）。最优策略81块场景按原规则返回 `FARM_TOO_LARGE`。模板的 `optimal` 字段照原始结果保留，页面仍使用“固定模版布局”描述，不把所有模板选配宣称为全局最优。

用户大田专项使用6×8去掉F1，春季全部12种应季作物各40，单独与原生运行器逐坑对照：384株、39个空坑、剩余96颗，两边完整输出无差异。

## 真实浏览器验证

使用内置浏览器访问只提供文件的 `http.server`，不使用计算接口。静态预览服务观察到80次GET资源请求，未出现 `/api` 请求。

- 最优策略：64块田生成576株，同族576/576，显示已证明最大合法播种量。
- 模版策略：用户47块春田生成384株，同族384/384，保留各阶段耗时分析，标注浏览器耗时。
- 1280×720下页面尺寸等于视口，14种库存展开，表格clientHeight与scrollHeight均345，没有表内滚动。
- “完整农田”在两个方向均适应画布；“清晰查看”可滚动到底部，背景层与784px完整内容范围一致，没有纯色接缝。
- 正在计算时可打开来源窗口；取消后按钮恢复，再次生成成功。
- 两个页面同时计算，小田完成时大田仍在运行，随后大田完成，互不取消。
- `/giant-seed-verifier/static/` 项目子路径下成功生成32株，图片全部加载。
- `?runtime=native` 仍可生成384株并显示CPU计时，来源说明与浏览器快照模式区分。

浏览器截图和结构化证据保存在本地 `outputs/web-verifier/wasm-*`；全量对照结果为 `browser-regression.json`，用户大田为 `browser-user-large-parity.json`，故意超时为 `browser-timeout-validation.json`。Node执行相同WASM的对照与真实浏览器UI验证分别记录，不混为同一项证据。

本次未进行Safari、手机性能、游戏实机或多人联网验证；浏览器秒数也不作为这些环境的速度承诺。

## 重跑

```sh
node --test web/giant-seed-verifier/tests/test_browser_runtime.mjs web/giant-seed-verifier/tests/test_crop_display.cjs web/giant-seed-verifier/tests/test_canvas_viewport.cjs
python3 web/giant-seed-verifier/tests/browser_regression.py --case-seconds 30 --output outputs/web-verifier/browser-regression.json
```

现有本机网页回归在 `web/giant-seed-verifier/` 内运行 `python3 -m unittest discover -s tests -v`。静态包 `outputs/web-verifier/tractor-browser-static-0.5.24.zip` 已检查目录条目、逐文件内容及ZIP完整性，通过后仅作为本地产物保留。
