"""Independently verify source-exact Normal sprite repair and BC isolation."""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile

import numpy as np
from arcade_source import ROOT, Source, decode_sprites, palette_rgb
from quantize import to_md
from vivid_palette import index


def pens(raw, size):
    out = np.zeros((size, size), np.uint8)
    for x in range(size):
        for y in range(size):
            at = ((x//8)*(size//8)+y//8)*32+(y%8)*4+(x%8)//2
            out[y, x] = (raw[at] >> (0 if x & 1 else 4)) & 15
    return out


def verify(baseline):
    gen = ROOT/'res/generated'
    recipe = json.loads((ROOT/'tools/data/normal_sprite_shade_repairs.json').read_text())
    source = Source(); sprites = decode_sprites(source.region('sprites'))
    main = source.region('maincpu'); lo = main[0x14a37:0x14e37]; hi = main[0x14e37:0x15237]
    colors = np.array([to_md(tuple(c//17 for c in palette_rgb(a, b))) for a, b in zip(lo, hi)])
    def words(path): return np.fromfile(path, '>u2')
    oldpal = words(baseline/'sprite_pal.bin'); pal = words(gen/'sprite_pal.bin')
    assert set(np.flatnonzero(oldpal != pal)) == {15, 31}
    assert (baseline/'bc_sprite_pal.bin').read_bytes() == (gen/'bc_sprite_pal.bin').read_bytes()
    oldlut = words(baseline/'vivid_lut.bin'); lut = words(gen/'vivid_lut.bin')
    assert np.array_equal(oldlut, lut), 'Unrelated Vivid colors changed'
    protected = {16: set(), 32: set()}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); wrapper = td/'keys.c'; libpath = td/'keys.dylib'
        wrapper.write_text('''#include "bc_actor_art.h"
void collect(unsigned char *small, unsigned char *large) {
 BcActor a={0}; a.body.state=0x80; a.body.sprite_base=0x100;
 for(unsigned ref=0x367a;ref<0x36d6;ref+=2) {
  a.sprite_base_ref=ref;
  for(unsigned frame=0;frame<65536;frame++) {
   a.body.sprite=(unsigned short)(0x100+frame);
   for(unsigned pal=0;pal<16;pal++) {
    a.body.attributes=pal; unsigned p=bc_actor_boss_pose(&a);
    if(p&0x80000u) (p&0x40000u?large:small)[p&32767]=1;
   }
  }
 }
}''')
        subprocess.run(['cc','-O2','-std=c99','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        str(ROOT/'src/bc_actor_art.c'),str(wrapper),'-o',str(libpath)],check=True)
        lib = C.CDLL(str(libpath)); small = (C.c_ubyte*32768)(); large = (C.c_ubyte*32768)()
        lib.collect(small, large)
        for size, values in ((16, small), (32, large)):
            protected[size].update(i for i, v in enumerate(values) if v)
            protected[size].update(code|(color<<11) for code in range(256) for color in range(16))
    for name in ('bc_sprite_recolors','bc_serpent_shapes','bc_player_projectile_shapes',
                 'bc_player_death_shapes','bc_boss_shots'):
        for row in json.loads((gen/(name+'.json')).read_text()):
            protected[row.get('size',16)].add(row['key'])
    restored = 0; checked = 0
    for size, name in ((16,'spr_bank'),(32,'spr_big')):
        stride = size*size//2; before = (baseline/(name+'.bin')).read_bytes(); after = (gen/(name+'.bin')).read_bytes()
        oldidx = words(baseline/(name+'_index.bin')); idx = words(gen/(name+'_index.bin'))
        assert np.array_equal(oldidx, idx) and len(before) == len(after)
        allowed = {int(idx[r['keys'][0]])&32767: r for r in recipe['repairs'] if r['size'] == size}
        for block in range(1, len(before)//stride+1):
            a = before[(block-1)*stride:block*stride]; b = after[(block-1)*stride:block*stride]
            if block not in allowed:
                assert a == b, (name,block,'unreviewed mutation'); continue
            r = allowed[block]; assert a != b
            assert hashlib.sha256(a).hexdigest() == r['before_sha256']
            assert hashlib.sha256(b).hexdigest() == r['after_sha256']
            oldpx, px = pens(a,size), pens(b,size); changed = oldpx != px
            assert np.array_equal(oldpx == 0, px == 0)
            assert int(changed.sum()) == r['restored_pixels']; restored += int(changed.sum())
            assert set(np.flatnonzero((idx&32767)==block)) == set(r['keys'])
            for key in r['keys']:
                assert key not in protected[size]
                code, color = key&2047, key>>11
                src = sprites[code] if size == 16 else np.block([
                    [sprites[code],sprites[(code+1)&2047]],
                    [sprites[(code+8)&2047],sprites[(code+9)&2047]]])
                rgb = colors[512+color*16+src.astype(int)]
                expected = (src != 15) & np.all(rgb == r['rgb3'],axis=2)
                assert np.array_equal(changed, expected)
                bank = int(idx[key])>>15
                prior = oldpal[bank*16+oldpx]; current = pal[bank*16+px]
                rr,gg,bb = r['rgb3']; assert np.all(current[changed] == rr*2+gg*32+bb*512)
                for vivid in (False,True):
                    x,y = prior,current
                    if vivid:
                        x = np.array([oldlut[index(int(v))] for v in x.ravel()]).reshape(x.shape)
                        y = np.array([lut[index(int(v))] for v in y.ravel()]).reshape(y.shape)
                    for v in np.unique(y):
                        assert len(np.unique(x[y==v])) <= 1, (key,'merged existing shades',vivid)
                checked += 1
        for key in protected[size]:
            block = int(idx[key])&32767
            if block: assert before[(block-1)*stride:block*stride] == after[(block-1)*stride:block*stride]
    assert restored == sum(r['restored_pixels'] for r in recipe['repairs'])
    return dict(passed=True,stored_pixels_restored=restored,alias_keys_checked=checked,
                changed_blocks=len(recipe['repairs']),added_pattern_bytes=0,
                source_exact=True,standard_vivid_no_new_merges=True,bc_patterns_unchanged=True,
                scope='Generated sprite banks, exhaustive supported BC actor/boss frame/palette selection, imported and player-page isolation. Native rendering, gallery upload and campaigns require separate checks.')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--baseline',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True); args = ap.parse_args()
    result = verify(args.baseline); args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2))
