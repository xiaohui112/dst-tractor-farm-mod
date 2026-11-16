"""Archive and explain the native-float32 rerun without conflating proof scopes."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    root=Path(__file__).resolve().parents[2]
    data={k:json.loads((args.input/(k+'.json')).read_text()) for k in ('main','repeat','legacy')}
    for d in data.values():
        assert d.get('completed_at') and d['snapshot_unchanged']
        assert d['mod_sha256']==data['main']['mod_sha256']
        for r in d['rows']:
            if 'solve_wall_seconds' in r:
                assert abs(r['solve_wall_seconds']-(r['quantity_wall_seconds']-r['model_wall_seconds']))<=.5, 'Clock anomaly: remeasure before publishing'
    old=json.load(gzip.open(root/'docs/evidence/cpsat-offline-2026-11-16/main/benchmark.json.gz','rt'))
    old_repeat=json.load(gzip.open(root/'docs/evidence/cpsat-offline-2026-11-16/repeat/benchmark.json.gz','rt'))
    assert data['main']['cases']==old['cases']==data['legacy']['cases']
    assert data['repeat']['cases']==old_repeat['cases']
    args.output.mkdir(parents=True,exist_ok=True)
    for name,d in data.items():
        folder=args.output/name;folder.mkdir(exist_ok=True)
        with gzip.open(folder/'benchmark.json.gz','wt') as f:
            json.dump(d,f,ensure_ascii=False)
        if name!='legacy':
            subprocess.run([sys.executable,str(Path(__file__).with_name('report.py')),
                            str(args.input/(name+'.json')),'--output',str(folder)],check=True)
    for name in ('geometry-analysis.json','witness-check.json','tests.txt','load-observation.json'):
        src=args.input/name
        if src.exists():(args.output/name).write_bytes(src.read_bytes())
    interrupted=args.input/'repeat-interrupted.json'
    if interrupted.exists():
        with gzip.open(args.output/'repeat/benchmark-interrupted.json.gz','wb') as f:f.write(interrupted.read_bytes())
    current=data['main'];repeat=data['repeat'];legacy=data['legacy']
    native_lua={r['case_id']:r for r in current['rows'] if r['solver']=='lua'}
    legacy_lua={r['case_id']:r for r in legacy['rows']}
    comparison=[]
    for c in current['cases']:
        k=c['id'];a=legacy_lua[k];b=native_lua[k]
        cps=[r for r in current['rows'] if r['case_id']==k and r['solver']!='lua' and r['optimal']]
        proven_count=cps[0]['count'] if cps else None
        comparison.append({'case_id':k,'legacy_lua_status':a['status'],'legacy_lua_count':a['count'],
                           'legacy_lua_seconds':a['quantity_wall_seconds'],
                           'native_input_lua_status':b['status'],'native_input_lua_count':b['count'],
                           'native_input_lua_seconds':b['quantity_wall_seconds'],
                           'native_cp_proven_count':proven_count,
                           'missing_directed_edges':current['geometry_diagnostics'][k]['native_only_directed_edges']})
    (args.output/'comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2))
    source_digest=hashlib.sha256(json.dumps(current['mod_sha256'],sort_keys=True).encode()).hexdigest()
    target='autumn/square-3/all-40/GIANT'
    lines=['# 原版浮点对齐后的离线复测','',
           '2026-11-16。冻结最新工作区 0.5.20 的 99 个 Mod 文件；本轮只改离线工具和证据，没有修改、打包或安装 Mod。',
           f"快照：`{current['snapshot']}`。文件清单摘要：`{source_digest}`。",'',
           '## 结论','',
           '**仅对齐离线引擎的坐标/查询语义，秋季3×3各40的 Lua 超时没有消失。** Mod 自己的 Lua 算术仍与原版距离运算不同。此前对旧输入加1e-10边界归一的实验，不能当作完整对齐引擎后的测速结果。','',
           '## 口径与验证','',
           '- 固定之前相同的48场景×3方法主测，以及相同8场景×3方法×3轮复测，共216次；另用同一个最新快照跑48次旧双精度输入的Lua对照。',
           '- 数量阶段10秒墙钟预算；Lua、CP-SAT单线程和8线程串行轮换。保留各阶段墙钟、CPU、状态、数量、上界和完整布局。',
           '- 测试使用共享桌面，并非独占机器；复测时记录到10个逻辑CPU、1分钟负载约10.84。绝对耗时和临界预算结果受负载影响，不作为实机等待时间承诺。',
           '- 复测检测到休眠式时钟跳变：CP内部计时与外层计时有约145秒、735秒等差异。受影响的两组场景/轮次均将三种方法整组重测，原记录单独保留，不计入正式结果；正式数据通过两种时钟差值检查（不超过0.5秒）。',
           '- 离线 Transform 采用float32存储；FindEntities模拟原版逐步单精度减乘加，包含半径等号，不加epsilon。原版依据是本机macOS x64 762172二进制，尚非实机查询/生长验收。',
           '- 最新Mod的Geometry、搜索、校验、整理函数完全不打补丁。Lua拿到存储后的坐标仍按原来的double算法运行。CP-SAT按原版float32距离建立同族/坑距约束。库存、季节、密度、逐格养分净零、4+4中心空位等规则保持不变。',
           '- Python独立检查使用原版精度；原Lua校验拒绝单独记录在metrics.runtime_validation_errors。不能因为原版模型认可就说现有Mod也能接受。',
           '- Lua的OPTIMAL只表示它自己模型内的证明；发现与原版可行域不同后，不以两个模型的耗时比宣称某个求解器更快。',
           f"- 三批快照前后哈希检查均通过；三批工作区Mod前后相同：{all(d['live_mod_unchanged'] for d in data.values())}。场景输入清单与旧报告逐项一致。",'',
           '## 秋季3×3各40：三轮复测','',
           '| 方法 | 完成轮数 | 株数 | 数量墙钟中位数 |','|---|---:|---|---:|']
    for method in ('lua','cp-sat-1','cp-sat-8'):
        rs=[r for r in repeat['rows'] if r['case_id']==target and r['solver']==method]
        values=sorted({r['count'] for r in rs if r['count'] is not None})
        lines.append(f"| {method} | {sum(r['optimal'] for r in rs)}/3 | {','.join(map(str,values)) or '预算内未返回证明结果'} | {statistics.median(r['quantity_wall_seconds'] for r in rs):.4f}秒 |")
    lines+=['', '## 48场景主测','',
            '| 方法/输入 | 各自模型完成证明 | 未完成证明 | 原版规则检查错误 | 原Lua拒绝的输出 |',
            '|---|---:|---:|---:|---:|']
    ls=legacy['summary']['lua']
    lines.append(f"| 最新Lua，旧double输入 | {ls['proven']}/48 | {48-ls['proven']} | 旧校验口径 | {ls.get('runtime_rejected_outputs',0)} |")
    for method,s in current['summary'].items():
        lines.append(f"| {method}，float32输入 | {s['proven']}/48 | {48-s['proven']} | {s['errors']} | {s['runtime_rejected_outputs']} |")
    lines+=['', '### Lua超时场景','',
            '| 场景 | 同快照旧输入 | float32输入 | 原版CP已证明株数 |','|---|---|---|---:|']
    for r in comparison:
        if r['native_input_lua_status']=='TIMEOUT':
            native_count=r['native_cp_proven_count'] if r['native_cp_proven_count'] is not None else '未证明'
            lines.append(f"| {r['case_id']} | {r['legacy_lua_status']}，{r['legacy_lua_seconds']:.4f}秒 | 超过10秒 | {native_count} |")
    lines+=['', '### Lua返回数量低于原版已证明数量','',
            '| 场景 | Lua模型内最优 | 原版模型最优 |','|---|---:|---:|']
    for r in comparison:
        a=r['native_input_lua_count'];c=r['native_cp_proven_count']
        if a is not None and c is not None and a<c:
            lines.append(f"| {r['case_id']} | {a} | {c} |")
    lines+=['', '## 为什么仍然出问题','',
            '对齐坐标存储后，3×3输入的原Lua几何漏掉72条有向邻接（36对），而原版距离计算认可它们。例如相邻地皮的两个x坐标为-1.3333333730697632与2.6666667461395264，z相同：Lua double算得距离平方16.00000095367433；原版逐步float32算得16。',
            '这与此前原始double坐标上的16.000000000000007不是同一对数值。只把坐标转为float32不等于后续Lua算术也自动使用float32。加1e-10既不能处理此例，也不能一般性对齐原版。','',
            '下一步应先设计并统一Mod各条同族距离判断与原版的语义，再衡量搜索优化或更换求解器的收益。本轮没有实施该修改。CP-SAT可以继续作为原版规则的离线对照；本轮数据不构成直接替换Mod求解器的依据。','',
            '## 文件','',
            '- [主测](main/report.md)、[主测CSV](main/timings.csv)、[主测原始结果](main/benchmark.json.gz)',
            '- [三轮复测](repeat/report.md)、[复测CSV](repeat/timings.csv)、[复测原始结果](repeat/benchmark.json.gz)',
            '- [受时钟中断影响的原始记录，不用于正式统计](repeat/benchmark-interrupted.json.gz)',
            '- [同快照旧输入对照](legacy/benchmark.json.gz)、[逐场景变化](comparison.json)',
            '- [浮点几何例子](geometry-analysis.json)、[FindEntities桩逐株见证复核](witness-check.json)、[冻结快照测试](tests.txt)', '']
    (args.output/'结论.md').write_text('\n'.join(lines))
    print(json.dumps({'main':current['summary'],'repeat':repeat['summary'],'legacy':legacy['summary']},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
