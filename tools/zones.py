"""Background palette zones: one per continuous scroll run (legs joined without a
teleport) from res/generated/levels.json (docs/re/levels.md). A zone switch
(palette load + cache flush) therefore only happens at a teleport, where the
arcade screen cuts anyway. Rects are in 32x32 world cells."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The intro/attract/ranking screens show fixed views; covered by explicit zones.
EXTRA = [
    ('title_city', (448, 16, 832, 240)),          # ranking screen city (scroll 384,0)
    ('earth', (2816, 3584 - 0, 4096, 4096)),     # Earth intro picture
]


def _runs():
    d = json.loads((ROOT / 'res/generated/levels.json').read_text())
    runs = []
    for s in d['sections']:
        cur = None
        for leg in s['legs']:
            st, en = leg['start'], leg['end']
            if cur and abs(st[0] - cur['end'][0]) <= 1 and abs(st[1] - cur['end'][1]) <= 1:
                cur['rects'].append(leg['world_rect']); cur['end'] = en
            else:
                cur = {'name': f"s{s['section']}r{len([r for r in runs if r['section'] == s['section']])}",
                       'section': s['section'], 'start': st, 'end': en, 'rects': [leg['world_rect']]}
                runs.append(cur)
    return runs


def _cells(px):
    x0 = min(r[0] for r in px); y0 = min(r[1] for r in px)
    x1 = max(r[2] for r in px); y1 = max(r[3] for r in px)
    c0, r0 = max(0, x0 // 32), max(0, y0 // 32)
    c1, r1 = min(128, (x1 + 31) // 32 + 1), min(128, (y1 + 31) // 32 + 1)
    return (c0, r0, c1 - c0, r1 - r0)


ZONES = []
for run in _runs():
    ZONES.append({'name': run['name'], 'rect': _cells(run['rects']), 'start': run['start']})
for name, r in EXTRA:
    ZONES.append({'name': name, 'rect': _cells([r]), 'start': None})

if __name__ == '__main__':
    for i, z in enumerate(ZONES):
        print(i, z)
