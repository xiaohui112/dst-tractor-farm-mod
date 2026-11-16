#!/usr/bin/env python3
"""Offline GIANT quantity comparison. Never edits or installs Mod files."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
import platform
import shutil
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import seed_strategy_audit as audit
from seed_strategy_matrix import matrix_cases
import ortools
from ortools.sat.python import cp_model
import native_float

FLOAT_MODEL = 'native-float32'


def manifest(root=ROOT):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((root / 'mod').rglob('*')) if p.is_file()}


def freeze(target):
    """Freeze runtime sources, including test-world preload dependencies."""
    if not target.exists():
        before = manifest()
        shutil.copytree(ROOT/'mod', target/'mod')
        shutil.copytree(ROOT/'tools/api-ref', target/'tools/api-ref')
        if before != manifest() or before != manifest(target):
            raise RuntimeError('Sources changed while copying snapshot; retry with a fresh path')
    audit.giant.ROOT = target
    return manifest(target)


def scenarios():
    # Fixed, preselected subset of existing generators; no result-based selection.
    selected = [c for c in audit.cases()
                if c['shape'] in ('single', 'L-3', 'ring-8')
                and c['id'].split('/')[-1] in ('all-season', 'user-tails')]
    selected += audit.holdout_cases(8) + audit.large_cases()
    selected += [c for c in matrix_cases() if c.get('strategy') == 'GIANT'
                 and ('/square-3/all-40/' in c['id'] or '/square-7/all-40/' in c['id'])]
    selected += [c for c in matrix_cases() if c.get('strategy') == 'GIANT'
                 and c['id'] in ('spring/L-7/all-40/GIANT', 'autumn/notch-7/all-40/GIANT')]
    assert len(selected) == 48 and len({c['id'] for c in selected}) == 48
    return selected


def context(case):
    """Identical canonical 9-pit input for both solvers, in runtime BFS order."""
    w = audit.world()
    if FLOAT_MODEL == 'native-float32':
        native_float.install(w)
    L = w.lua
    remaining = set(map(tuple, case['tiles']))
    queue = [tuple(case['tiles'][0])]
    ordered = []
    while queue:
        x, z = queue.pop(0)
        if (x, z) not in remaining:
            continue
        remaining.remove((x, z))
        ordered.append((x, z))
        queue.extend(((x, z-1), (x-1, z), (x+1, z), (x, z+1)))
    if remaining:
        raise ValueError('Requires one connected region')
    tiles = [{'x': x*4, 'z': z*4} for x, z in ordered]
    slots = [{'x': t['x'] + (s % 3 - 1)*w.grid_spacing,
              'z': t['z'] + (s // 3 - 1)*w.grid_spacing,
              'cx': t['x'], 'cz': t['z']} for t in tiles for s in range(9)]
    if FLOAT_MODEL == 'native-float32':
        # These are positions read back from engine-owned soil entities.
        for slot in slots:
            slot['x'], slot['z'] = native_float.f32(slot['x']), native_float.f32(slot['z'])
    g = L.globals()
    for slot in slots:
        soil=g.SpawnPrefab('farm_soil')
        soil.Transform.SetPosition(soil.Transform,slot['x'],0,slot['z'])
    g.tiles = L.table_from(tiles, recursive=True)
    g.slots = L.table_from(slots, recursive=True)
    # Runtime inventory collection excludes unidentified seeds before this API.
    g.stock = L.table_from({k: n for k, n in case['stock'].items() if k in audit.RULES})
    g.season = case['season']
    L.execute("""
