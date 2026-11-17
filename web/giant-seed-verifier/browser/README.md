# 浏览器 Lua 5.1 运行版本

默认页面使用 **Lua 5.1.5 WebAssembly + Dedicated Web Worker**。网页从静态文件读取运行时、Mod 原始 Lua 和规则快照，直接在访问者的浏览器中生成布局，不调用 `/api`，不需要 Python 后端。当前仅本地实现和验证，未发布到 GitHub Pages，也未增加自动发布工作流。

## 本地打开

在仓库根目录执行以下命令，仅提供静态文件：

```sh
python3 -m http.server 8890 --bind 127.0.0.1 --directory web/giant-seed-verifier/static
```

打开 `http://127.0.0.1:8890/`。这里的 Python 仅用于本地预览静态资源，不执行计算；以后可将整个 `static/` 目录托管到静态站点。不要通过 `file://` 双击 HTML，Worker 和 WASM 需要 HTTP(S)。运行时不从第三方 CDN 加载任何依赖。

原来的本机算法验证服务继续保留：启动 `server.py` 后，在地址后加 `?runtime=native` 使用 Python/Lupa，读取本机 Mod 和游戏文件，用于开发对照。默认地址使用浏览器快照，两种模式在来源窗口中有不同说明。

## 复用与适配边界

- `planner-bundle.json` 的 `modules` 是构建时逐字读取的 Mod Lua 文件；不翻译搜索、配比、模板、候选、预算或排列逻辑。浏览器执行前检查每个模块的 SHA-256。补充打包 `aom_plan_budget.lua`，因为它是当前动态规划入口的顶层依赖。
- `lua_bridge.lua` 原样打包；沿用本机验证器的地图、土坑、实体与物料仓模拟。`lua51_host.c` 只提供阶段消息、计时和原版 float32 查询运算。
- `result.lua` 只从原始计划提取结果并序列化。`planner-engine.mjs` 负责输入校验、结果整理以及独立的库存、应季、同族、坑距、逐格养分检查，不决定作物布局。模板的最终验证仍调用 Mod 原始验证函数。
- 原版作物定义在构建时由现有 Lua 5.1 适配器求值，只导出规划需要的五组字段；记录完整定义来源哈希及常量，不打包整个游戏 `scripts.zip`。浏览器不会访问 Steam 安装目录，也不能检查本机 Mod 是否与网页相同。
- `native_source`、场景适配层、结果适配层和 WASM 都有完整性校验。构建原始模块、规则快照与页面作为同一版静态资源，Mod 更新后需要重新打包；网页显示的是快照版本，不是实时本机源码。

## 任务、性能和计时

每次生成拥有独立 Worker 和新 Lua state。取消、修改输入、替换任务会终止旧 Worker；任务编号检查防止迟到结果覆盖新任务。即使 Lua 正在同步搜索，也可以取消，不依赖 Worker 接收取消消息。第一版不使用 pthreads、SharedArrayBuffer 或跨域隔离头。

两种策略保持原来的含义：模板为有工作次数预算的完整模板选配；最优策略在最大数量证明完成前不返回较少数量冒充最优，保留 64 块连通地皮上限。模板不新增固定地皮上限；实际仍受浏览器内存和设备性能约束。用户取消或运行失败会明确显示状态，不伪造完成结果。

保留生成总耗时与分阶段分析。WASM 中的 `os.clock` 绑定单调浏览器计时，`timings.basis=browser_elapsed`，不声称是进程 CPU 时间。`elapsed_ms` 从输入规范化后到独立结果校验完成，包含 Lua 源码装载、扫描和序列化；分阶段之和不一定等于总耗时。`runtime_init_ms` 单独记录校验和初始化运行时的时间，不计入生成耗时。浏览器耗时受设备和标签页调度影响，不等同游戏预览等待。

## 构建

已附带编译产物，可以直接预览。构建规则/Mod 快照（开发机器需要本机验证器依赖及游戏定义）：

```sh
python3 web/giant-seed-verifier/browser/build.py --bundle-only
```

重编运行时使用 Emscripten **4.0.20** 和本目录 `vendor/lua-5.1.5.tar.gz`：

```sh
python3 web/giant-seed-verifier/browser/build.py --emcc /path/to/emsdk/upstream/emscripten/emcc
```

SDK 先激活 4.0.20，并按其说明配置 Python 环境。Lua 源码包校验后在临时目录解压编译；不改 Mod 文件。禁用浮点融合，不启用 fast-math，游戏查询用显式 float32 中间步骤。`static/runtime/runtime-build.json` 保存编译器版本、源码及产物哈希；Lua 许可证随产物保存。

## 验证

```sh
node --test web/giant-seed-verifier/tests/test_browser_runtime.mjs web/giant-seed-verifier/tests/test_crop_display.cjs web/giant-seed-verifier/tests/test_canvas_viewport.cjs
python3 web/giant-seed-verifier/tests/browser_regression.py --output outputs/web-verifier/browser-regression.json
```

WASM 测试覆盖真实 Lua 5.1 API、协程、float32 边界、输入拒绝、完整性校验、取消加载及替换任务的迟到结果。双运行时回归在 Node 中执行与浏览器相同的 WASM，与 Python/Lupa 对照，不能代替真实浏览器的 Worker、画布和交互验证。回归超时必须作为未完成记录，不能算通过。此迁移不等同游戏实机或联网验证。本轮完整结果与边界见[验证记录](validation-20261117.md)。
