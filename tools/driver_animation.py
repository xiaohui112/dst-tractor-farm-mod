# -*- coding: utf-8 -*-
"""ANIM v4 reader/writer and native riding-pose compositor (Python 2.7/3 stdlib).
Format reference: Klei Mod Tools / dstmodders ktools kanim_serialize.cpp.
Only animation matrices/layers are changed; character builds and skins stay native.
"""
from __future__ import print_function
import copy
import io
import json
import os
import struct
import zipfile

BANK = 'aom_tractor_driver'


def name_hash(value):
    result = 0
    for c in value.lower().encode('utf-8'):
        if not isinstance(c, int):
            c = ord(c)
        result = (c + result * 65599) & 0xffffffff
    return result


class Reader(object):
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def read(self, count):
        if count < 0 or self.pos + count > len(self.data):
            raise ValueError('Truncated animation/build data')
        value = self.data[self.pos:self.pos + count]
        self.pos += count
        return value

    def unpack(self, fmt):
        return struct.unpack('<' + fmt, self.read(struct.calcsize('<' + fmt)))

    def string(self):
        size = self.unpack('I')[0]
        if size > 1024 * 1024:
            raise ValueError('Invalid string length')
        return self.read(size).decode('utf-8')


def parse_anim(data):
    reader = Reader(data)
    if reader.read(8) != b'ANIM\x04\x00\x00\x00':
        raise ValueError('Expected ANIM v4 from the PC version of DST')
    elements, frames, events, count = reader.unpack('4I')
    animations = []
    actual = [0, 0, 0]
    for _ in range(count):
        animation = {'name': reader.string()}
        animation['facing'], animation['bank'], animation['rate'], n = reader.unpack('BIfI')
        animation['frames'] = []
        for _ in range(n):
            frame = {'bbox': reader.unpack('4f')}
            frame['events'] = [reader.unpack('I')[0] for _ in range(reader.unpack('I')[0])]
            frame['elements'] = []
            for _ in range(reader.unpack('I')[0]):
                values = reader.unpack('3I7f')
                frame['elements'].append({'symbol': values[0], 'frame': values[1], 'layer': values[2],
                                          'matrix': list(values[3:9]), 'z': values[9]})
            animation['frames'].append(frame)
            actual[0] += len(frame['elements'])
            actual[1] += 1
            actual[2] += len(frame['events'])
        animations.append(animation)
    strings = {}
    for _ in range(reader.unpack('I')[0]):
        key = reader.unpack('I')[0]
        strings[key] = reader.string()
    if reader.pos != len(data) or actual != [elements, frames, events]:
        raise ValueError('Animation counts or trailing bytes are invalid')
    return {'animations': animations, 'strings': strings}


def write_anim(bank):
    parts = [b'ANIM\x04\x00\x00\x00']
    animations = bank['animations']
    frames = [frame for anim in animations for frame in anim['frames']]
    parts.append(struct.pack('<4I', sum(len(f['elements']) for f in frames), len(frames),
                             sum(len(f['events']) for f in frames), len(animations)))
    def string(value):
        encoded = value.encode('utf-8')
        return struct.pack('<I', len(encoded)) + encoded
    for anim in animations:
        parts.append(string(anim['name']))
        parts.append(struct.pack('<BIfI', anim['facing'], anim['bank'], anim['rate'], len(anim['frames'])))
        for frame in anim['frames']:
            parts.append(struct.pack('<4fI', *(list(frame['bbox']) + [len(frame['events'])])))
            for value in frame['events']:
                parts.append(struct.pack('<I', value))
            parts.append(struct.pack('<I', len(frame['elements'])))
            for element in frame['elements']:
                values = [element['symbol'], element['frame'], element['layer']] + list(element['matrix']) + [element['z']]
                parts.append(struct.pack('<3I7f', *values))
    parts.append(struct.pack('<I', len(bank['strings'])))
    for key, value in sorted(bank['strings'].items()):
        parts.append(struct.pack('<I', key) + string(value))
    return b''.join(parts)


def build_symbols(data):
    reader = Reader(data)
    if reader.read(8) != b'BILD\x06\x00\x00\x00':
        raise ValueError('Expected BILD v6')
    count, _ = reader.unpack('2I')
    name = reader.string()
    for _ in range(reader.unpack('I')[0]):
        reader.string()
    symbols = set()
    for _ in range(count):
        symbols.add(reader.unpack('I')[0])
        frames = reader.unpack('I')[0]
        reader.read(frames * 32)
    return name, symbols


