#!/usr/bin/env python3
"""两种巨大化策略的尺寸/库存矩阵，或模版模式的完整地形回归。"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from functools import partial
import hashlib
import json
from pathlib import Path

import seed_strategy_audit as audit


def matrix_cases():
    cases = []
    for season in ('autumn', 'winter', 'spring', 'summer'):
        for side in (1, 2, 3, 5, 7, 8):
            for amount in (4, 10, 20, 40, 99):
                for mode in ('GIANT_TEMPLATE', 'GIANT'):
                    cases.append({
                        'id': f'{season}/square-{side}/all-{amount}/{mode}',
                        'season': season, 'strategy': mode,
                        'tiles': [(x, z) for z in range(side) for x in range(side)],
                        'stock': {k: amount for k, v in audit.RULES.items() if season in v['seasons']},
                    })
        for shape in ('notch', 'L', 'ring'):
            coords = [(x, z) for z in range(7) for x in range(7)
                      if (shape == 'notch' and (x, z) != (6, 6))
                      or (shape == 'L' and (x == 0 or z == 6))
                      or (shape == 'ring' and (x in (0, 6) or z in (0, 6)))]
            for mode in ('GIANT_TEMPLATE', 'GIANT'):
                cases.append({
                    'id': f'{season}/{shape}-7/all-40/{mode}',
                    'season': season, 'strategy': mode, 'tiles': coords,
                    'stock': {k: 40 for k, v in audit.RULES.items() if season in v['seasons']},
                })
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=('matrix', 'template-all'), default='matrix')
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--case-seconds', type=float, default=30)
    parser.add_argument('--output', type=Path, default=Path('outputs/seed-strategy-matrix.json'))
    args = parser.parse_args()
    cases = matrix_cases() if args.suite == 'matrix' else [
        {**case, 'strategy': 'GIANT_TEMPLATE'} for case in audit.all_balanced_cases()]
    scripts = audit.ROOT / 'mod/Tractor/scripts'
    paths = sorted(set(scripts.glob('aom_seed_*.lua')) | {scripts / 'aom_dynamic_farm.lua'})

    def hashes():
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

    report = {'source_sha256': hashes(), 'started_at': datetime.now().isoformat(),
              'case_wall_budget_seconds': args.case_seconds, 'rows': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        run = partial(audit.run_case, case_seconds=args.case_seconds)
        for row in pool.map(run, cases):
            report['rows'].append(row)
            if len(report['rows']) % 20 == 0 or row['errors']:
                print(len(report['rows']), '/', len(cases), row['id'], row.get('count'), row['errors'], flush=True)
                args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if hashes() != report['source_sha256']:
        raise RuntimeError('回归期间源码发生变化，报告不能用于发布验收')
    report['completed_at'] = datetime.now().isoformat()
    audit.write_timing_artifacts(report, args.output)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report['timing_summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
