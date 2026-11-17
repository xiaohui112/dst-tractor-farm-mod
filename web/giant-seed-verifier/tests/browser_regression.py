#!/usr/bin/env python3
"""Native Lua 5.1 versus browser Lua WASM, without controlling a browser.

python3 web/giant-seed-verifier/tests/browser_regression.py --limit 2 --output /tmp/browser-smoke.json
python3 web/giant-seed-verifier/tests/browser_regression.py --case-seconds 30 --output /tmp/browser-regression.json

--limit selects N cases PER strategy. Exit 0 means all selected comparisons passed,
1 means a mismatch/error, and 2 means incomplete (including a hard case timeout).
Durations are recorded separately and never compared for equality.
"""
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'tools'))
IGNORE_META = {'fingerprint', 'runtime', 'installed_match', 'timing_basis', 'snapshot'}
STRATEGIES = ('GIANT', 'GIANT_TEMPLATE')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def json_hash(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode())


def differences(expected, actual, path='', exact=False):
    """Retain paths and values; coordinate/crop comparisons use exact=True."""
    out = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(expected.keys() | actual.keys()):
            loc = f'{path}.{key}' if path else key
            if key not in expected or key not in actual:
                out.append({'path': loc, 'expected': expected.get(key, '<missing>'), 'actual': actual.get(key, '<missing>')})
            else:
                out.extend(differences(expected[key], actual[key], loc, exact))
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            out.append({'path': path + '.length', 'expected': len(expected), 'actual': len(actual)})
        for i, (a, b) in enumerate(zip(expected, actual)):
            out.extend(differences(a, b, f'{path}[{i}]', exact))
    else:
        numeric = type(expected) in (int, float) and type(actual) in (int, float)
        equal = (expected == actual if exact else math.isclose(expected, actual, rel_tol=1e-10, abs_tol=1e-8)) if numeric else type(expected) is type(actual) and expected == actual
        if not equal:
            out.append({'path': path, 'expected': expected, 'actual': actual})
    return out


def build_cases():
    import runner  # Adds the verifier's bundled lupa runtime before audit imports.
    import seed_strategy_audit as audit
    structured = audit.cases()
    selected = []
    for season in ('autumn', 'winter', 'spring', 'summer'):
        for i, shape in enumerate(audit.SHAPES):
            options = [c for c in structured if c['season'] == season and c['shape'] == shape]
            selected.append(options[i % 12])
    assert len(selected) == 64
    selected += audit.holdout_cases(12)
    base = []
    for case in selected:
        tiles = [list(t) for t in case['tiles']]
        base.append({'name': case['id'], 'suite': 'holdout' if case['id'].startswith('holdout-') else 'NativeParity', 'scene': {
            'season': case['season'], 'width': max(t[0] for t in tiles) + 1,
            'height': max(t[1] for t in tiles) + 1, 'tiles': tiles, 'start': tiles[0], 'seeds': case['stock']}})
    for n in (0, 1, 3, 4, 7, 9, 10):
        base.append({'name': f'boundary/stock-{n}', 'suite': 'boundary', 'scene': {
            'width': 1, 'height': 1, 'seeds': {'potato': n, 'tomato': 40, 'randomseed': 100}},
            'expect': {'count': 8 if n >= 4 else 0}})
    base.append({'name': 'boundary/disconnected-start', 'suite': 'boundary', 'scene': {
        'width': 4, 'height': 1, 'tiles': [[0, 0], [3, 0]], 'start': [3, 0],
        'seeds': {'potato': 20, 'tomato': 20}}, 'expect': {'count': 8}})
    # Use three balanced species at 192, not the known expensive mixed-stock grids.
    for case in audit.large_cases():
        if case['id'] not in ('large/autumn-64', 'large/winter-64', 'large/summer-64'):
            continue
        base.append({'name': case['id'] + '/three-192', 'suite': 'large', 'scene': {
            'width': 8, 'height': 8, 'season': case['season'], 'tiles': [list(t) for t in case['tiles']], 'seeds': case['stock']}})
    spring = [[x, z] for z in range(6) for x in range(8) if (x, z) != (7, 5)]
    base.append({'name': 'large/spring-47', 'suite': 'large', 'scene': {
        'width': 8, 'height': 6, 'season': 'spring', 'tiles': spring,
        'seeds': {'carrot': 192, 'corn': 192, 'potato': 192}}})
    base.append({'name': 'boundary/template-81-optimal-over-limit', 'suite': 'boundary', 'scene': {
        'width': 9, 'height': 9, 'season': 'autumn', 'seeds': {'tomato': 324, 'potato': 324}}})
    out = []
    for item in base:
        for strategy in STRATEGIES:
            row = {**item, 'id': strategy + '/' + item['name'], 'scene': {**item['scene'], 'strategy': strategy}}
            if item['name'] == 'boundary/template-81-optimal-over-limit':
                if strategy == 'GIANT_TEMPLATE':
                    row['scene']['template_id'] = 'autumn-01'
                    row['expect'] = {'count': 648}
                else:
                    row['expect'] = {'count': 0, 'reason': 'FARM_TOO_LARGE'}
            out.append(row)
    for name, season, width, height, seeds in (
        ('autumn-09', 'autumn', 2, 1, {'garlic': 4, 'onion': 4, 'potato': 8}),
        ('autumn-10', 'autumn', 2, 2, {'tomato': 16, 'potato': 16}),
        ('spring-11', 'spring', 2, 2, {'garlic': 8, 'onion': 8, 'potato': 16}),
        ('spring-12', 'spring', 2, 2, {'garlic': 8, 'onion': 8, 'potato': 16}),
    ):
        out.append({'id': 'GIANT_TEMPLATE/locked/' + name, 'name': 'locked/' + name, 'suite': 'locked', 'scene': {
            'strategy': 'GIANT_TEMPLATE', 'template_id': name, 'season': season,
            'width': width, 'height': height, 'seeds': seeds}})
    assert all(sum(c['suite'] in ('NativeParity', 'holdout') and c['scene']['strategy'] == s for c in out) == 76 for s in STRATEGIES)
    return out