def merge_rider(native, cabin, cow_symbols, config):
    strings = dict(native['strings'])
    strings.update(cabin['strings'])
    strings[name_hash(BANK)] = BANK
    views = config['views']
    templates = {}
    for anim in cabin['animations']:
        if anim['name'] == 'idle':
            templates[anim['facing']] = anim['frames'][0]
    for mask in (5, 48, 192):
        if mask not in templates:
            raise ValueError('Cabin missing a six-facing idle: %s' % mask)
    excluded = set(cow_symbols)
    for key, value in strings.items():
        if value.lower().startswith('beefalo') or value.lower() in ('swap_saddle',):
            excluded.add(key)
    def is_head(element):
        return strings.get(element['symbol'], '').lower() in ('headbase', 'headbase_hat', 'head')
    anchors = {}
    for anim in native['animations']:
        if anim['name'] == 'idle_loop':
            head = next((e for e in anim['frames'][0]['elements'] if is_head(e)), None)
            if head:
                anchors[anim['facing']] = head['matrix'][4:6]
    if not anchors:
        raise ValueError('Native riding idle_loop/headbase not found; unsupported game assets')
    result = []
    for original in native['animations']:
        for mask, key in ((5, 'side'), (48, 'upside'), (192, 'downside'), (2, 'upside'), (8, 'downside')):
            facing = original['facing'] & mask
            if not facing:
                continue
            anim = copy.deepcopy(original)
            anim['facing'] = facing
            anim['bank'] = name_hash(BANK)
            view = views[key]
            ref = next((value for flag, value in anchors.items() if flag & facing), None)
            if ref is None:
                raise ValueError('Missing native idle anchor for facing %s' % facing)
            scale = config['driver_scale']
            dx, dy = view['neck'][0] - scale * ref[0], view['neck'][1] - scale * ref[1]
            template = templates[mask if mask in templates else (48 if mask == 2 else 192)]
            for frame in anim['frames']:
                driver = [e for e in frame['elements'] if e['symbol'] not in excluded]
                if not driver:
                    raise ValueError('No character elements remain in ' + anim['name'])
                for element in driver:
                    matrix = element['matrix']
                    element['matrix'] = [matrix[0]*scale, matrix[1]*scale, matrix[2]*scale,
                                         matrix[3]*scale, matrix[4]*scale+dx, matrix[5]*scale+dy]
                # Native z values increase toward the background; keep player part order.
                driver.sort(key=lambda e: e['z'], reverse=True)
                for i, element in enumerate(driver):
                    element['z'] = .6 - .2 * i / max(1, len(driver)-1)
                vehicle = copy.deepcopy(template['elements'])
                # Vehicle SCML names define the foreground/background groups explicitly.
                for element in vehicle:
                    name = strings.get(element['symbol'], '')
                    element['z'] = {'aom_cabin_back': 1.0, 'aom_driver_attachment_rear': 1.2,
                                    'aom_cabin_front': 0.0, 'aom_driver_attachment_front': -.2}.get(name, 0.0)
                frame['elements'] = sorted(vehicle + driver, key=lambda e: e['z'])
                # Broad, stable bounds include hats, vehicle and both attachment mounts.
                frame['bbox'] = (0.0, -120.0, 700.0, 520.0)
            result.append(anim)
    return {'animations': result, 'strings': strings}


def find_game_asset(game, filename):
    direct = [os.path.join(game, 'data', 'anim', filename), os.path.join(game, 'anim', filename)]
    for path in direct:
        if os.path.isfile(path):
            return path, None
    # Some game installations bundle anim/*.zip inside databundles.
    for folder in (os.path.join(game, 'data', 'databundles'), os.path.join(game, 'databundles')):
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                if not name.lower().endswith('.zip') or 'anim' not in name.lower():
                    continue
                path = os.path.join(folder, name)
                with zipfile.ZipFile(path) as archive:
                    matches = [n for n in archive.namelist() if n.replace('\\', '/').split('/')[-1] == filename]
                    if matches:
                        return path, matches[0]
    raise ValueError('Cannot find native game asset: ' + filename)


def read_game_zip(game, filename):
    path, nested = find_game_asset(game, filename)
    if nested:
        with zipfile.ZipFile(path) as archive:
            return zipfile.ZipFile(io.BytesIO(archive.read(nested)))
    return zipfile.ZipFile(path)


