"""Home-mode BG parallax analysis (docs/parallax.md). Imported by build_assets.py (zone variants,
far-layer tiles) and build_parallax.py (tables). Pure functions of the ROM set and levels.json.

Two kinds of BG parallax, both only where the arcade map allows it without touching gameplay:

* Far layer (FAR): a zone whose background is a periodic texture behind the terrain (stage 5's
  cave wall). The texture pixels are cut out of the zone's metatiles (Home variant of the zone)
  and plane A shows the texture instead of the stars, scrolled slower than plane B. The texture
  is identified by colour: the arcade draws it with its own colour set, which the rock never uses.
  The offset between the texture and the world is a stateless function of the camera that is a
  multiple of the texture period wherever cells that were *not* cut are visible, so cut and uncut
  cells always join seamlessly. Cells are only cut where needed (visible on the playfield while the
  offset is not 0) and never where they would pass under the HUD window rows (the window replaces
  plane A on its rows, so a cut texture pixel there would show black).

* Bands (BANDS): world cell rows of distant scenery on a horizontal leg, without terrain, streamed
  by bg.c at their own camera x (bx = x0 + (cam_x - x0) * num / den) and shown with plane-B line
  scroll. Checked here: no terrain, nothing visible changes at the end of the band (band and world
  agree pixel for pixel there), rows on the playfield (not under the HUD).
"""
import json, sys
from functools import lru_cache
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from arcade_source import Source, ROOT, decode_bgtiles, bgmap_cells
import zones as zonecfg

VIEW_X, VIEW_Y = 96, 16
SW, SH = 320, 224
HUD_TOP, HUD_BOT = 16, 208      # window rows 0-1 and 26-27 (always shown in play): lines [0,16) and [208,224)
GEN = ROOT / 'res/generated'

# far layers: zone name, texture estimation rect (world px), period, far speed = num/den of plane B
FAR = [
    dict(zone='s5r1', name='stage 5 cave wall', rect=(1537, 2064, 4032, 2288), period=32, num=1, den=2),
]
# wheel bosses of sections 2 and 4 (arcade scroll-copy tables $70D2, $70E2): the 8 pod sockets on the
# rim are transparent in the map (the pods are sprites orbiting over them), so the stars show through
# them, also in the wreck that stays at the next section's start. With the stars in depth layers that
# reads as scrolling inside the boss: Home fills the transparent pixels inside the wheel with the
# cell's darkest colour. (The section-9 wheel sits on opaque background.)
WHEEL_TABLES = (0x70D2, 0x70E2)
WHEEL_CENTRE = (319, 128)       # wheel centre - scroll copy position (world px)
WHEEL_R = (124, 96)             # ellipse radii (measured: rim at +-123 x, +-94 y)

# bands: zone, leg camera y, camera x range [x0, x1] (x1: band locked again), world cell rows, speed
BANDS = [
    dict(zone='s1r0', name='stage 1 Mt Fuji', cam_y=16, x0=None, x1=None, rows=(4, 4), num=3, den=4,
         find='fuji'),
    dict(zone='s1r0', name='stage 1 hills', cam_y=16, x0=None, x1=4095, rows=(2, 5), num=1, den=2,
         find='hills'),
]


@lru_cache(None)
def world():
    """4096x4096 arcade colour index image (colour*16 + pen, -1 = transparent pen 15)"""
    src = Source()
    bgt = decode_bgtiles(src.region('bgtiles'))
    code, color, flags = bgmap_cells(src.region('bgmap'))
    W = np.zeros((4096, 4096), np.int16)
    for r in range(128):
        for c in range(128):
            t = bgt[code[r, c]].astype(np.int16)
            if flags[r, c] & 1: t = t[:, ::-1]
            if flags[r, c] & 2: t = t[::-1, :]
            W[r * 32:r * 32 + 32, c * 32:c * 32 + 32] = np.where(t == 15, -1, t + 16 * color[r, c])
    return W, code, color, flags


@lru_cache(None)
def bg_tiles():
    return decode_bgtiles(Source().region('bgtiles'))