def file_rows(meta):
    return {row['path']: row for row in meta.get('files', [])}


def compare_meta(expected, actual, path):
    errors = []
    for key, value in expected.items():
        if key in IGNORE_META or key == 'files':
            continue
        if key not in actual:
            errors.append({'path': f'{path}.{key}', 'expected': value, 'actual': '<missing>'})
        else:
            errors.extend(differences(value, actual[key], f'{path}.{key}'))
    expected_files, actual_files = file_rows(expected), file_rows(actual)
    for name, row in expected_files.items():
        errors.extend(differences(row, actual_files.get(name), f'{path}.files.{name}'))
    for name, row in actual_files.items():
        if name in expected_files:
            continue
        p = (ROOT / 'mod/Tractor' / name).resolve()
        if not p.is_relative_to(ROOT / 'mod/Tractor') or not p.is_file():
            errors.append({'path': f'{path}.files.{name}', 'error': 'extra manifest file not found in Mod'})
        else:
            errors.extend(differences({'path': name, 'bytes': p.stat().st_size, 'sha256': digest(p.read_bytes())}, row, f'{path}.files.{name}'))
    return errors


def verify_bundle(bundle_path):
    import runner
    bundle = json.loads(bundle_path.read_text())
    errors, hashes = [], {}
    modules = bundle.get('modules', {})
    if not modules:
        raise ValueError('bundle.modules is empty')
    scripts = (runner.MOD / 'scripts').resolve()
    for name, source in modules.items():
        p = (scripts / (name + '.lua')).resolve()
        if not p.is_relative_to(scripts) or not p.is_file() or not isinstance(source, str):
            errors.append({'path': f'modules.{name}', 'error': 'module/source path is invalid'})
            continue
        expected, actual = digest(p.read_bytes()), digest(source.encode())
        hashes[name] = expected
        if expected != actual:
            errors.append({'path': f'modules.{name}', 'expected': expected, 'actual': actual})
    for name in runner.MODULES:
        if name[:-4] not in modules:
            errors.append({'path': f'modules.{name[:-4]}', 'error': 'runner module missing from bundle'})
    meta = runner.metadata()
    errors.extend(compare_meta(meta, bundle.get('meta', {}), 'bundle.meta'))
    # native_source is a planning-field snapshot, not the whole game prefab.
    # Its original-game hash is compared above through meta.native_sha256.
    lua, native = runner._execute({'season': 'autumn', 'tiles': [[0, 0]], 'start': [0, 0], 'seeds': {}, 'crop_order': []})

    def plain(value):
        if hasattr(value, 'items'):
            return {str(k): plain(v) for k, v in value.items()}
        return value

    fields = ('good_seasons', 'family_min_count', 'family_check_dist', 'nutrient_consumption', 'nutrient_restoration')
    definitions = {k: {f: plain(native.defs[k][f]) for f in fields} for k in runner.CROP_ORDER}
    errors.extend(differences(definitions, bundle.get('definitions'), 'definitions'))
    snapshot = plain(lua.execute(bundle['native_source']).PLANT_DEFS)
    errors.extend(differences(definitions, snapshot, 'native_source.definitions'))
    adapters = {'bridge': (HERE / 'lua_bridge.lua').read_text()}
    # The adapter is authored by the main agent; both its embedded bytes and,
    # where present, its original file are checked without reimplementing it.
    adapter_file = HERE / 'browser/result.lua'
    if adapter_file.exists():
        adapters['result_adapter'] = adapter_file.read_text()
    for key in ('native_source', 'bridge', 'result_adapter'):
        raw = bundle.get(key)
        if not isinstance(raw, str):
            errors.append({'path': key, 'error': 'adapter source missing'})
            continue
        if key in adapters:
            errors.extend(differences(digest(adapters[key].encode()), digest(raw.encode()), key + '.source_sha256'))
        errors.extend(differences(digest(raw.encode()), bundle.get('adapter_hashes', {}).get(key), 'adapter_hashes.' + key))
    runtime = bundle.get('runtime_build', {})
    for name in ('lua51.mjs', 'lua51.wasm'):
        p = bundle_path.parent / name
        actual = digest(p.read_bytes())
        errors.extend(differences(actual, runtime.get('files', {}).get(name), 'runtime_build.files.' + name))
        hashes['runtime/' + name] = actual
    build_file = bundle_path.parent / 'runtime-build.json'
    if build_file.exists():
        errors.extend(differences(json.loads(build_file.read_text()), runtime, 'runtime_build'))
    hashes['bundle'] = digest(bundle_path.read_bytes())
    return {'status': 'failed' if errors else 'passed', 'errors': errors, 'hashes': hashes, 'native_sha256': meta['native_sha256']}, bundle


