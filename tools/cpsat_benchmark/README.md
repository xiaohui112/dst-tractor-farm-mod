# CP-SAT 离线对照原型

此目录只用于开发机实验，不被 Mod、网页验证器或发布包引用。
比较选定冻结源码的 `aom_seed_packing.Balanced` 与 OR-Tools CP-SAT 的最大播种量求解；当前Mod版本0.5.23。历史实验不代表此版本已重测，设计与结论口径见[最优报告](../../docs/reports/巨大化最优设计与验证报告.md)。

## 运行

在仓库根目录，使用 Python 3.11 创建独立环境：

```sh
python3.11 -m venv outputs/cpsat-venv
outputs/cpsat-venv/bin/pip install -r tools/cpsat_benchmark/requirements.txt
outputs/cpsat-venv/bin/python -m unittest discover -s tools/cpsat_benchmark -p 'test_*.py' -v
outputs/cpsat-venv/bin/python tools/cpsat_benchmark/benchmark.py --output outputs/cpsat-comparison/benchmark.json --seconds 10
```

沿用 `tools/seed_strategy_audit.py`，从本机 Steam DST `scripts.zip` 读取真实作物定义与常量；游戏安装路径同该审计工具。
使用 `--case ID` 可指定场景（可重复），`--repeat 3` 可重复测量，`--workers 1 8` 指定 CP-SAT 线程数。

## 模型与规则

- 坑位 × 应季已识别作物的 0–1 变量，每坑至多一株；库存不足同族最低数的作物与普通未知种子不参与。
- 每种作物总量不超过库存，每块地皮三个养分分量分别净变化为零；不读取当前肥力。
- 每株在原版半径内（包含自身）达到原版同族最低数，允许同族跨地皮。
- 原版坑距冲突和单地皮密度上限。
- 最优策略不限制4＋4的空坑位置；中心留空仅参与固定数量后的整齐评分。模版策略另按目录保留固定空坑。
- 目标只最大化合法株数；证明数量后调用与 Mod 相同的 `Layout.Regularize`、同样的尺寸相关试探预算整理排列。整理是现有启发式，不声称排列全局最优。

默认 `--float-model native-float32`：输入坑位模拟原版 Transform 的 float32 存储与读回，离线 FindEntities 桩按原版单精度减/乘/加顺序计算，边界包含等号，无 epsilon。依据为本机 macOS x64 762172 原版二进制，见 `docs/evidence/family-distance-2026-11-16/原版FindEntities边界核对.md`。

**直接运行冻结的 Mod 源码，不在离线进程中替换 Geometry 或校验函数。** 2026-11-16 修复前的快照仍以 Lua double 重算距离，与引擎存在边界可行域差异；修复后的 Mod 直接采用原版 `FindEntities` 返回的邻接关系，离线环境只模拟该引擎接口。CP-SAT 的同族和坑距约束使用原版 float32 距离；养分和其他规则保持不变。报告分别记录原版检查错误与 `metrics.runtime_validation_errors`（对应快照的 Lua 校验拒绝），不把后者隐藏成规则通过。历史报告及快照保持原样。

CP-SAT 不读取 Lua 求解结果、上界、模版或解提示。每份输出检查库存、季节、逐格养分、中心孔、密度和原版 float32 同族/坑距，并额外执行原 Lua `Layout.Valid` 与非空方案的 `Dynamic.Validate`。Python 原审计中的宽容差同族检查不再作为本模式的距离判据。原 Lua 整理器保持不变，整理后的输出另做相同检查。

`--float-model legacy-double` 保留此前实验的双精度输入、Lua 邻接以及旧校验口径，仅用于同快照前后对照。两种模式使用相同的库存、季节、九宫格布局意图和求解预算；可行域的差异是本次诊断结果的一部分，不能直接称作纯求解器速度比较。
测试对单地皮土豆/番茄的全部 3^9 个布局枚举，并验证与 CP-SAT 的完整可行集相等（含空布局共 71 个）。

## 对照口径

固定 48 个场景均来自已有生成器：24 个四季单格/L形/环形与零碎库存场景，8 个固定随机种子连通农田，6 个 63/64 地皮场景，8 个四季 3×3/7×7 全种类库存 40 场景，2 个大型缺角/L形场景。

三种方法串行运行，逐场景轮换执行顺序；每次创建新的 Lua 环境，避免跨场景缓存。比较对象是核心规划器，不含游戏扫描、进程启动或数据传输。所有方法使用同一批坑坐标、BFS 地皮顺序、库存、季节和原版定义。

- `quantity_wall_seconds`：主要指标。Lua 从进入 `Packing.Balanced` 到开始整理；CP-SAT 包含几何准备、Python 建模和求解。公共测试世界/输入构建、结果校验不计入。
- `quantity_cpu_seconds`：进程 CPU，8 线程可能远大于墙钟时间，不能当作玩家等待时间。
- `model_wall_seconds` / `solve_wall_seconds`：CP-SAT 分项。
- `arrangement_wall_seconds` / `total_wall_seconds`：数量完成后的同一整理算法耗时，以及两阶段合计；双方初始布局不同，整理耗时与质量可能不同。
- `status`、`optimal`、`count`、`upper`：严格区分有解和已证明最优。Lua 超时不虚构当前最优解/上界，报告为未知；CP-SAT 保留有解时的数量及搜索上界。
- `solutions`：CP-SAT 每次改进的时间与数量；Lua 未插桩记录首解，不作首解速度比较。

数量预算默认 10 秒，CP-SAT 扣除建模后设置剩余求解时间，Lua 在原有 yield 点检查；两者均有少量停止延迟。排列阶段独立计时、不受数量预算截断。CP-SAT 不启用容差最优或提前接受可行解。
空布局在数学模型中是合法的数量 0；运行时不把空布局作为可播方案，此处只比较数量。

开跑前把 Mod 与测试世界 API 参考复制到输出目录的 `source-snapshot`，所有 Lua 模块（含测试世界预加载模块）都从快照读取。结束检查快照 SHA-256 不变；并行任务随后改动工作区不会混入本次测试。`--snapshot PATH` 可复用指定快照。该快照仅供本机复现，不打包或安装到游戏。
报告保存完整输入、布局、规则、版本与所有快照 Mod 文件 SHA-256，同时记录工作区是否有其他并行改动。
只对双方各自模型均报告最优的成对样本列出耗时比，并单独统计超时和数量/几何差异；有边界可行域差异时不能把该比值视为同一个数学问题的算法速度比。不能把超时预算当成实际最优求解时间，也不能从少数成功样本推断全部场景收益。