@lru_cache(None)
def wheel_fill():
    """{metatile code: 32x32 bool in metatile orientation}: the transparent pixels to fill. A pixel is
    filled only if it lies inside a wheel ellipse at every place the metatile is used in the map, so
    a changed metatile simply replaces the original (no extra metatiles: the wheel fight already
    pins 44 of bg.c's 56 cache slots) and nothing outside a wheel changes."""
    W, code, color, flags = world()
    bgt = bg_tiles()
    M = Source().region('maincpu')
    w16 = lambda a: M[a] | (M[a + 1] << 8)
    rx, ry = WHEEL_R
    inside = np.zeros(W.shape, bool)
    for tab in WHEEL_TABLES:
        for k in range(4):
            cx, cy = w16(tab + 4 * k + 2) + WHEEL_CENTRE[0], w16(tab + 4 * k) + WHEEL_CENTRE[1]
            if W[cy, cx] < 0:
                continue                        # no wheel at this copy (section 3 start)
            ys, xs = np.mgrid[cy - ry:cy + ry + 1, cx - rx:cx + rx + 1]
            inside[ys, xs] |= ((xs - cx) / rx) ** 2 + ((ys - cy) / ry) ** 2 <= 1
    out = {}
    for cd in {int(code[y >> 5, x >> 5]) for y, x in zip(*np.nonzero(inside & (W < 0)))}:
        m = bgt[cd] == 15
        for r, c in zip(*np.nonzero(code == cd)):
            m &= to_meta(inside[r * 32:r * 32 + 32, c * 32:c * 32 + 32], int(flags[r, c]))
        if m.any():
            out[cd] = m
    return out


def to_meta(mask, fl):
    """a world-oriented 32x32 mask in the orientation of the cell's metatile (map flags b0 h, b1 v)"""
    if fl & 1: mask = mask[:, ::-1]
    if fl & 2: mask = mask[::-1, :]
    return mask


def home_zones():
    """zones with a Home variant: far layers, zones using a filled wheel metatile"""
    code = world()[1]
    fill = wheel_fill()
    out = set(far_layers())
    for zi, z in enumerate(zonecfg.ZONES):
        x0, y0, w, h = z['rect']
        if np.isin(code[y0:y0 + h, x0:x0 + w], list(fill)).any():
            out.add(zi)
    return out


@lru_cache(None)
def terrain():
    t = np.frombuffer((GEN / 'terrain.bin').read_bytes(), np.uint8)
    return np.unpackbits(t).reshape(256, 256)       # [cy16][cx16]


def zone_index(name):
    return next(i for i, z in enumerate(zonecfg.ZONES) if z['name'] == name)


def legs_cam():
    """every leg as (section, (dx, dy), start cam, end cam)"""
    d = json.loads((GEN / 'levels.json').read_text())
    out = []
    for s in d['sections']:
        for leg in s['legs']:
            st = (leg['start'][0] + VIEW_X, leg['start'][1] + VIEW_Y)
            en = (leg['end'][0] + VIEW_X, leg['end'][1] + VIEW_Y)
            out.append((s['section'], tuple(leg['dir']), st, en))
    return out


def path_positions(zone_rect_px):
    """camera positions (every px) along the legs whose camera lies in the zone"""
    x0, y0, x1, y1 = zone_rect_px
    pos = []
    for sec, d, st, en in legs_cam():
        n = max(abs(en[0] - st[0]), abs(en[1] - st[1]))
        for i in range(n + 1):
            cx = st[0] + (en[0] - st[0]) * i // max(n, 1)
            cy = st[1] + (en[1] - st[1]) * i // max(n, 1)
            mx, my = cx + SW // 2, cy + SH // 2
            if x0 <= mx < x1 and y0 <= my < y1:
                pos.append((cx, cy, d))
    return pos