def connected(scene):
    tiles = set(map(tuple, scene.get('tiles', [[x, z] for z in range(scene['height']) for x in range(scene['width'])])))
    start = tuple(scene.get('start', next(iter(tiles))))
    found, todo = {start}, deque([start])
    while todo:
        x, z = todo.popleft()
        for p in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            if p in tiles and p not in found:
                found.add(p)
                todo.append(p)
    return found


def pattern_metrics(slots):
    groups, tiles = defaultdict(Counter), defaultdict(list)
    for p in slots:
        tiles[p['cx'], p['cz']].append(p)
    for points in tiles.values():
        motif = tuple(p['crop'] or '_' for p in sorted(points, key=lambda p: (p['z'], p['x'])))
        groups[tuple(sorted(Counter(motif).items()))][motif] += 1
    mismatch = 0
    for group in groups.values():
        motifs = list(group.items())
        for i, (a, n) in enumerate(motifs):
            for b, m in motifs[i + 1:]:
                mismatch += n * m * sum(x != y for x, y in zip(a, b)) / sum(group.values())
    return {'pattern_mismatch': mismatch, 'mismatched_tiles': sum(sum(g.values()) - max(g.values()) for g in groups.values())}


def legality(scene, result):
    import seed_strategy_audit as audit
    errors = []
    points = result['slots']
    used = dict(Counter(p['crop'] for p in points if p['crop']))
    errors.extend(differences(used, result['used'], 'used_from_slots', exact=True))
    errors.extend(differences(sum(used.values()), result['count'], 'count_from_slots', exact=True))
    remaining = {k: n - used.get(k, 0) for k, n in scene['seeds'].items()}
    errors.extend(differences(remaining, result['remaining'], 'remaining_from_stock', exact=True))
    if any(n < 0 for n in remaining.values()):
        errors.append({'path': 'remaining', 'error': 'negative inventory'})
    case = {'tiles': connected(scene), 'season': scene['season'], 'stock': scene['seeds']}
    independent, _ = audit.independent_check(case, points, native_float=True)
    errors.extend({'path': 'independent_check', 'error': e} for e in independent)
    allowed = {(x * 4, z * 4) for x, z in connected(scene)}
    if any((p['cx'], p['cz']) not in allowed for p in points):
        errors.append({'path': 'slots', 'error': 'slot outside start-connected field'})
    if len({(p['x'], p['z']) for p in points}) != len(points):
        errors.append({'path': 'slots', 'error': 'duplicate pit coordinates'})
    return errors


