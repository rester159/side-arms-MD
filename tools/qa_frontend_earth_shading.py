#!/usr/bin/env python3
"""Check linked Earth/flash source shades and unchanged surrounding intro frames."""
import argparse
import ast
import hashlib
import json
import struct
from pathlib import Path

import numpy as np
from arcade_source import ROOT, Source, decode_bgtiles, bgmap_cells, palette_rgb
from bc_background_equivalence import symbols
from quantize import md_word, to_md


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--burn-repair', action='store_true')
    args = parser.parse_args()
    burn_recipe = json.loads((ROOT/'tools/data/frontend_burn_palette.json').read_text()) if args.burn_repair else None
    src = Source()
    maincpu = src.region('maincpu')
    colors = np.array([md_word(to_md(tuple(v//17 for v in palette_rgb(
        maincpu[0x14a37+i], maincpu[0x14e37+i])))) for i in range(1024)])
    # Read the generator's source-coordinate specification without running it.
    tree = ast.parse((ROOT/'tools/build_frontend.py').read_text())
    nodes = [n for n in tree.body if
             isinstance(n, ast.FunctionDef) and n.name == 'world_view' or
             isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and
             t.id == 'SCENES' for t in n.targets)]
    code, color, flags = bgmap_cells(src.region('bgmap'))
    scope = dict(np=np, bgt=decode_bgtiles(src.region('bgtiles')),
                 code=code, color=color, flags=flags)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<source-views>', 'exec'), scope)
    old = (args.baseline/'rom.bin').read_bytes()
    rom = (ROOT/'out/release/rom.bin').read_bytes()
    os = symbols(args.baseline/'symbol.txt')
    sy = symbols(ROOT/'out/release/symbol.txt')

    def decode(data, symbols, scene, setid, palette):
        pal = np.array(struct.unpack_from('>32H', data, symbols[palette]))
        attrs = np.array(struct.unpack_from('>1792H', data,
                                          symbols[f'fe_scene{scene}_map'])).reshape(28, 64)
        pixels = np.zeros((224, 320), int)
        opaque = np.zeros((224, 320), bool)
        for y in range(28):
            for x in range(40):
                attr = int(attrs[y, x])
                if not attr:
                    continue
                tile = (attr & 2047)-160
                assert tile >= 0
                at = symbols[f'fe_set{setid}_tiles']+tile*32
                raw = np.frombuffer(data[at:at+32], np.uint8).reshape(8, 4)
                pens = np.stack((raw >> 4, raw & 15), -1).reshape(8, 8)
                if attr & 0x800:
                    pens = pens[:, ::-1]
                if attr & 0x1000:
                    pens = pens[::-1, :]
                pixels[y*8:y*8+8, x*8:x*8+8] = pal[((attr >> 13)&1)*16+pens]
                opaque[y*8:y*8+8, x*8:x*8+8] = pens != 0
        return pixels, opaque, attrs

    vivid = np.array(struct.unpack_from('>512H', rom, sy['vivid_lut']))
    def vivid_words(v):
        return vivid[(v >> 1 & 7) | (v >> 5 & 7) << 3 | (v >> 9 & 7) << 6]

    reports = []
    for i, (name, setid, x, y) in enumerate(scope['SCENES']):
        palette = 'fe_earth_pal' if i in (1, 2) else f'fe_set{setid}_pal'
        map_ptr, descriptor_set, pal_ptr = struct.unpack_from('>IBxI', rom, sy['fe_scenes']+i*10)
        assert (map_ptr, descriptor_set, pal_ptr) == (sy[f'fe_scene{i}_map'], setid, sy[palette])
        before, old_mask, old_attrs = decode(old, os, i, setid, f'fe_set{setid}_pal')
        after, mask, attrs = decode(rom, sy, i, setid, palette)
        assert np.array_equal(mask, old_mask), (name, 'opacity')
        assert np.array_equal(attrs & 0x8000, old_attrs & 0x8000), (name, 'priority')
        if i in (1, 2):
            ids = scope['world_view'](x, y)
            assert np.array_equal(mask, ids >= 0)
            assert np.array_equal(after[mask], colors[ids[mask]]), (name, 'source shade')
        elif burn_recipe and i in burn_recipe['scenes']:
            ids = scope['world_view'](x, y)
            source_words = colors[np.maximum(ids, 0)]
            selected = mask & np.isin(source_words, burn_recipe['source_colors'])
            assert np.array_equal(after[selected], source_words[selected]), (name, 'burn source shade')
            assert np.array_equal(after[~selected], before[~selected]), (name, 'unrelated pixels')
            for yy in range(0, 224, 32):
                for xx in range(0, 320, 32):
                    sl = np.s_[yy:yy+32, xx:xx+32]
                    live = mask[sl]
                    prior, current = before[sl][live], after[sl][live]
                    for old_words, new_words in ((prior, current), (vivid_words(prior), vivid_words(current))):
                        for value in np.unique(new_words):
                            assert len(np.unique(old_words[new_words == value])) <= 1, (name, 'merged shade', yy, xx)
        else:
            assert np.array_equal(after, before), (name, 'unrelated frame changed')
        reports.append(dict(scene=i, name=name, changed_pixels=int(np.sum(after != before))))
    for name in (['fe_set0_pal'] if burn_recipe else ['fe_set0_pal', 'fe_set1_pal']):
        assert rom[sy[name]:sy[name]+64] == old[os[name]:os[name]+64]
    newpal = struct.unpack_from('>32H', rom, sy['fe_earth_pal'])
    oldpal = struct.unpack_from('>32H', old, os['fe_set1_pal'])
    assert newpal[1:4] == oldpal[1:4] and newpal[17:19] == oldpal[17:19]
    vivid = struct.unpack_from('>512H', rom, sy['vivid_lut'])
    packed = lambda w: (w >> 1 & 7) | (w >> 5 & 7) << 3 | (w >> 9 & 7) << 6
    shades = set(newpal)
    assert len({vivid[packed(w)] for w in shades}) == len(shades), 'Vivid shade collapse'
    assert sum(r['changed_pixels'] for r in reports) == 5679 + (burn_recipe['restored_pixels'] if burn_recipe else 0)
    result = dict(passed=True, rom_sha256=hashlib.sha256(rom).hexdigest(),
                  source_exact_scenes=[1, 2], unchanged_scenes=sum(r['changed_pixels'] == 0 for r in reports),
                  burn_restored_pixels=burn_recipe['restored_pixels'] if burn_recipe else 0,
                  stars_unchanged=True, vivid_shades_distinct=True, scenes=reports)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