Layout=require('aom_seed_layout');Balance=require('aom_seed_balance')
Packing=require('aom_seed_packing');crops=Layout.Crops(stock,DEFS,season)
task={};geometry=nil
""")
    return w, slots


def geometry(w):
    w.lua.execute('geometry=Layout.Geometry(tiles,slots,DEFS);geometry.balanced=true')
    return w.lua.globals().geometry


def geometry_diagnostics(case):
    """Outside timed solves: compare native radius to unmodified Lua geometry."""
    w, slots = context(case)
    geo = geometry(w)
    distances = native_float.distance_matrix(slots)
    native_only, lua_only = [], []
    for i in range(len(slots)):
        actual = {int(q.j)-1 for q in geo.near[i+1].values()
                  if (geo.ranges[16][i+1][q.j] if geo.ranges is not None else q.d <= 16)}
        native = {int(j) for j in (distances[i] <= 16).nonzero()[0]}
        native_only += [[i+1, j+1] for j in sorted(native-actual)]
        lua_only += [[i+1, j+1] for j in sorted(actual-native)]
    return {'radius':4, 'native_only_directed_edges':len(native_only),
            'lua_only_directed_edges':len(lua_only), 'native_only_examples':native_only[:6],
            'slots_sha256':hashlib.sha256(json.dumps(slots,sort_keys=True).encode()).hexdigest(),
            'slots':slots}


def validate(case, w, slots, board):
    """Existing independent checker + runtime layout and full plan validators."""
    points = [{**p, 'crop': k or False} for p, k in zip(slots, board)]
    errors, metrics = audit.independent_check(case, points)
    if FLOAT_MODEL == 'native-float32':
        # Keep inventory/season/nutrients/region checks, replace tolerant family
        # and double spacing checks with the independently emulated engine.
        errors = [e for e in errors if e not in ('family', 'spacing')]
        distances = native_float.distance_matrix(slots)
        for i, crop in enumerate(board):
            if not crop:
                continue
            rule = audit.RULES[crop]
            family = sum(other == crop and distances[i, j] <= native_float.radius_squared(rule['radius'])
                         for j, other in enumerate(board))
            if family < rule['minimum']:
                errors.append('family')
            if any(board[j] and distances[i, j] <= native_float.radius_squared(audit.CONSTANTS['FARM_TILL_SPACING'])
                   for j in range(i)):
                errors.append('spacing')
    for t in range(len(slots)//9):
        cells = board[t*9:t*9+9]
        counts = Counter(k for k in cells if k)
        if sorted(counts.values()) == [4, 4] and cells[4]:
            errors.append('4+4-center')
        if sum(counts.values()) > audit.CONSTANTS['FARM_PANT_OVERCROWDING_MAX_PLANTS']:
            errors.append('density')
    L = w.lua
    L.globals().board = L.table_from([k or False for k in board])
    if L.globals().geometry is None:
        geometry(w)
    runtime_errors = []
    if not L.eval('Layout.Valid(board,geometry)'):
        runtime_errors.append('lua-layout-invalid')
    if any(board):
        L.globals().checked_slots = L.table_from(points, recursive=True)
        valid = L.eval("require('aom_dynamic_farm').Validate({dynamic=true,tiles=tiles,slots=checked_slots,season=season,nutrient_balanced=true,strategy='GIANT'})")
        if not (valid[0] if isinstance(valid, tuple) else valid):
            runtime_errors.append('lua-plan-invalid')
    metrics['runtime_validation_errors'] = runtime_errors
    if FLOAT_MODEL != 'native-float32':
        errors += runtime_errors
    return sorted(set(errors)), metrics


def model_for(w, slots):
    """Pure Boolean pit model; no templates, solution hints or Lua upper bounds."""
    L = w.lua
    g = L.globals()
    geo = geometry(w)
    native_distances = native_float.distance_matrix(slots) if FLOAT_MODEL == 'native-float32' else None
    crops = [g.crops[i] for i in range(1, len(g.crops)+1)]
    model = cp_model.CpModel()
    x = [[model.new_bool_var(f'p{i}_{k}') for k in crops] for i in range(len(slots))]
    occupied = [model.new_bool_var(f'occupied{i}') for i in range(len(slots))]
    for i in range(len(slots)):
        model.add(sum(x[i]) == occupied[i])
    for c, k in enumerate(crops):
        model.add(sum(row[c] for row in x) <= int(g.stock[k]))
        definition = g.DEFS[k]
        for i in range(len(slots)):
            if native_distances is not None:
                near = [int(j) for j in (native_distances[i] <= native_float.radius_squared(definition.family_check_dist)).nonzero()[0]]
            else:
                near = [int(q.j)-1 for q in geo.near[i+1].values()
                        if q.d <= definition.family_check_dist**2]
            model.add(sum(x[j][c] for j in near) >= int(definition.family_min_count)).only_enforce_if(x[i][c])
    for i in range(len(slots)):
        conflicts = ([int(j) for j in (native_distances[i] <= native_float.radius_squared(audit.CONSTANTS['FARM_TILL_SPACING'])).nonzero()[0]]
                     if native_distances is not None else [int(j)-1 for j in geo.conflicts[i+1].values()])
        for j in conflicts:
            if j > i:
                model.add(occupied[i] + occupied[j] <= 1)
    for t in range(len(slots)//9):
        indices = range(t*9, t*9+9)
        counts = [sum(x[i][c] for i in indices) for c in range(len(crops))]
        for nutrient in (1, 2, 3):
            terms = []
            for c, k in enumerate(crops):
                vector = g.Balance.Vector(g.DEFS[k])
                if vector is None:
                    model.add(counts[c] == 0)
                else:
                    assert vector[nutrient] == int(vector[nutrient])
                    terms.append(int(vector[nutrient])*counts[c])
            model.add(sum(terms) == 0)
        total = sum(occupied[i] for i in indices)
        model.add(total <= int(audit.CONSTANTS['FARM_PANT_OVERCROWDING_MAX_PLANTS']))
        eight = model.new_bool_var(f'eight{t}')
        model.add(total == 8).only_enforce_if(eight)
        model.add(total != 8).only_enforce_if(eight.Not())
        fours = []
        for c, count in enumerate(counts):
            four = model.new_bool_var(f'four{t}_{c}')
            model.add(count == 4).only_enforce_if(four)
            model.add(count != 4).only_enforce_if(four.Not())
            fours.append(four)
        # With 8 plants and occupied center, forbid two species of exactly 4.
        model.add(sum(fours) <= 1).only_enforce_if([eight, occupied[t*9+4]])
    model.maximize(sum(occupied))
    return model, x, crops


class Progress(cp_model.CpSolverSolutionCallback):
    def __init__(self):
        super().__init__()
        self.events = []

    def on_solution_callback(self):
        self.events.append({'solve_wall_seconds': self.wall_time,
                            'count': round(self.objective_value),
                            'upper': self.best_objective_bound})


def run_cp(case, workers, seconds):
    w, slots = context(case)
    start, cpu = time.perf_counter(), time.process_time()
    model, x, crops = model_for(w, slots)
    built = time.perf_counter()
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = 4217849
    solver.parameters.max_time_in_seconds = max(0.001, seconds-(built-start))
    callback = Progress()
    status = solver.solve(model, callback)
    end = time.perf_counter()
    feasible = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    row = {'solver': f'cp-sat-{workers}', 'status': solver.status_name(status),
           'optimal': status == cp_model.OPTIMAL, 'count': round(solver.objective_value) if feasible else None,
           'upper': solver.best_objective_bound, 'quantity_wall_seconds': end-start,
           'quantity_cpu_seconds': time.process_time()-cpu, 'model_wall_seconds': built-start,
           'solve_wall_seconds': solver.wall_time, 'solutions': callback.events,
           'branches': solver.num_branches, 'conflicts': solver.num_conflicts, 'errors': []}
    if feasible:
        board = [next((k for c, k in enumerate(crops) if solver.value(x[i][c])), False)
                 for i in range(len(slots))]
        row['errors'], row['metrics'] = validate(case, w, slots, board)
        row['board'] = board
        if row['optimal']:
            arrange(case, w, slots, row)
    return row


def arrange(case, w, slots, row):
    L = w.lua
    start = time.perf_counter()
    # Same runtime routine and size-dependent search budget as Packing.Balanced.
    L.execute('arranged,arrangement=Layout.Regularize(board,geometry,nil,false,#tiles>16 and 250 or 1400)')
    row['arrangement_wall_seconds'] = time.perf_counter()-start
    row['total_wall_seconds'] = row['quantity_wall_seconds'] + row['arrangement_wall_seconds']
    row['arranged_board'] = [L.globals().arranged[i] for i in range(1, len(slots)+1)]
    errors, row['arranged_metrics'] = validate(case, w, slots, row['arranged_board'])
    row['errors'] += errors
    if row['arranged_metrics']['count'] != row['count']:
        row['errors'].append('arrangement-changed-count')


def run_lua(case, seconds):
    w, slots = context(case)
    L = w.lua
    g = L.globals()
    start, cpu = time.perf_counter(), time.process_time()
    quantity_end = []

    def stage(name):
        if name == 'arrangement':
            quantity_end.append((time.perf_counter(), time.process_time()))

    def guard():
        if not quantity_end and time.perf_counter()-start > seconds:
            raise TimeoutError('quantity deadline')

    g.stage_hook, g.guard = stage, guard
    L.execute("trace={Stage=function(_,s)stage_hook(s)end,Skip=function()end,Context=function()end,Emit=function()end,Clock=os.clock}")
    try:
        L.execute('result,proof=Packing.Balanced(crops,stock,tiles,slots,DEFS,guard,trace,task)')
    except TimeoutError:
        return {'solver': 'lua', 'status': 'TIMEOUT', 'optimal': False, 'count': None,
                'upper': None, 'quantity_wall_seconds': time.perf_counter()-start,
                'quantity_cpu_seconds': time.process_time()-cpu, 'errors': []}
    end = time.perf_counter()
    qwall, qcpu = quantity_end[0] if quantity_end else (end, time.process_time())
    board = [g.result[i] for i in range(1, len(slots)+1)] if g.result is not None else [False]*len(slots)
    row = {'solver': 'lua', 'status': 'OPTIMAL' if g.proof.optimal else 'FEASIBLE',
           'optimal': bool(g.proof.optimal), 'count': int(g.proof.total or 0), 'upper': g.proof.upper,
           'quantity_wall_seconds': qwall-start, 'quantity_cpu_seconds': qcpu-cpu,
           'arrangement_wall_seconds': end-qwall, 'total_wall_seconds': end-start,
           'board': board}
    row['errors'], row['metrics'] = validate(case, w, slots, board)
    return row


def summary(rows):
    out = {}
    for name in ('lua', 'cp-sat-1', 'cp-sat-8'):
        rs = [r for r in rows if r['solver'] == name]
        if not rs:
            continue
        proven = [r for r in rs if r['optimal']]
        out[name] = {'runs': len(rs), 'proven': len(proven), 'errors': sum(bool(r['errors']) for r in rs),
                     'runtime_rejected_outputs':sum(bool(r.get('metrics',{}).get('runtime_validation_errors')) for r in rs),
                     'quantity_wall_sum_seconds': sum(r['quantity_wall_seconds'] for r in rs),
                     'proven_quantity_wall_median': statistics.median(r['quantity_wall_seconds'] for r in proven) if proven else None}
    lua = {(r['case_id'], r['repeat']): r for r in rows if r['solver'] == 'lua'}
    for name in ('cp-sat-1', 'cp-sat-8'):
        paired = [(lua.get((r['case_id'], r['repeat'])), r) for r in rows if r['solver'] == name]
        paired = [(a,b) for a,b in paired if a and a['optimal'] and b['optimal']]
        if paired:
            ratios = [a['quantity_wall_seconds']/b['quantity_wall_seconds'] for a,b in paired]
            out[name]['paired'] = {'both_proven': len(paired), 'cp_faster': sum(v>1 for v in ratios),
                                    'median_speedup': statistics.median(ratios),
                                    'geomean_speedup': math.exp(statistics.mean(math.log(v) for v in ratios)),
                                    'count_mismatches': [a['case_id'] for a,b in paired if a['count'] != b['count']]}
    return out


def main():
    global FLOAT_MODEL
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seconds', type=float, default=10)
    p.add_argument('--repeat', type=int, default=1)
    p.add_argument('--limit', type=int)
    p.add_argument('--case', action='append', help='Exact case ID (repeatable)')
    p.add_argument('--workers', type=int, nargs='+', default=[1, 8])
    p.add_argument('--snapshot', type=Path, help='Create/reuse an immutable runtime snapshot')
    p.add_argument('--float-model', choices=['native-float32', 'legacy-double'], default='native-float32')
    args = p.parse_args()
    FLOAT_MODEL = args.float_model
    cases = scenarios()
    if args.case:
        cases = [c for c in cases if c['id'] in args.case]
        if len(cases) != len(set(args.case)):
            p.error('Unknown case ID')
    if args.limit:
        cases = cases[:args.limit]
    snapshot = (args.snapshot or args.output.parent/'source-snapshot').resolve()
    frozen = freeze(snapshot)
    live_before = manifest()
    report = {'started_at': datetime.now().astimezone().isoformat(), 'mod_sha256': frozen,
              'snapshot': str(snapshot), 'float_model': FLOAT_MODEL,
              'native_float_sha256': hashlib.sha256(Path(native_float.__file__).read_bytes()).hexdigest(),
              'benchmark_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'environment': {'platform': platform.platform(), 'python': sys.version, 'ortools': ortools.__version__},
              'native_sha256': hashlib.sha256(audit.NATIVE.encode()).hexdigest(),
              'rules': audit.RULES, 'constants': audit.CONSTANTS, 'cases': cases,
              'quantity_wall_budget_seconds': args.seconds, 'repeats': args.repeat,
              'proof_scope_note':'Lua executes the frozen Mod source without planner patches. Older snapshots recompute double distances; native-query snapshots use the emulated engine membership. CP uses the selected float model. Compare validation diagnostics and source fingerprints, not just times.',
              'geometry_diagnostics':{}, 'rows': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for repeat in range(args.repeat):
        for index, case in enumerate(cases):
            if case['id'] not in report['geometry_diagnostics']:
                report['geometry_diagnostics'][case['id']] = geometry_diagnostics(case)
            methods = [('lua', None)] + [('cp', n) for n in args.workers]
            shift = (index + repeat) % len(methods)
            methods = methods[shift:] + methods[:shift]
            for method, workers in methods:
                row = run_lua(case, args.seconds) if method == 'lua' else run_cp(case, workers, args.seconds)
                row.update(case_id=case['id'], repeat=repeat)
                row['proof_scope'] = 'snapshot-lua-planner' if method == 'lua' else FLOAT_MODEL
                report['rows'].append(row)
                report['summary'] = summary(report['rows'])
                args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
                print(index+1, repeat+1, case['id'], row['solver'], row['status'], row['count'],
                      round(row['quantity_wall_seconds'], 4), row['errors'], flush=True)
                if row['errors']:
                    raise RuntimeError('Rule validation failed; see report')
            proven = [r['count'] for r in report['rows'] if r['case_id']==case['id'] and r['repeat']==repeat and r['optimal']]
            feasible = [r['count'] for r in report['rows'] if r['case_id']==case['id'] and r['repeat']==repeat and r['count'] is not None]
            if len(set(proven)) > 1 or proven and max(feasible) > proven[0]:
                if FLOAT_MODEL == 'native-float32':
                    report.setdefault('cross_model_count_disagreements', []).append({'case_id':case['id'],'repeat':repeat})
                else:
                    raise RuntimeError('Optimal counts disagree; see report')
    report['snapshot_unchanged'] = manifest(snapshot) == frozen
    report['live_mod_unchanged'] = manifest() == live_before
    report['completed_at'] = datetime.now().astimezone().isoformat()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    assert report['snapshot_unchanged'], 'Frozen sources changed during benchmark'
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