def compare_case(case, native, browser):
    import runner
    errors = []
    for field in ('count', 'upper', 'optimal', 'reason', 'strategy', 'valid', 'used', 'remaining', 'tiles', 'template_modules', 'checks', 'layout', 'used_tiles', 'input'):
        if field in native or field in browser:
            errors.extend(differences(native.get(field, '<missing>'), browser.get(field, '<missing>'), field))
    errors.extend(differences(native['slots'], browser.get('slots'), 'slots', exact=True))
    errors.extend(compare_meta(native['source'], browser.get('source', {}), 'source'))
    for field, expected in case.get('expect', {}).items():
        errors.extend(differences(expected, native.get(field), 'expect.native.' + field))
        errors.extend(differences(expected, browser.get(field), 'expect.browser.' + field))
    scene = runner.normalize(case['scene'])
    metrics = {}
    for name, result in (('native', native), ('browser', browser)):
        errors.extend({'runtime': name, **e} for e in legality(scene, result))
        metrics[name] = pattern_metrics(result['slots'])
    errors.extend(differences(metrics['native'], metrics['browser'], 'independent_pattern_metrics'))
    return errors, metrics


def native_worker():
    try:
        import runner
        scene = json.load(sys.stdin)
        started = time.perf_counter()
        result = runner.run(scene)
        print(json.dumps({'status': 'complete', 'wall_ms': (time.perf_counter() - started) * 1000, 'result': result}, ensure_ascii=False, allow_nan=False))
    except Exception:
        print(json.dumps({'status': 'error', 'error': traceback.format_exc()}))
        return 1
    return 0


