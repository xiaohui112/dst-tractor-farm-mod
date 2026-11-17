# 巨大化静态模版逐格审核目录

[截图转录核对记录、原图与禁用项配比](REVIEW.md)。

来源图保存在 sources/；行从上到下、列从左到右，每3行/列为一块地皮。`_`是必要空坑。替换只取原图OR；18株是单独的程序定义。

| 编号 | 分类/启用 | 角色作物（一个角色只选一种） | 格子行 | 备注 |
|---|---|---|---|---|
| autumn-01 | grid/启用 | A=tomato；B=eggplant,potato | AAA / A_B / BBB |  |
| autumn-02 | grid/启用 | A=garlic；B=onion；C=pepper | _AAAA_ / _BBBB_ / _CCCC_ |  |
| autumn-03 | staggered/禁用 | A=pepper；B=corn；C=carrot,pumpkin |  | 20株六角错位 |
| autumn-04 | grid/启用 | A=corn；B=carrot,pumpkin；C=eggplant,potato | _AAAA_ / _BBBB_ / _CCCC_ |  |
| autumn-05 | grid/启用 | A=pepper；B=tomato | _AAAA_ / _BBBB_ / _BBBB_ |  |
| autumn-06 | staggered/禁用 | A=garlic；B=carrot；C=eggplant,potato |  | 20株六角错位 |
| autumn-07 | grid/启用 | A=pepper；B=garlic；C=carrot,pumpkin | CAAAAC / CBBBBC / CC__CC |  |
| autumn-08 | grid/启用 | A=onion；B=pepper；C=corn | CAAAAC / CBBBBC / CC__CC |  |
| autumn-09 | grid/启用 | A=garlic；B=onion；C=eggplant,potato | CAAAAC / CBBBBC / CC__CC | pair-detail.png提供同图放大细节 |
| autumn-10 | grid/启用 | A=tomato；B=eggplant,potato | _AAAA_ / BBAABB / BBAABB / BBAABB / BBAABB / _AAAA_ |  |
| autumn-11 | staggered/禁用 | A=onion；B=corn；C=eggplant,potato |  | 20株六角错位 |
| winter-01 | grid/启用 | A=asparagus；B=carrot,pumpkin；C=potato | _AAAA_ / _BBBB_ / _CCCC_ |  |
| winter-02 | staggered/禁用 | A=asparagus；B=potato；C=carrot,pumpkin |  | 20株，原图芦笋4；同时养分不平衡，不纠正原图 |
| spring-01 | grid/启用 | A=carrot；B=watermelon | AAA / A_B / BBB |  |
| spring-02 | grid/启用 | A=eggplant,potato；B=tomato | AAA / A_B / BBB | 与秋季1的作物方向相反 |
| spring-03 | grid/启用 | A=asparagus,corn；B=carrot；C=eggplant,potato | _AAAA_ / _BBBB_ / _CCCC_ |  |
| spring-04 | grid/启用 | A=watermelon；B=eggplant,potato；C=pomegranate,onion；D=asparagus,corn | _BBBB_ / DCAACD / DCAACD / DCAACD / DCAACD / _BBBB_ |  |
| spring-05 | grid/启用 | A=dragonfruit；B=durian,garlic；C=pomegranate,onion | _AAAA_ / _BBBB_ / _CCCC_ |  |
| spring-06 | grid/启用 | A=dragonfruit；B=tomato | _AAAA_ / _BBBB_ / _BBBB_ |  |
| spring-07 | grid/启用 | A=pomegranate,onion；B=watermelon | _AAAA_ / _BBBB_ / _BBBB_ |  |
| spring-08 | grid/启用 | A=dragonfruit；B=carrot；C=durian,garlic | _BBBB_ / BACCAB / BACCAB / BACCAB / BACCAB / _BBBB_ |  |
| spring-09 | grid/启用 | A=dragonfruit；B=pomegranate,onion；C=asparagus,corn | CAAAAC / CBBBBC / CC__CC |  |
| spring-10 | grid/启用 | A=dragonfruit；B=durian,garlic；C=carrot | CAAAAC / CBBBBC / CC__CC |  |
| spring-11 | grid/启用 | A=durian,garlic；B=pomegranate,onion；C=eggplant,potato | CAAAAC / CBBBBC / CC__CC |  |
| spring-12 | grid/启用 | A=durian,garlic；B=pomegranate,onion；C=eggplant,potato | _CCCC_ / ACBBCA / ACBBCA / ACBBCA / ACBBCA / _CCCC_ | 原图与spring-15重复，仍分别登记 |
| spring-13 | grid/启用 | A=carrot；B=tomato；C=dragonfruit；D=asparagus,corn | _AAAA_ / DCBBCD / DCBBCD / DCBBCD / DCBBCD / _AAAA_ |  |
| spring-14 | grid/启用 | A=asparagus；B=dragonfruit；C=pomegranate,onion | _AAAA_ / ABCCBA / ABCCBA / ABCCBA / ABCCBA / _AAAA_ |  |
| spring-15 | grid/启用 | A=durian,garlic；B=pomegranate,onion；C=eggplant,potato | _CCCC_ / ACBBCA / ACBBCA / ACBBCA / ACBBCA / _CCCC_ | 原图与spring-12重复，仍分别登记 |
| spring-16 | staggered/禁用 | A=dragonfruit；B=carrot；C=asparagus,corn |  | 20株六角错位 |
| spring-17 | staggered/禁用 | A=pomegranate,onion；B=eggplant,potato；C=asparagus,corn |  | 20株六角错位 |
| spring-18 | staggered/禁用 | A=watermelon；B=carrot；C=asparagus,corn；D=eggplant,potato |  | 20株六角错位 |
| summer-01 | grid/启用 | A=dragonfruit,pepper；B=garlic；C=pomegranate,onion | _AAAA_ / _BBBB_ / _CCCC_ |  |
| summer-02 | grid/启用 | A=dragonfruit,pepper；B=tomato | _AAAA_ / _BBBB_ / _BBBB_ |  |
| summer-03 | grid/启用 | A=pomegranate,onion；B=watermelon | _AAAA_ / _BBBB_ / _BBBB_ |  |
| summer-04 | grid/启用 | A=dragonfruit,pepper；B=pomegranate,onion；C=corn | CAAAAC / CBBBBC / CC__CC |  |
| summer-05 | non_giant/禁用 | A=tomato；B=corn；C=watermelon；D=dragonfruit；E=pomegranate,onion |  | 40株错位图，另含8石榴或洋葱；番茄明确标为Not Giant |
| program-18-ratio | grid/启用 | 所有原版作物，逐地皮养分平衡、共同应季；下列为原有角色首选：A=dragonfruit,pepper；B=tomato | BBAABB / BBAABB / BBAABB | 程序定义，非原图；6+12；构建时覆盖所有共同应季且逐地皮养分平衡的原版组合，角色不拆分 |
| program-18-equal | grid/启用 | 所有原版作物，逐地皮养分平衡、共同应季；下列为原有角色首选：A=carrot,pumpkin；B=asparagus,corn；C=eggplant,potato | AAAAAA / BBBBBB / CCCCCC | 程序定义，非原图；6+6+6；构建时覆盖所有共同应季且逐地皮养分平衡的原版组合，角色不拆分 |

程序18株模板另登记单地皮9株补块（不在锁定模板列表中单独选择）。只填完整模板未占用的地皮，不改原图格子或必要空坑；逐地皮养分互补，同族由整片田实际距离校验。