def texture(rect, P):
    W = world()[0]
    x0, y0, x1, y1 = rect
    Z = W[y0:y1, x0:x1]
    T = np.full((P, P), -1, np.int16)
    for py in range(P):
        for px in range(P):
            v = Z[(py - y0) % P::P, (px - x0) % P::P].ravel()
            v = v[v >= 0]
            if len(v):
                vals, c = np.unique(v, return_counts=True)
                T[py, px] = vals[c.argmax()]
    return T


def cells_in_view(cx, cy, y_lo, y_hi):
    """world cells intersecting the screen lines [y_lo, y_hi) at camera (cx, cy)"""
    if y_hi <= y_lo:
        return set()
    return {(x, y) for y in range((cy + y_lo) >> 5, ((cy + y_hi - 1) >> 5) + 1)
            for x in range(cx >> 5, ((cx + SW - 1) >> 5) + 1)}


def far_layer(cfg):
    """analysis of one far layer: texture, cut cells, offset segments, plane-A camera rect"""
    zi = zone_index(cfg['zone'])
    zx, zy, zw, zh = zonecfg.ZONES[zi]['rect']
    W = world()[0]
    P = cfg['period']
    T = texture(cfg['rect'], P)
    tcol = set(int(v) for v in np.unique(T[T >= 0]))
    zpx = (zx * 32, zy * 32, (zx + zw) * 32, (zy + zh) * 32)
    pos = path_positions(zpx)
    # cells with texture pixels
    far_cells = {}
    for y in range(zy, zy + zh):
        for x in range(zx, zx + zw):
            c = W[y * 32:y * 32 + 32, x * 32:x * 32 + 32]
            m = np.isin(c, list(tcol))
            if m.any():
                far_cells[(x, y)] = m
    # cells seen under the HUD rows / on the playfield, per camera position
    hud_seen = set()
    for cx, cy, d in pos:
        hud_seen |= cells_in_view(cx, cy, 0, HUD_TOP) | cells_in_view(cx, cy, HUD_BOT, SH)
    # parallax segments: horizontal legs; positions whose playfield shows no cell that is ever
    # under the HUD (those cells stay uncut)
    segs, cut = [], set()
    for sec, d, st, en in legs_cam():
        if d[1] != 0 or d[0] != 1:
            continue
        cy = st[1]
        if not (zpx[0] <= st[0] + SW // 2 < zpx[2] and zpx[1] <= cy + SH // 2 < zpx[3]):
            continue
        ok = []
        for cx in range(st[0], en[0] + 1):
            play = cells_in_view(cx, cy, HUD_TOP, HUD_BOT)
            ok.append(not any(c in hud_seen and c in far_cells for c in play))
        # longest run of ok positions
        best, run = None, None
        for i, v in enumerate(ok + [False]):
            if v and run is None: run = i
            if not v and run is not None:
                if best is None or i - run > best[1] - best[0]: best = (run, i)
                run = None
        if not best:
            continue
        xa, xb = st[0] + best[0], st[0] + best[1] - 1
        # offset = (cam - xa) * (den - num) / den must end on a multiple of the period
        k = cfg['den'] - cfg['num']
        step = P * cfg['den'] // np.gcd(P * cfg['den'], k)      # camera px per period of offset
        xb = xa + (xb - xa) // step * step
        if xb - xa < step:
            continue
        seg_cut = set()
        for cx in range(xa, xb + 1):
            seg_cut |= {c for c in cells_in_view(cx, cy, HUD_TOP, HUD_BOT) if c in far_cells}
        if seg_cut:                                 # legs without texture need no segment
            segs.append((int(xa), int(xb), int(cy), 0, int(k), int(cfg['den'])))
            cut |= seg_cut
    # plane A shows the texture wherever a cut cell is on the playfield
    show = [(cx, cy) for cx, cy, d in pos if any(c in cut for c in cells_in_view(cx, cy, HUD_TOP, HUD_BOT))]
    rect = (min(p[0] for p in show), min(p[1] for p in show), max(p[0] for p in show), max(p[1] for p in show))
    # checks: no star pixel (original transparent) on the playfield while plane A shows the texture,
    # and no cut cell under the HUD anywhere
    sky = 0                                         # worst view: stray transparent pixels
    for cx, cy, d in pos:
        if rect[0] <= cx <= rect[2] and rect[1] <= cy <= rect[3]:
            v = W[cy + HUD_TOP:cy + HUD_BOT, cx:cx + SW]
            sky = max(sky, int((v < 0).sum()))
    assert sky <= 16, ('stars would be hidden by the far layer', cfg['name'], sky)
    bad = len(cut & hud_seen)
    return dict(zi=zi, T=T, tcol=tcol, cut=cut, cells=far_cells, segs=segs, rect=rect, sky=sky, hud_cut=bad,
                name=cfg['name'], P=P)


@lru_cache(None)
@lru_cache(None)
def far_layers():
    return {zone_index(c['zone']): far_layer(c) for c in FAR}


# ---------------------------------------------------------------------------------------- bands
def _opaque_cols(rows):
    W = world()[0]
    return np.nonzero((W[rows[0] * 32:rows[1] * 32 + 32] >= 0).any(axis=0))[0]


def _band_find(cfg):
    """x0/x1 of the named bands, measured on the map (see BANDS)"""
    W = world()[0]
    cy0, cy1 = cfg['rows']
    if cfg['find'] == 'hills':
        # stage 1, rows 2-5: east of the sea (colour 21) and the cliff (colour 22) only the hills,
        # the far grey ground and its craters (colour 0): the band starts with the cliff out of view
        band = W[cy0 * 32:cy1 * 32 + 32] >> 4
        sea = np.nonzero(((band == 21) | (band == 22)).any(axis=0))[0]
        return dict(x0=int(sea[sea < 3000].max()) + 1, x1=cfg['x1'])
    if cfg['find'] == 'fuji':
        # stage 1, row 4: black sky but for the city's two tall towers, Mt Fuji and the cliff
        op = _opaque_cols(cfg['rows'])
        towers_end = int(op[op < 1200].max())
        fuji = (int(op[(op >= 1200) & (op < 2300)].min()), int(op[(op >= 1200) & (op < 2300)].max()))
        cliff = int(op[op >= 2300].min())
        x0 = towers_end + 1                         # camera past the towers: none in view
        # bx = x0 + (cam - x0) * num / den: Fuji has left the band window when bx > its east edge
        # (and the world window: cam > its east edge); the cliff is still out of view then
        x1 = -(-(fuji[1] + 1 - x0) * cfg['den'] // cfg['num']) + x0
        x1 = max(x1, fuji[1] + 1)
        assert x1 + SW <= cliff, ('fuji band does not fit', x0, x1, cliff)
        return dict(x0=x0, x1=x1)
    raise ValueError(cfg['find'])


@lru_cache(None)
def band_list():
    W = world()[0]
    T = terrain()
    out = []
    for cfg in BANDS:
        f = _band_find(cfg)
        x0, x1 = f['x0'], f['x1']
        cy0, cy1 = cfg['rows']
        zi = zone_index(cfg['zone'])
        zx, zy, zw, zh = zonecfg.ZONES[zi]['rect']
        x1 = min(x1, (zx + zw) * 32 - SW)
        # checks: band rows on the playfield, no terrain under the band at either camera
        sy0, sy1 = cy0 * 32 - cfg['cam_y'], cy1 * 32 + 32 - cfg['cam_y']
        assert sy0 >= HUD_TOP and sy1 <= HUD_BOT, ('band under the HUD', cfg['name'])
        ter = T[cy0 * 2:cy1 * 2 + 2, x0 >> 4:(x1 + SW + 15) >> 4]
        assert not ter.any(), ('terrain in band', cfg['name'])
        # at x1 the band must equal the world (the band locks again without a visible change)
        bx1 = x0 + (x1 - x0) * cfg['num'] // cfg['den']
        if x1 < (zx + zw) * 32 - SW:
            a = W[cy0 * 32:cy1 * 32 + 32, bx1:bx1 + SW]
            b = W[cy0 * 32:cy1 * 32 + 32, x1:x1 + SW]
            assert (a == b).all(), ('band end differs', cfg['name'], x1, bx1)
        out.append(dict(zi=zi, cam_y=cfg['cam_y'], x0=x0, x1=x1, cy0=cy0, cy1=cy1, num=cfg['num'],
                        den=cfg['den'], name=cfg['name']))
    return out


def bands():
    return [(b['zi'], b['cam_y'], b['x0'], b['x1'], b['cy0'], b['cy1'], b['num'], b['den'], b['name'])
            for b in band_list()]


if __name__ == '__main__':
    for zi, f in far_layers().items():
        print('far', f['name'], 'zone', zi, 'segments', f['segs'], 'plane-A rect', f['rect'],
              'cut cells', len(f['cut']), 'of', len(f['cells']), 'max sky px per view', f['sky'], 'cut under HUD', f['hud_cut'])
    for b in band_list():
        print('band', b)


# ------------------------------------------------------------------------ build_assets.py helpers
def home_variant(zi, code, color, flags, mid, dark_pen):
    """Home variant of zone zi: changed cells use new metatiles - far-layer texture pixels made
    transparent (cut), wheel sockets filled with dark_pen(colour). Returns (variants, zmap):
    variants = [(original meta index, 32x32 pens in metatile orientation)], zmap = the zone map
    with changed cells pointing at len(metas) + variant index."""
    f = far_layers().get(zi)
    fills = wheel_fill()
    W = world()[0]
    bgt = bg_tiles()
    x0, y0, w, h = zonecfg.ZONES[zi]['rect']
    variants, vidx, zmap = [], {}, []
    nmeta = len(mid)
    for r in range(y0, y0 + h):
        for c in range(x0, x0 + w):
            fl = int(flags[r, c])
            m = mid[(code[r, c], color[r, c])]
            e = m
            cut = f is not None and (c, r) in f['cut']
            if cut or int(code[r, c]) in fills:
                t = bgt[code[r, c]].copy()
                if cut:
                    t[to_meta(np.isin(W[r * 32:r * 32 + 32, c * 32:c * 32 + 32], list(f['tcol'])), fl)] = 15
                if int(code[r, c]) in fills:
                    t[fills[int(code[r, c])]] = dark_pen(int(color[r, c]))
                key = (m, t.tobytes())
                if key not in vidx:
                    vidx[key] = len(variants); variants.append((m, t))
                e = nmeta + vidx[key]
            zmap.append(e | ((fl & 1) << 14) | ((fl & 2) << 14))
    assert nmeta + len(variants) <= 1024, 'bg.c MAX_META'
    return variants, zmap


def far_tiles(zi, pals, MD, nearest, tile_bytes):
    """far texture -> (tile bytes, map words of one period, w, h); palette per 8x8 tile by error"""
    T = far_layers()[zi]['T']
    P = T.shape[0]
    tiles, index, words = [], {}, []
    for ty in range(P // 8):
        for tx in range(P // 8):
            blk = T[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8]
            best = None
            for p in range(len(pals)):
                err, px = 0, np.zeros((8, 8), np.int32)
                for y in range(8):
                    for x in range(8):
                        v = int(blk[y, x])
                        if v < 0:
                            continue
                        k = nearest(MD[v], pals[p]); px[y, x] = 1 + k
                        err += sum((a - b) ** 2 for a, b in zip(MD[v], pals[p][k]))
                if best is None or err < best[0]:
                    best = (err, p, px)
            _, p, px = best
            word = None
            for fl, a in ((0, px), (0x800, px[:, ::-1]), (0x1000, px[::-1, :]), (0x1800, px[::-1, ::-1])):
                tb = tile_bytes(a)
                if tb in index:
                    word = index[tb] | fl; break
            if word is None:
                index[tile_bytes(px)] = len(tiles); tiles.append(tile_bytes(px)); word = len(tiles) - 1
            words.append(word | (p << 13))          # low priority
    return b''.join(tiles), words, P // 8, P // 8
