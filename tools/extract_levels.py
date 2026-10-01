#!/usr/bin/env python3
"""Extract Side Arms stage/camera/collision data from the original ROM -> res/generated/levels.json.

Development-only (reads the hash-checked ROM via arcade_source.Source). See docs/re/levels.md.

Decoded structures (main CPU region: $0000-$7FFF fixed, bank n at 0x8000+n*0x4000):
* Scroll script   bank 1 $815C-$A407 (B1), pointer RAM $E090, interpreter $2044-$211F.
                  Records {cmd, trig, lo, hi}; cmd $FF = 2-byte page marker {FF, FF}.
                  A record fires when low byte of the moving-axis scroll coordinate
                  ($E092 if X dir $E089 != 0, else $E094) == trig.
                    $FE       call lo|hi with bank 0 mapped (via RAM 'call nn' at $E0F8)
                    $FB-$FD   spawn task in slot 3/4/5 at lo|hi
                    $FF       end of 256-px page (advance 2, stop for this tick)
                    other     spawn 32-byte object template lo|hi into $FF00 slots;
                              cmd = y (X scrolling) or x*2 (Y scrolling)
* Section table   $15B4: 16 words; DSW1 (~$C804 & $0F) index when debug DSW0.7 is on ($1594).
* Command library bank 0 $8000-$8330 (B0) + boss spawners in fixed ROM.
* Wheel-boss tables $70D2/$70E2/$70F2 (fixed): 3 animation frames (Y,X) + death destination.
* BG collision    bank 2 $A000-$BFFF (B2): 1 bit per 16x16 world cell, tested at B2:$84B5 /
                  $07C0 / $082F / B2:$949C.

The script is simulated at 1 scroll px per 2 frames with each boss halt cleared immediately.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from arcade_source import Source, ROOT

SCRIPT_START, SCRIPT_BANK = 0x815C, 1
SECTION_TABLE = 0x15B4
SCRIPT_END = 0xA406            # after the final halt record only $FF padding follows
SCREEN_W, SCREEN_H = 384, 224
VIS_X0, VIS_Y0 = 64, 16           # visible window offset inside the scrolled tilemap (MAME raw screen)
WHEEL = {0x7192: (0x61, 0x70D2), 0x719C: (0x62, 0x70E2), 0x71A6: (0x63, 0x70F2)}
FINAL_BOSS = 0x5FC3


class Rom:
    def __init__(self):
        self.r = Source().region('maincpu')
        assert len(self.r) >= 0x18000, len(self.r)  # fixed 32K + banks 0-3 (4-7 unpopulated)

    def b(self, bank, addr):
        return self.r[addr] if addr < 0x8000 else self.r[0x8000 + bank * 0x4000 + addr - 0x8000]

    def w(self, bank, addr):
        return self.b(bank, addr) | self.b(bank, addr + 1) << 8


def decode_library(rom):
    """Classify FE call targets by matching their code bytes."""
    lib = {}
    for a in range(0x8000, 0x8340):
        b = [rom.b(0, a + i) for i in range(13)]
        # ld hl,Y ; ld ($E094),hl ; ld hl,X ; ld ($E092),hl ; ret
        if b[0] == 0x21 and b[3:6] == [0x22, 0x94, 0xE0] and b[6] == 0x21 and b[9:12] == [0x22, 0x92, 0xE0] and b[12] == 0xC9:
            lib[a] = {'op': 'teleport', 'y': b[1] | b[2] << 8, 'x': b[7] | b[8] << 8}
        # ld a,n ; ld ($E08A/$E08B),a   (Y / X direction latch)
        if b[0] == 0x3E and b[2] == 0x32 and b[4] == 0xE0 and b[3] in (0x8A, 0x8B) and b[1] in (0, 1, 0xFF):
            lib[a] = {'op': 'dir_y' if b[3] == 0x8A else 'dir_x', 'dir': {0: 0, 1: 1, 0xFF: -1}[b[1]]}
        # ld a,n ; ld ($E048),a ; ret
        if b[0] == 0x3E and b[2:5] == [0x32, 0x48, 0xE0] and b[5] == 0xC9:
            lib[a] = {'op': 'set_E048', 'value': b[1]}
        # ld a,n ; ld hl,tbl ; jr $810E  -> stage music (sound command n) + $E050 table per DSW0
        if b[0] == 0x3E and b[2] == 0x21 and (b[5] == 0x18 or a == 0x8109) and 0x80CA <= a <= 0x810B:
            lib[a] = {'op': 'music', 'sound': b[1]}
        # ld c,n ; jr $8032 -> rank $E017 = c + table $8049[~DSW0 & 7]
        if b[0] == 0x0E and b[2] == 0x18 and a < 0x8031 and a + 4 + (b[3] - 256 if b[3] > 127 else b[3]) == 0x8032:
            lib[a] = {'op': 'rank', 'base': b[1]}
    lib[0x8030] = {'op': 'rank', 'base': rom.b(0, 0x8031)}
    lib[0x8051] = {'op': 'resume'}
    lib[0x8057] = {'op': 'halt'}
    for a, hl in ((0x8069, 0x1E), (0x806E, 0x96), (0x8073, 0x12C), (0x8078, 0x258), (0x807D, 0x384), (0x8082, 0x708)):
        lib[a] = {'op': 'pause', 'ticks': hl}
    # sprite bosses: ld a,$13; call $02F3; ld a,$3n; call $02F3; ld hl,tmpl; ld de,$FB00
    for a in range(0x100, 0x7FF0):
        b = [rom.b(0, a + i) for i in range(16)]
        if b[0] == 0x3E and b[2:5] == [0xCD, 0xF3, 0x02] and b[5] == 0x3E and b[7:10] == [0xCD, 0xF3, 0x02] \
                and b[10] == 0x21 and b[13:16] == [0x11, 0x00, 0xFB]:
            lib[a] = {'op': 'boss', 'kind': 'sprite', 'sound': b[6], 'template': f'{b[11] | b[12] << 8:04X}', 'object': 'FB00'}
    for a, (sel, tbl) in WHEEL.items():
        # ld a,5 ; ld bc,task ; call $00EF  -> task $3B3A/$3B42/$3B4A sets $E0D0 when halted
        assert rom.b(0, a) == 0x3E and rom.b(0, a + 2) == 0x01, hex(a)
        frames = [{'y': rom.w(0, tbl + 4 * k), 'x': rom.w(0, tbl + 4 * k + 2)} for k in range(3)]
        death = {'y': rom.w(0, tbl + 12), 'x': rom.w(0, tbl + 14)}
        lib[a] = {'op': 'boss', 'kind': 'bg_wheel', 'E0D0': sel, 'task': f'{rom.w(0, a + 3):04X}',
                  'anim_scroll': frames, 'death_scroll': death, 'sound': 0x35}
    assert rom.b(0, FINAL_BOSS) == 0xFD   # ld iy,$F600 ...
    lib[FINAL_BOSS] = {'op': 'boss', 'kind': 'final', 'objects': 'F600 x8', 'death_task': '3B8A'}
    return lib


def scan_script(rom, start=SCRIPT_START):
    recs, a = [], start
    while a < 0xC000:
        c = rom.b(SCRIPT_BANK, a)
        if c == 0xFF:
            recs.append((a, 0xFF, rom.b(SCRIPT_BANK, a + 1), None)); a += 2
        else:
            recs.append((a, c, rom.b(SCRIPT_BANK, a + 1), rom.w(SCRIPT_BANK, a + 2))); a += 4
    return recs


def simulate(lib, recs):
    """Run the script from power-on game start: X=Y=0, X dir +1 ($1580-$15B1, $0D77)."""
    x = y = 0
    lx, ly = 1, 0
    frame, i = 0, 0
    events, last_boss = [], None
    while i < len(recs):
        dx, dy = lx, ly                     # $1FB7: $E08A/$E08B -> $E088/$E089 each loop
        y = (y + dy) & 0xFFF
        x = (x + dx) & 0xFFF
        frame += 2                          # $1FE5: scroll only on odd $E003 (every other loop)
        while i < len(recs):
            a, c, t, p = recs[i]
            cur = (x if dx else y if dy else None)
            if cur is None or (cur & 0xFF) != t:
                break
            i += 1
            if c == 0xFF:
                break
            ev = {'ptr': f'{a:04X}', 'frame': frame, 'x': x, 'y': y}
            if c == 0xFE:
                info = lib.get(p, {'op': 'spawn_call'})
                ev.update(info); ev['target'] = f'{p:04X}'
                op = info['op']
                if op == 'teleport':
                    x, y = info['x'], info['y']
                elif op == 'dir_x':
                    lx = info['dir']
                elif op == 'dir_y':
                    ly = info['dir']
                elif op == 'boss':
                    last_boss = info
                elif op == 'halt':
                    ev['boss'] = last_boss and last_boss['kind']
                    if last_boss and last_boss['kind'] == 'bg_wheel':   # death handler $7511
                        x, y = last_boss['death_scroll']['x'], last_boss['death_scroll']['y']
                        ev['after_death_scroll'] = last_boss['death_scroll']
                    if last_boss and last_boss['kind'] == 'final':
                        events.append(ev)
                        return events
                    last_boss = None
            elif c in (0xFB, 0xFC, 0xFD):
                ev.update({'op': 'spawn_task', 'slot': c - 0xF8, 'entry': f'{p:04X}'})
            else:
                ev.update({'op': 'spawn_object', 'pos': c, 'template': f'{p:04X}'})
            events.append(ev)
    return events


def collision_map(rom):
    """B2:$A000: per 256-px band (Y>>8) $200 bytes; per 16-px column 2 bytes (rows 0-7, 8-15),
    bit (7-row). Returns 256 rows of 256 cells (world px = cell*16)."""
    rows = [[0] * 256 for _ in range(256)]
    for band in range(16):
        for col in range(256):
            for half in range(2):
                v = rom.b(2, 0xA000 + band * 0x200 + col * 2 + half)
                for k in range(8):
                    if v >> (7 - k) & 1:
                        rows[band * 16 + half * 8 + k][col] = 1
    return rows


def main():
    rom = Rom()
    lib = decode_library(rom)
    table = [rom.w(0, SECTION_TABLE + 2 * k) for k in range(16)]
    starts = []
    for p in table[1:]:
        if p not in starts:
            starts.append(p)
    starts = sorted(starts)                       # $815C, $84D6 ... $A3E2 (10 sections)
    recs = scan_script(rom)
    events = simulate(lib, recs)
    ctrl_ops = ('teleport', 'dir_x', 'dir_y', 'music', 'rank', 'boss', 'halt', 'pause', 'resume')

    # section k = script records [start_k, start_k+1); the teleport that closes the previous
    # section (record at start_k - 4) belongs to section k, and the debug-start duplicate at
    # start_k fires in the same tick at the same place (kept, harmless).
    first_ptr = []
    for lo in starts:
        prev = [r for r in recs if r[0] == lo - 4]
        is_tp = prev and prev[0][1] == 0xFE and lib.get(prev[0][3], {}).get('op') == 'teleport'
        first_ptr.append(lo - 4 if is_tp else lo)
    first_ptr.append(0xC000)
    dense = dense_positions(lib, recs)
    sections = []
    for n, lo in enumerate(starts):
        ev = [e for e in events if first_ptr[n] <= int(e['ptr'], 16) < first_ptr[n + 1]]
        ctrl = [e for e in ev if e['op'] in ctrl_ops]
        f0 = ev[0]['frame']
        f1 = events[[i for i, e in enumerate(events) if int(e['ptr'], 16) >= first_ptr[n + 1]][0]]['frame'] \
            if n + 1 < len(starts) else ev[-1]['frame']
        halts = [e for e in ctrl if e['op'] == 'halt']
        bosses = [dict(at=[e['x'], e['y']], frame=e['frame'] - f0, **{k: e[k] for k in ('kind', 'target')})
                  for e in ctrl if e['op'] == 'boss']
        sections.append({
            'section': n + 1,
            'debug_dsw1_index': table.index(lo),
            'script': [f'{lo:04X}', f'{starts[n + 1] if n + 1 < len(starts) else 0xC000:04X}'],
            'pages': sum(1 for r in recs if lo <= r[0] < min(first_ptr[n + 1], SCRIPT_END) and r[1] == 0xFF),
            'spawn_records': sum(1 for e in ev if e['op'].startswith('spawn')),
            'start_scroll': [ev[0]['x'], ev[0]['y']],
            'frame_start': f0, 'frame_end': f1, 'frames_nominal': f1 - f0,
            'music': [e['sound'] for e in ctrl if e['op'] == 'music'],
            'bosses': bosses,
            'halts': [[e['x'], e['y']] for e in halts],
            'legs': legs_for(dense, f0, f1),
            'control': ctrl,
        })

    out = {
        'source': 'Side Arms (MAME sidearms) main CPU; see docs/re/levels.md',
        'scroll': {
            'ram_x': 'E092', 'ram_y': 'E094', 'px_per_frame_nominal': 0.5,
            'note': '1 px per 2 main-loop iterations ($E003 odd); slows under CPU load',
            'visible_window': {'x': VIS_X0, 'y': VIS_Y0, 'w': SCREEN_W, 'h': SCREEN_H},
            'mode_ram': 'E080', 'modes': {'80': 'scrolling', '40': 'halted (boss)', '20': 'timed pause ($E084 ticks)'},
            'dir_ram': {'y': 'E088 (latch E08A)', 'x': 'E089 (latch E08B)'},
            'starfield': '+1 $C805 (X) / $C806 (Y) write every 4 frames while that axis moves; direction-independent',
        },
        'section_table_15B4': [f'{p:04X}' for p in table],
        'library': {f'{k:04X}': v for k, v in sorted(lib.items())},
        'sections': sections,
        'collision': {'source': 'B2:A000-BFFF', 'cell_px': 16, 'w': 256, 'h': 256,
                      'rows_hex': [''.join('%x' % int(''.join(map(str, row[c:c + 4])), 2) for c in range(0, 256, 4))
                                   for row in collision_map(rom)]},
    }
    dst = ROOT / 'res/generated/levels.json'
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, indent=1))
    for s in sections:
        print(f"section {s['section']:2d} script {s['script'][0]}-{s['script'][1]} start={s['start_scroll'][0]:03X},{s['start_scroll'][1]:03X} "
              f"frames={s['frames_nominal']} music={s['music']} bosses={[(b['kind'], b['target'], '%03X,%03X' % tuple(b['at'])) for b in s['bosses']]}")
        for L in s['legs']:
            print(f"     +{L['frame']:5d} {L['start'][0]:03X},{L['start'][1]:03X} -> {L['end'][0]:03X},{L['end'][1]:03X} dir={L['dir']} {L['frames']}f rect={L['world_rect']}")
    print('wrote', dst)


def legs_for(dense, f0, f1):
    """Straight camera legs in [f0, f1): start/end scroll, direction, frames and the world-pixel
    rectangle [x0, y0, x1, y1) swept by the visible window (may exceed 4096 = tilemap wrap)."""
    pts = [(f, x, y) for f, x, y in dense if f0 <= f < f1]
    legs, cur = [], None
    for (f, x, y) in pts:
        if cur:
            dx, dy = x - cur['_x'], y - cur['_y']
            step = (dx, dy)
            if abs(dx) > 1 or abs(dy) > 1 or (cur['dir'] is not None and step != cur['dir'] and step != (0, 0)):
                legs.append(cur); cur = None
            else:
                if step != (0, 0):
                    cur['dir'] = step
                cur['_x'], cur['_y'], cur['end'], cur['frames'] = x, y, [x, y], f - cur['f']
                continue
        cur = {'f': f, 'start': [x, y], 'end': [x, y], 'dir': None, 'frames': 0, '_x': x, '_y': y}
    if cur:
        legs.append(cur)
    out = []
    for L in legs:
        (sx, sy), (ex, ey) = L['start'], L['end']
        if L['dir'] and L['dir'][0] < 0: sx, ex = ex, sx
        if L['dir'] and L['dir'][1] < 0: sy, ey = ey, sy
        out.append({'frame': L['f'] - f0, 'start': L['start'], 'end': L['end'],
                    'dir': list(L['dir'] or (0, 0)), 'frames': L['frames'],
                    'world_rect': [sx + VIS_X0, sy + VIS_Y0, ex + VIS_X0 + SCREEN_W, ey + VIS_Y0 + SCREEN_H]})
    return [o for o in out if o['frames'] > 0]


def dense_positions(lib, recs):
    """Scroll position each tick (frame, x, y), same rules as simulate()."""
    out = []
    x = y = 0
    lx, ly = 1, 0
    frame, i, last_boss = 0, 0, None
    while i < len(recs):
        dx, dy = lx, ly
        y = (y + dy) & 0xFFF; x = (x + dx) & 0xFFF; frame += 2
        while i < len(recs):
            a, c, t, p = recs[i]
            cur = (x if dx else y if dy else None)
            if cur is None or (cur & 0xFF) != t:
                break
            i += 1
            if c == 0xFF:
                break
            if c == 0xFE and p in lib:
                info = lib[p]; op = info['op']
                if op == 'teleport':
                    x, y = info['x'], info['y']
                elif op == 'dir_x':
                    lx = info['dir']
                elif op == 'dir_y':
                    ly = info['dir']
                elif op == 'boss':
                    last_boss = info
                elif op == 'halt':
                    if last_boss and last_boss['kind'] == 'bg_wheel':
                        x, y = last_boss['death_scroll']['x'], last_boss['death_scroll']['y']
                    if last_boss and last_boss['kind'] == 'final':
                        out.append((frame, x, y)); return out
                    last_boss = None
        out.append((frame, x, y))
    return out


if __name__ == '__main__':
    main()