def native_run(case, seconds):
    started = time.perf_counter()
    try:
        proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--native-worker'], input=json.dumps(case['scene']), text=True, capture_output=True, timeout=seconds)
        try:
            row = json.loads(proc.stdout)
        except ValueError:
            row = {'status': 'error', 'error': 'Invalid native worker JSON', 'stdout': proc.stdout}
        if proc.stderr:
            row['stderr'] = proc.stderr
        return row
    except subprocess.TimeoutExpired:
        return {'status': 'incomplete', 'wall_ms': (time.perf_counter() - started) * 1000, 'error': f'Native exceeded {seconds}s; process killed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--case-seconds', type=float, default=30)
    parser.add_argument('--output', type=Path, default=Path('/tmp/tractor-browser-regression.json'))
    parser.add_argument('--limit', type=int, help='first N cases per strategy, including both strategies')
    parser.add_argument('--only', help='case ID substring filter')
    parser.add_argument('--list', action='store_true', help='print generated cases without running engines')
    args = parser.parse_args()
    if not math.isfinite(args.case_seconds) or args.case_seconds <= 0 or args.limit is not None and args.limit <= 0:
        parser.error('--case-seconds and --limit must be positive')
    cases = build_cases()
    if args.only:
        cases = [c for c in cases if args.only in c['id']]
    if args.limit:
        seen = Counter()
        selected = []
        for case in cases:
            strategy = case['scene']['strategy']
            seen[strategy] += 1
            if seen[strategy] <= args.limit:
                selected.append(case)
        cases = selected
    if not cases:
        parser.error('no cases selected')
    if args.list:
        print(json.dumps(cases, ensure_ascii=False, indent=2))
        return 0
    report = {'schema': 1, 'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'running',
              'case_seconds': args.case_seconds, 'suite_complete': not bool(args.limit or args.only),
              'coverage': {s: dict(Counter(c['suite'] for c in cases if c['scene']['strategy'] == s)) for s in STRATEGIES},
              'timing_policy': 'native and WASM durations recorded independently, never equality-tested',
              'selected': len(cases), 'rows': [], 'failures': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')

    bundle_path = HERE / 'static/runtime/planner-bundle.json'
    engine_path = HERE / 'static/planner-engine.mjs'
    try:
        report['integrity'], _ = verify_bundle(bundle_path)
        report['engine_sha256'] = digest(engine_path.read_bytes())
        if report['integrity']['status'] != 'passed':
            report['status'] = 'failed'
            save()
            print('FAIL bundle integrity:', json.dumps(report['integrity']['errors'], ensure_ascii=False), flush=True)
            return 1
        save()
        native_rows = {}
        for i, case in enumerate(cases, 1):
            row = native_run(case, args.case_seconds)
            native_rows[case['id']] = row
            print(f'Native {i}/{len(cases)} {case["id"]}: {row["status"]}', flush=True)
        cmd = ['node', str(Path(__file__).with_name('browser_batch.mjs')), '--case-seconds', str(args.case_seconds)]
        # A file prevents a large stdin pipe from blocking while Node emits results.
        import tempfile
        with tempfile.TemporaryFile(mode='w+') as payload:
            json.dump({'cases': [{'id': c['id'], 'scene': c['scene']} for c in cases]}, payload)
            payload.seek(0)
            with subprocess.Popen(cmd, stdin=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as proc:
                by_id = {c['id']: c for c in cases}
                received = set()
                for line in proc.stdout:
                    event = json.loads(line)
                    if event['type'] != 'case':
                        if event['type'] == 'fatal':
                            report['batch_error'] = event['error']
                        continue
                    ident = event['id']
                    if ident not in by_id or ident in received:
                        raise ValueError('Unexpected/duplicate Node case: ' + ident)
                    received.add(ident)
                    case, native = by_id[ident], native_rows[ident]
                    row = {'id': ident, 'suite': case['suite'], 'scene': case['scene'], 'native_status': native['status'], 'browser_status': event['status'],
                           'native_wall_ms': native.get('wall_ms'), 'browser_wall_ms': event.get('wall_ms')}
                    errors, metrics = [], {}
                    if 'incomplete' in (native['status'], event['status']):
                        row['status'] = 'incomplete'
                    elif native['status'] != 'complete' or event['status'] != 'complete':
                        row['status'] = 'failed'
                    else:
                        try:
                            errors, metrics = compare_case(case, native['result'], event['result'])
                        except Exception:
                            errors = [{'path': 'comparison', 'error': traceback.format_exc()}]
                        row['status'] = 'failed' if errors else 'passed'
                        for name, data in (('native', native['result']), ('browser', event['result'])):
                            row[name] = {k: data.get(k) for k in ('count', 'upper', 'optimal', 'reason', 'used', 'remaining', 'layout', 'timings', 'elapsed_ms')}
                            row[name]['slots_sha256'] = json_hash(data['slots'])
                        row['pattern_metrics'] = metrics
                    if row['status'] != 'passed':
                        report['failures'].append({'id': ident, 'scene': case['scene'], 'status': row['status'], 'differences': errors,
                                                   'native': native, 'browser': event})
                        print('FIRST DETAIL' if len(report['failures']) == 1 else 'DETAIL', ident, json.dumps(errors[:6], ensure_ascii=False), flush=True)
                    report['rows'].append(row)
                    save()
                    print(f'WASM {len(received)}/{len(cases)} {ident}: {row["status"]}', flush=True)
                stderr = proc.stderr.read()
                returncode = proc.wait()
                report['node_exit_code'] = returncode
                if stderr:
                    report['node_stderr'] = stderr
                for case in cases:
                    if case['id'] not in received:
                        report['rows'].append({'id': case['id'], 'status': 'incomplete'})
                        report['failures'].append({'id': case['id'], 'status': 'incomplete', 'scene': case['scene'], 'native': native_rows[case['id']], 'error': report.get('batch_error', 'No Node response')})
        report['integrity_after'], _ = verify_bundle(bundle_path)
        if report['integrity_after'] != report['integrity'] or digest(engine_path.read_bytes()) != report['engine_sha256']:
            report['source_changed'] = True
    except (FileNotFoundError, ImportError) as exc:
        report['status'] = 'incomplete'
        report['error'] = str(exc)
        save()
        print('INCOMPLETE:', exc, flush=True)
        return 2
    except Exception:
        report['status'] = 'failed'
        report['error'] = traceback.format_exc()
        save()
        print(report['error'], flush=True)
        return 1
    report['summary'] = dict(Counter(row['status'] for row in report['rows']))
    failed = report['summary'].get('failed', 0) or report.get('source_changed') or report.get('batch_error') or report.get('node_exit_code', 0) not in (0, 2)
    incomplete = report['summary'].get('incomplete', 0) or len(report['rows']) != len(cases)
    report['status'] = 'failed' if failed else 'incomplete' if incomplete else 'passed'
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    save()
    print(json.dumps({'status': report['status'], 'suite_complete': report['suite_complete'], 'summary': report['summary'], 'output': str(args.output)}, ensure_ascii=False), flush=True)
    return 1 if failed else 2 if incomplete else 0


if __name__ == '__main__':
    raise SystemExit(native_worker() if '--native-worker' in sys.argv else main())
