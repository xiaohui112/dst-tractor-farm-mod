"""Read-only inspection of the local macOS x64 DST 762172 binary.

Run with outputs/cpsat-venv/bin/python. Writes evidence beside this script;
does not launch DST or modify any Mod/runtime/snapshot files.
Addresses below are specific to the recorded binary SHA-256.
"""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BIN = Path.home() / "Library/Application Support/Steam/steamapps/common/Don't Starve Together/dontstarve_steam.app/Contents/MacOS/dontstarve_dedicated_server_nullrenderer"
data = BIN.read_bytes()
# Mach-O segment address mapping: locate FindEntities' Lua registration entry.
assert struct.unpack_from('<I', data)[0] == 0xfeedfacf
segments = []
offset = 32
for _ in range(struct.unpack_from('<I', data, 16)[0]):
    command, size = struct.unpack_from('<II', data, offset)
    if command == 0x19:
        vm, vmsize, fileoff, filesize = struct.unpack_from('<QQQQ', data, offset + 24)
        segments.append((vm, fileoff, filesize))
    offset += size
name_offset = data.index(b'FindEntities\0')
name_vm = next(vm + name_offset - off for vm, off, size in segments
               if off <= name_offset < off + size)
refs = []
start = 0
needle = struct.pack('<Q', name_vm)
while True:
    pos = data.find(needle, start)
    if pos < 0:
        break
    refs.append({'file_offset': hex(pos), 'function_vm': hex(struct.unpack_from('<Q', data, pos + 8)[0])})
    start = pos + 1
assert any(r['function_vm'] == '0x1001ebd10' for r in refs), 'Different binary: re-discover function addresses'
ranges = [
    ('Transform.SetPosition', 0x100172314, 0x1001723A0),
    ('Transform.GetWorldPosition', 0x1001724FC, 0x100172580),
    ('FindEntities Lua wrapper', 0x1001EBD10, 0x1001EBF05),
    ('Query context / radius squared', 0x1001C570C, 0x1001C57B0),
    ('Query context / grid call', 0x1001C5880, 0x1001C5942),
    ('Grid candidate loop', 0x1001C5A90, 0x1001C5B10),
    ('Candidate distance, tags, append', 0x1001CBDCE, 0x1001CBF91),
]
assembly = []
for label, lo, hi in ranges:
    r = subprocess.run(['xcrun', 'llvm-objdump', '-d',
                        '--start-address=' + hex(lo), '--stop-address=' + hex(hi),
                        '--no-show-raw-insn', str(BIN)], capture_output=True, text=True, check=True)
    assembly.append(label + '\n' + r.stdout)
(OUT / 'native-disassembly.txt').write_text('\n'.join(assembly))

def f32(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]

def engine_d2(p, q):
    # subss/mulss/addss order observed at 0x1001cbdf2..0x1001cbe28.
    dx, dy, dz = (f32(f32(a) - f32(b)) for a, b in zip(p, q))
    return f32(f32(dz * dz) + f32(f32(dx * dx) + f32(dy * dy)))

a, b = 8 + 4 / 3, 4 + 4 / 3
result = {
    'evidence_type': 'static binary inspection plus IEEE-754 float32 emulation; no successful live query',
    'binary': str(BIN), 'sha256': hashlib.sha256(data).hexdigest(),
    'version_from_startup_log': '762172', 'registration': refs,
    'example': {'lua_x1': a, 'lua_x2': b, 'lua_double_d2': (a-b)**2,
                'stored_x1': f32(a), 'stored_x2': f32(b),
                'float32_delta': f32(f32(a)-f32(b)),
                'float32_d2': engine_d2((a, 0, 0), (b, 0, 0))},
    'boundary_cases': [
        {'input_x': x, 'stored_x': f32(x), 'd2': engine_d2((0, 0, 0), (x, 0, 0)),
         'passes_distance_filter': engine_d2((0, 0, 0), (x, 0, 0)) <= 16}
        for x in [4, 4.000000000000001, 4.0000001, 4.000000476837158]
    ],
}
sys.path.insert(0, str(ROOT / 'tools/cpsat_benchmark'))
import benchmark as bench
bench.FLOAT_MODEL = 'legacy-double'  # Preserve this historical input experiment.
snapshot = ROOT / 'outputs/cpsat-comparison/source-snapshot'
assert snapshot.exists()
bench.freeze(snapshot)
case = next(c for c in bench.scenarios() if c['id'] == 'autumn/square-3/all-40/GIANT')
_, slots = bench.context(case)
board = json.loads((OUT / 'result.json').read_text())['board']
missing, extra, changed, failures = [], [], [], []
for i, p in enumerate(slots):
    neighbors = 0
    crop = board[i]
    rule = bench.audit.RULES[crop]
    for j, q in enumerate(slots):
        d2 = engine_d2((p['x'], 0, p['z']), (q['x'], 0, q['z']))
        ideal = sum((round(p[k]*.75)-round(q[k]*.75))**2 for k in ('x', 'z')) <= 9
        double = sum((p[k]-q[k])**2 for k in ('x', 'z')) <= 16
        if ideal and d2 > 16:
            missing.append([i, j])
        if not ideal and d2 <= 16:
            extra.append([i, j])
        if double != (d2 <= 16):
            changed.append([i, j])
        if board[j] == crop and d2 <= f32(f32(rule['radius'])**2):
            neighbors += 1
    if neighbors < rule['minimum']:
        failures.append({'slot': i, 'crop': crop, 'neighbors_including_self': neighbors})
result['autumn_3x3_origin_grid'] = {
    'missing_directed_edges_vs_ideal': len(missing),
    'extra_directed_edges_vs_ideal': len(extra),
    'changed_directed_edges_vs_double': len(changed),
    'prior_81_candidate_family_failures': failures,
}
(OUT / 'native-float32-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
