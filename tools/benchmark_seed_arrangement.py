#!/usr/bin/env python3
"""Compare two frozen Mod sources through the real web Lua adapter.

Alternate source order on repeated runs; keep CPU phases separate from wall time.
No alternative planner or relaxed validation is used.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'web/giant-seed-verifier'))
import runner


def cases():
    three = {'carrot': 192, 'corn': 192, 'potato': 192}
    shapes = {
        'L': [[0, 0], [1, 0], [2, 0], [0, 1], [0, 2]],
        'T': [[0, 0], [1, 0], [2, 0], [1, 1]],
        'U': [[0, 0], [0, 1], [1, 1], [2, 1], [2, 0]],
        'ring': [[x, z] for z in range(3) for x in range(3) if (x, z) != (1, 1)],
        'bridge': [[0, 0], [0, 1], [1, 0], [2, 0], [3, 0], [3, 1], [4, 0]],
        'notch': [[x, z] for z in range(5) for x in range(5) if not (x >= 3 and z >= 3)],
    }
    out = []

    def add(name, stock, width=3, height=3, season='autumn', tiles=None, **extra):
        data = dict(width=width, height=height, season=season, seeds=stock, **extra)
        if tiles is not None:
            data['tiles'] = tiles
        out.append({'id': name, 'input': data})

    add('screenshot-5x5', three, 5, 5)
    add('full-8x8', three, 8, 8)
    add('limited-equal', dict.fromkeys(three, 40), 5, 5)
    add('unequal-tails', {'carrot': 7, 'corn': 7, 'potato': 24, 'tomato': 17}, 5, 1)
    add('mixed-nine', {k: 40 for k in ('carrot', 'corn', 'potato', 'tomato', 'eggplant', 'pumpkin', 'garlic', 'onion', 'pepper')}, 5, 5)
    add('two-crops', {'tomato': 100, 'potato': 100}, 5, 5)
    add('single-4+4', {'tomato': 9, 'potato': 9}, 1, 1)
    add('winter-three', {'carrot': 40, 'asparagus': 40, 'potato': 40}, season='winter')
    add('summer-three', {'onion': 40, 'garlic': 40, 'pepper': 40}, season='summer')
    for name, tiles in shapes.items():
        width = max(x for x, z in tiles) + 1
        height = max(z for x, z in tiles) + 1
        add(name + '-full', three, width, height, tiles=tiles)
    add('T-minimum', {k: 4 for k in ('carrot', 'corn', 'potato', 'tomato', 'eggplant', 'pumpkin', 'garlic', 'onion', 'pepper')}, tiles=shapes['T'])
    add('U-tails', {k: 7 for k in ('carrot', 'corn', 'potato', 'tomato', 'eggplant', 'pumpkin')}, tiles=shapes['U'])
    add('ring-scarce', {k: 6 for k in ('carrot', 'corn', 'potato', 'tomato', 'eggplant', 'pumpkin', 'garlic', 'onion', 'pepper')}, tiles=shapes['ring'])
    add('bridge-mixed', {k: 6 for k in ('carrot', 'corn', 'potato', 'tomato', 'asparagus', 'eggplant', 'watermelon', 'dragonfruit', 'durian', 'garlic', 'onion', 'pomegranate')}, 5, 2, season='spring', tiles=shapes['bridge'])
    add('locked-template', {'tomato': 40, 'potato': 40}, 2, 2, strategy='GIANT_TEMPLATE')
    return out


def pattern_metrics(slots):
    tiles = defaultdict(list)
    for p in slots:
        tiles[p['cx'], p['cz']].append(p)
    groups = defaultdict(Counter)
    patterns = {}
    for tile, points in sorted(tiles.items()):
        points.sort(key=lambda p: (p['z'], p['x']))
        motif = tuple(p['crop'] or '_' for p in points)
        composition = tuple(sorted(Counter(motif).items()))
        groups[composition][motif] += 1
        patterns[f'{tile[0] / 4:g},{tile[1] / 4:g}'] = list(motif)
    mismatched_tiles = sum(sum(g.values()) - max(g.values()) for g in groups.values())
    # Independent global pairwise pit mismatch, normalized by group size.
    mismatch = 0
    for group in groups.values():
        size = sum(group.values())
        motifs = list(group.items())
        for i, (a, n) in enumerate(motifs):
            for b, m in motifs[i + 1:]:
                mismatch += n * m * sum(x != y for x, y in zip(a, b)) / size
    return {'mismatched_tiles': mismatched_tiles, 'pattern_mismatch': mismatch, 'patterns': patterns}


def tile_compositions(slots):
    tiles = defaultdict(Counter)
    for p in slots:
        tiles[p['cx'], p['cz']][p['crop'] or '_'] += 1
    return dict(tiles)


def execute(case, source, seconds):
    started = time.perf_counter()

    def cancelled():
        if time.perf_counter() - started > seconds:
            raise TimeoutError(f'{case["id"]}: exceeded {seconds}s')
        return False

    modules = tuple(name for name in runner.MODULES if (source / 'scripts' / name).exists())
    with patch.object(runner, 'MOD', source), patch.object(runner, 'MODULES', modules):
        result = runner.run(case['input'], cancelled=cancelled)
    return {**result, 'pattern_metrics': pattern_metrics(result['slots'])}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before', type=Path, required=True, help='Frozen Tractor directory with scripts and modinfo.lua')
    p.add_argument('--after', type=Path, default=ROOT / 'mod/Tractor')
    p.add_argument('--rounds', type=int, default=3)
    p.add_argument('--case-seconds', type=float, default=45)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--only', help='Comma-separated case IDs')
    args = p.parse_args()
    selected = [c for c in cases() if not args.only or c['id'] in args.only.split(',')]
    report = {'rounds': args.rounds, 'basis': 'quantity/arrangement: process CPU ms; elapsed: backend elapsed_ms (before independent export checks)', 'cases': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for case in selected:
        row = {**case, 'before': [], 'after': []}
        for repeat in range(args.rounds):
            order = ('before', 'after') if repeat % 2 == 0 else ('after', 'before')
            for label in order:
                try:
                    r = execute(case, getattr(args, label).resolve(), args.case_seconds)
                    row[label].append(r)
                except Exception as exc:
                    row[label].append({'error': str(exc)})
        row['summary'] = {}
        for label in ('before', 'after'):
            results = [r for r in row[label] if 'error' not in r]
            if len(results) != args.rounds:
                row['summary'][label] = {'errors': [r['error'] for r in row[label] if 'error' in r]}
                continue
            first = results[0]
            row['summary'][label] = {
                'count': first['count'], 'optimal': first['optimal'], 'valid': first['valid'],
                'quantity_ms': statistics.median(r['timings']['quantity_ms'] for r in results),
                'arrangement_ms': statistics.median(r['timings']['arrangement_ms'] for r in results),
                'wall_ms': statistics.median(r['elapsed_ms'] for r in results),
                'mismatched_tiles': first['pattern_metrics']['mismatched_tiles'],
                'pattern_mismatch': first['pattern_metrics']['pattern_mismatch'],
                'deterministic': all(r['slots'] == first['slots'] for r in results),
            }
        report['cases'].append(row)
        if not any('errors' in s for s in row['summary'].values()):
            before, after = row['before'][0], row['after'][0]
            row['quantity_unchanged'] = before['count'] == after['count'] and before['used'] == after['used']
            row['tile_compositions_unchanged'] = tile_compositions(before['slots']) == tile_compositions(after['slots'])
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(case['id'], json.dumps(row['summary'], ensure_ascii=False), flush=True)
    if any('errors' in s for c in report['cases'] for s in c['summary'].values()):
        raise SystemExit(1)
    if any(c['summary']['before']['count'] != c['summary']['after']['count'] for c in report['cases']):
        raise SystemExit('Maximum quantity changed')
    if any(not c['quantity_unchanged'] or not c['tile_compositions_unchanged'] for c in report['cases']):
        raise SystemExit('Per-crop or per-tile quantities changed')


if __name__ == '__main__':
    main()
