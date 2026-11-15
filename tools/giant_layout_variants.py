"""Deterministic, regular nine-slot layouts. Legacy IDs and coordinates remain unchanged."""
from copy import deepcopy
from functools import reduce
from math import gcd

CROP_ORDER = ('carrot', 'corn', 'potato', 'tomato', 'asparagus', 'eggplant',
              'pumpkin', 'watermelon', 'dragonfruit', 'durian', 'garlic', 'onion',
              'pepper', 'pomegranate')


def _slots(rows, width, height):
    return [dict(tx=tx, tz=tz, x=(i % 3 - 1) * 4 / 3,
                 z=(i // 3 - 1) * 4 / 3, crop=crop or False)
            for tz in range(height) for tx in range(width)
            for i, crop in enumerate(rows[tz * width + tx])]


def _mirror(row):
    return [row[z * 3 + x] for z in range(3) for x in (2, 1, 0)]


def make_variant(base, consume, dense=False):
    """Create only proven ratio classes; the native runtime validator remains authoritative."""
    if (base.get('reference_only') or base.get('shape') != 'grid'
            or base.get('not_giant') or base.get('width') not in (1, 2)
            or base.get('height') not in (1, 2)):
        return None
    w, h = base['width'], base['height']
    ratio = base['ratio']
    crops = [c for c in CROP_ORDER if c in ratio]
    common = reduce(gcd, ratio.values())
    primitive = sorted(n // common for n in ratio.values())
    area = w * h
    old_total = sum(ratio.values())
    target = area * 9 if dense else old_total
    if dense and (target <= old_total or any(n * target % old_total for n in ratio.values())):
        return None
    needs = {c: n * target // old_total for c, n in ratio.items()}
    rows = None
    style = 'rows'
    if primitive == [1, 1]:
        if dense:
            return None  # An odd number of plants cannot have equal counts on each tile.
        a, b = crops
        rows = [[a, a, a, a, False, b, b, b, b] for _ in range(area)]
    elif primitive == [1, 1, 1]:
        a, b, c = crops
        if dense:
            rows = [[a] * 3 + [b] * 3 + [c] * 3 for _ in range(area)]
        elif w == 2:
            left = [False, a, a, False, b, b, False, c, c]
            rows = [row for _ in range(h) for row in (left, _mirror(left))]
            style = 'paired-rows'
    elif primitive == [1, 2]:
        a = next(c for c in crops if ratio[c] == max(ratio.values()))
        b = next(c for c in crops if c != a)
        if dense:
            rows = [[a] * 6 + [b] * 3 for _ in range(area)]
        elif w == 2:
            left = [False, a, a, False, a, a, False, b, b]
            rows = [row for _ in range(h) for row in (left, _mirror(left))]
            style = 'paired-rows'
    elif primitive == [1, 1, 2]:
        if dense:
            return None  # The per-tile balanced count is a multiple of four.
        a = next(c for c in crops if ratio[c] == max(ratio.values()))
        b, c = [k for k in crops if k != a]
        if w == 2:
            left = [a, a, b, a, False, b, a, c, c]
            rows = [row for _ in range(h) for row in (left, _mirror(left))]
            style = 'paired-centre-gap'
    elif primitive == [1, 1, 1, 1] and w == h == 2:
        if dense:
            # The four crops consist of two low single-channel consumers and one
            # high consumer opposite a low dual-channel consumer. Three tiles
            # use 3A+3B+2C+D, the last uses 3C+6D; global counts are 9 each.
            high = [c for c in crops if sum(consume[c]) == 8]
            if len(high) != 1:
                return None
            c = high[0]
            def delta(k):
                v = consume[k]
                back = sum(v) // v.count(0)
                return [-n if n else back for n in v]
            d = next((k for k in crops if k != c and
                      all(x == -2 * y for x, y in zip(delta(c), delta(k)))), None)
            if d is None:
                return None
            a, b = [k for k in crops if k not in (c, d)]
            rows = [[a, a, a, b, b, b, c, c, d],
                    [a, a, a, b, b, b, c, d, c],
                    [a, a, a, b, b, b, c, c, d],
                    [c, d, d, c, d, d, c, d, d]]
            style = 'four-crop-bands'
        else:
            a, b, c, d = crops
            rows = [[a, a, b, d, False, b, d, c, c] for _ in range(4)]
            style = 'four-crop-ring'
    if rows is None:
        return None
    entry = deepcopy(base)
    entry.update(id=base['id'] + ('-dense' if dense else '-regular'),
                 parent_id=base['id'], ratio=needs,
                 slots=_slots(rows, w, h), layout_style=style,
                 variant_kind='dense' if dense else 'regular')
    return entry


def enhance_catalog(data, consume):
    """Append variants without replacing any legacy ID, quota, or saved slot index."""
    for entries in data.values():
        seen = set()
        additions = []
        for base in entries:
            if base.get('variant_kind'):
                continue
            for dense in (False, True):
                entry = make_variant(base, consume, dense)
                if entry is None:
                    continue
                signature = (entry['width'], entry['height'],
                             tuple(sorted(entry['ratio'].items())), dense)
                if signature in seen:
                    continue
                seen.add(signature)
                additions.append(entry)
        entries.extend(additions)
    return data