def native_riding_bank(game):
    import fnmatch
    candidates = []
    for folder in (os.path.join(game, 'data', 'anim'), os.path.join(game, 'anim')):
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                if fnmatch.fnmatch(name.lower(), 'player_mount*.zip') or name.lower() == 'wilsonbeefalo.zip':
                    candidates.append((os.path.join(folder, name), None))
    for folder in (os.path.join(game, 'data', 'databundles'), os.path.join(game, 'databundles')):
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                if not name.lower().endswith('.zip') or 'anim' not in name.lower():
                    continue
                path = os.path.join(folder, name)
                with zipfile.ZipFile(path) as archive:
                    for entry in archive.namelist():
                        base = entry.replace('\\', '/').split('/')[-1].lower()
                        if fnmatch.fnmatch(base, 'player_mount*.zip') or base == 'wilsonbeefalo.zip':
                            candidates.append((path, entry))
    combined = {'animations': [], 'strings': {}}
    seen = {}
    sources = []
    for path, nested in candidates:
        if nested:
            with zipfile.ZipFile(path) as outer:
                data = io.BytesIO(outer.read(nested))
        else:
            data = path
        with zipfile.ZipFile(data) as archive:
            if 'anim.bin' not in archive.namelist():
                continue
            bank = parse_anim(archive.read('anim.bin'))
        for anim in bank['animations']:
            if anim['bank'] != name_hash('wilsonbeefalo'):
                continue
            key = (anim['name'], anim['facing'])
            if key in seen:
                if seen[key] != anim:
                    raise ValueError('Conflicting native riding animation: %s/%s' % key)
                continue
            seen[key] = anim
            combined['animations'].append(anim)
        combined['strings'].update(bank['strings'])
        sources.append(nested or os.path.basename(path))
    required = set(('idle_loop', 'mount', 'dismount', 'run_pre', 'run_loop', 'run_pst'))
    missing = required - set(anim['name'] for anim in combined['animations'])
    if missing:
        raise ValueError('Native player_mount*.zip missing required riding animations: ' + ', '.join(sorted(missing)))
    return combined, sources


def build_driver(game, mod, config_path):
    with open(config_path, 'r') as source:
        config = json.load(source)
    native, sources = native_riding_bank(game)
    with read_game_zip(game, 'beefalo_build.zip') as archive:
        _, cow = build_symbols(archive.read('build.bin'))
    cabin_path = os.path.join(mod, 'anim', 'aom_tractor_cabin.zip')
    with zipfile.ZipFile(cabin_path) as archive:
        cabin = parse_anim(archive.read('anim.bin'))
        data = dict((name, archive.read(name)) for name in archive.namelist())
    name, symbols = build_symbols(data['build.bin'])
    owned = set(name_hash(value) for value in ('aom_cabin_back', 'aom_cabin_front',
                'aom_driver_attachment_rear', 'aom_driver_attachment_front'))
    if name != 'aom_tractor_cabin' or not owned.issubset(symbols):
        raise ValueError('Compiled cabin build or symbols do not match the driver project')
    textures = [content for name, content in data.items() if name.lower().endswith('.tex')]
    if not textures or any(content[:4] != b'KTEX' for content in textures):
        raise ValueError('Compiled cabin texture atlas missing or invalid')
    merged = merge_rider(native, cabin, cow, config)
    data['anim.bin'] = write_anim(merged)
    parse_anim(data['anim.bin'])
    target = os.path.join(mod, 'anim', BANK + '.zip')
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(data.items()):
            archive.writestr(name, content)
    manifest = os.path.join(mod, 'scripts', 'aom_driver_visual_bank.lua')
    with io.open(manifest, 'w', encoding='utf-8') as output:
        output.write(u'-- Generated by the Windows driver builder.\nreturn { available=true, bank="aom_tractor_driver", build="aom_tractor_cabin" }\n')
    report = {'native_sources': sources, 'native_animation_count': len(native['animations']),
              'driver_animation_count': len(merged['animations']), 'native_stategraph': True,
              'character_build_preserved': True, 'six_facing': True}
    with io.open(os.path.join(mod, 'Driver-Build-Report.json'), 'w', encoding='utf-8') as output:
        output.write(json.dumps(report, ensure_ascii=False, indent=2) + u'\n')
    print('Built:', target, '- native riding timelines:', len(native['animations']),
          '- driver facing variants:', len(merged['animations']))
    return target


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', required=True)
    parser.add_argument('--mod', required=True)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    build_driver(args.game, args.mod, args.config)
