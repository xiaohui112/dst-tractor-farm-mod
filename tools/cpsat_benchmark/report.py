#!/usr/bin/env python3
"""Create a compact CSV and Chinese report from the raw benchmark JSON."""
import argparse
import csv
import json
from pathlib import Path
import statistics


def main():
    p = argparse.ArgumentParser()
    p.add_argument('input', type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    data = json.loads(args.input.read_text())
    rows = data['rows']
    fields = ['case_id', 'repeat', 'solver', 'status', 'optimal', 'count', 'upper',
              'quantity_wall_seconds', 'quantity_cpu_seconds', 'model_wall_seconds',
              'solve_wall_seconds', 'arrangement_wall_seconds', 'total_wall_seconds', 'errors']
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output/'timings.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    summary = data['summary']
    native = data.get('float_model') == 'native-float32'
    lines = ['# CP-SAT 离线对照结果', '',
             f"完成时间：{data.get('completed_at', '尚未完成')}。",
             f"固定 {len(data['cases'])} 个场景，每方法 {data['repeats']} 轮；数量阶段预算 {data['quantity_wall_budget_seconds']} 秒。",
             f"环境：{data['environment']['platform']}，OR-Tools {data['environment']['ortools']}。",
             f"冻结快照 SHA-256 全量前后相同：{data.get('snapshot_unchanged', False)}。",
             f"快照：`{data.get('snapshot', '')}`。", '',
             '## 汇总', '',
             '| 方法 | 测量数 | 证明最优 | 未证明 | 规则错误 | 数量阶段总墙钟秒（含超时） |',
             '|---|---:|---:|---:|---:|---:|']
    for name, s in summary.items():
        lines.append(f"| {name} | {s['runs']} | {s['proven']} | {s['runs']-s['proven']} | {s['errors']} | {s['quantity_wall_sum_seconds']:.3f} |")
    if native:
        lines += ['', '**证明口径：Lua 的 OPTIMAL 是其未修改的运行时几何模型内证明；CP-SAT 按原版 float32 距离证明。两者可能有边界可行域差异，不能只看速度比推断求解器优劣。**', '',
                  '错误列只统计原版 float32 与库存/季节/养分/坑距/密度/中心孔规则检查；原 Lua 校验拒绝单独列出：', '']
        for name, s in summary.items():
            lines.append(f"- {name}：{s.get('runtime_rejected_outputs', 0)} 份输出被原 Lua 距离/方案校验拒绝。")
    lines += ['', '只在双方均证明最优的成对样本上计算速度比：Lua 数量墙钟 ÷ CP-SAT 数量墙钟；大于 1 表示 CP-SAT 更快。', '',
              '| 方法 | 双方最优样本 | CP-SAT 更快 | 速度比中位数 | 速度比几何平均 | 最优数量不一致 |',
              '|---|---:|---:|---:|---:|---:|']
    for name in ('cp-sat-1', 'cp-sat-8'):
        if name not in summary or 'paired' not in summary[name]:
            continue
        s = summary[name]['paired']
        lines.append(f"| {name} | {s['both_proven']} | {s['cp_faster']} | {s['median_speedup']:.3f}× | {s['geomean_speedup']:.3f}× | {len(s['count_mismatches'])} |")
    lines += ['', '## 逐场景数量阶段', '',
              '以下时间为各轮中位数，单位秒。星号表示至少一轮未证明最优，此时耗时不能作为最优求解时间。数量显示“可行数量/搜索上界”；无可行解记录显示 `?`。', '',
              '| 场景 | Lua 秒 | CP-SAT 1 线程秒 | CP-SAT 8 线程秒 | 数量（Lua；1线程；8线程，最后一轮） |',
              '|---|---:|---:|---:|---|']
    for case in data['cases']:
        times, quantities = [], []
        for solver in ('lua', 'cp-sat-1', 'cp-sat-8'):
            rs = [r for r in rows if r['case_id']==case['id'] and r['solver']==solver]
            if not rs:
                times.append('—'); quantities.append('—'); continue
            times.append(f"{statistics.median(r['quantity_wall_seconds'] for r in rs):.4f}" + ('*' if any(not r['optimal'] for r in rs) else ''))
            r = rs[-1]
            quantities.append(str(r['count']) if r['optimal'] else f"{r['count'] if r['count'] is not None else '?'}/{r['upper'] if r['upper'] is not None else '?'}")
        lines.append('| '+case['id']+' | '+' | '.join(times)+' | '+'；'.join(quantities)+' |')
    lines += ['', '## 解释与限制', '',
              '- 该结果评估当前直接坑位布尔模型，不能推出所有 CP-SAT 建模方式或整数规划都较慢/较快。',
              '- 当前 Lua 有领域专用配比、上界和构造捷径；CP-SAT 原型未使用这些解提示或上界。',
              '- 主指标包含 CP-SAT 建模成本；双方均不含游戏扫描、进程启动、IPC 和校验成本。',
              '- 数量已证明的方案均接现有 Lua 排列整理器；布局和整理起点可能不同，不保证视觉质量相同。',
              '- 单线程与 8 线程分别报告。8 线程占用更多 CPU，多线程结果存在运行波动。',
              '- 超时只说明预算内未证明最优，不等于无解，也不等于 CP-SAT 找到的数量就是最大值。',
              '- 测试仅覆盖理想九宫格、现有生成器选出的连通空田；未覆盖现场坑位偏移或真实 DST 帧率、联机体验。',
              '- 完整输入、布局、证明状态、首次/后续 CP-SAT 解事件及 Mod 哈希保存在同目录 JSON。', '']
    if native:
        lines += ['- 离线 Transform 与 FindEntities 桩已模拟单精度。Mod 自己的 Lua 算术与距离校验原样保留；CP-SAT 使用原版单精度邻接，未使用容差。',
                  '- 原 Lua 整理器同样未修补，其输出仍单独经过原版规则复核；原 Lua 拒绝情况在 metrics.runtime_validation_errors 中记录。',
                  '- 本轮不是实机查询、帧率或生长验收；原版依据为本机 macOS x64 762172 二进制。', '']
    (args.output/'report.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    main()
