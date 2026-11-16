# 截图转录核对记录

2026-11-16。本轮直接查看五张本地原图，并放大逐格对照角色表；没有把旧算法生成的随机布局当成原图。这里只记录转录核对，不代表用户已人工签收，也不代表DST实机生长验收。

| 原图 | 目录编号 | 核对结果 |
|---|---|---|
| [秋季](sources/autumn.png) | autumn-01～11 | 8项九宫格启用，3项错位禁用 |
| [冬季](sources/winter.png) | winter-01～02 | 1项九宫格启用，1项错位且养分不平衡禁用 |
| [春季](sources/spring.png) | spring-01～18 | 15项九宫格启用，3项错位禁用 |
| [夏季](sources/summer.png) | summer-01～05 | 4项九宫格启用，1项含非巨大化作物的错位示例禁用 |
| [双地皮放大图](sources/pair-detail.png) | autumn-09的细节来源 | CAAAAC / CBBBBC / CC__CC；不重复增加一个布局编号 |

九宫格表逐格保留作物和空坑；所有OR按原图记录。spring-02的茄子/土豆在上，番茄在下，不能套用秋季1的作物朝向。spring-12与spring-15原图本身重复，仍分别编号；双地皮16株重复两组与四地皮32株的格子不同，不能按总需求合并。autumn-10是16番茄＋16土豆或茄子，留四角，不能改为每块中心空坑。

禁用项的原图标注数量如下，只作来源登记，不从这些错位图推导九宫格：

| 编号 | 原图标注 |
|---|---|
| autumn-03 | 4辣椒＋8玉米＋8胡萝卜或南瓜 |
| autumn-06 | 4大蒜＋8胡萝卜＋8土豆或茄子 |
| autumn-11 | 4洋葱＋8玉米＋8土豆或茄子 |
| winter-02 | 4芦笋＋8土豆＋8胡萝卜或南瓜；不把芦笋改成大蒜 |
| spring-16 | 4火龙果＋8胡萝卜＋8芦笋或玉米 |
| spring-17 | 4石榴或洋葱＋8土豆或茄子＋8芦笋或玉米 |
| spring-18 | 4西瓜＋8胡萝卜＋4芦笋或玉米＋4土豆或茄子 |
| summer-05 | 8番茄＋8玉米＋8西瓜＋8火龙果＋8石榴或洋葱；番茄标注Not Giant |

program-18-ratio与program-18-equal为独立程序定义，分别为6＋12与6＋6＋6；它们不是截图条目，也不从20株错位图改造而来。允许作物名单写在自身角色表中，不按养分向量自由扩大。

三层验收分别保存：本记录及原图为转录证据；coordinate-fixtures.json与真实Lua逐坑比对为执行证据；原版定义上的库存、季节、逐地皮净养分、同族距离、真实坑距检查为合法性证据。构建器按格子自动统计，不再同时手写布局坐标和库存需求。

重建与检查：

```sh
PYTHONPATH=/tmp/pylua python3 tools/build_seed_catalog.py
PYTHONPATH=/tmp/pylua python3 tools/build_seed_catalog.py --check
PYTHONPATH=/tmp/pylua:tools/tests python3 -m unittest test_seed_catalog test_template_strategy
python3 tools/planner_fingerprint.py
```

修改目录后必须同时回归最优策略的数量与耗时。最优的初始构造会读取合法静态候选，目录不是与其完全无关的数据。
