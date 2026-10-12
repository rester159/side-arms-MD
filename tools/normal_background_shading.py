"""Restore selected Normal background shades without changing surrounding colors."""
import struct
import json
from pathlib import Path
import numpy as np
from quantize import md_word


def refit_materials(zone, tiles, attrs, palettes, metas, source, colors):
    """Apply the offline source-pair-preserving fit; no runtime processing."""
    import hashlib
    from quantize import nearest
    recipe = json.loads((Path(__file__).parent/f'data/normal_zone{zone}_palette_fit.json').read_text())
    old_pal = [v for bank in palettes for v in
               [0]+[md_word(c) for c in bank]+[0]*(15-len(bank))]
    for name, data in (('tiles', tiles), ('attr', attrs),
                       ('pal', struct.pack('>32H', *old_pal))):
        assert hashlib.sha256(data).hexdigest() == recipe['input_sha256'][name], name
    banks = [[(v >> 1 & 7, v >> 5 & 7, v >> 9 & 7) for v in bank]
             for bank in recipe['banks']]
    assert all(len(bank) == 15 for bank in banks)
    assert banks[0][:3] == palettes[0][:3] and banks[1][:2] == palettes[1][:2]
    assert len(recipe['assignments']) == len(metas)*16
    for meta, (code, color) in enumerate(metas):
        for k in range(16):
            n = meta*16+k
            attr = struct.unpack_from('>H', attrs, n*2)[0]
            bank = recipe['assignments'][n]
            assert bank in (0, 1)
            original = source[code, k//4*8:k//4*8+8, k%4*8:k%4*8+8]
            lookup = {pen: 0 if pen == 15 else 1+nearest(colors[int(color)*16+pen], banks[bank])
                      for pen in range(16)}
            px = np.vectorize(lookup.get)(original)
            tiles[n*32:n*32+32] = ((px[:, ::2] << 4) | px[:, 1::2]).astype(np.uint8).tobytes()
            struct.pack_into('>H', attrs, n*2, (attr & ~0x2000) | (bank << 13) if attr else 0)
    palettes[:] = banks


def restore_materials(zone, tiles, attrs, palettes, metas, source, colors):
    recipes = json.loads((Path(__file__).parent/'data/normal_background_shade_repairs.json').read_text())['repairs']
    recipe = next((r for r in recipes if r['zone'] == zone), None)
    if recipe is None:
        return
    old_words = [[md_word(c) for c in bank] for bank in palettes]
    old_pal = [v for bank in old_words for v in [0]+bank+[0]*(15-len(bank))]
    banks = [set(bank) for bank in recipe['banks']]
    packed = []
    for b, wanted in enumerate(banks):
        ordered = list(dict.fromkeys(c for c in old_words[b] if c in wanted))
        ordered += sorted(wanted-set(ordered))
        assert len(ordered) <= 15
        prefix = 3 if b == 0 else 2
        assert ordered[:prefix] == old_words[b][:prefix]
        packed.append([0]+ordered+[0]*(15-len(ordered)))
        palettes[b] = [(v >> 1 & 7, v >> 5 & 7, v >> 9 & 7) for v in ordered]
    restored = 0
    for meta, (code, color) in enumerate(metas):
        for k in range(16):
            n = meta*16+k
            attr = struct.unpack_from('>H', attrs, n*2)[0]
            raw = np.frombuffer(bytes(tiles[n*32:n*32+32]), np.uint8).reshape(8, 4)
            pens = np.stack((raw >> 4, raw & 15), -1).reshape(8, 8)
            live = pens != 0
            if not live.any():
                continue
            actual = np.array(old_pal)[((attr >> 13)&1)*16+pens]
            output = actual.copy()
            if int(color) in recipe.get('source_palettes', []) or str(int(color)) in recipe.get('source_colors', {}):
                original = source[code, k//4*8:k//4*8+8, k%4*8:k%4*8+8]
                desired = np.array([md_word(colors[int(color)*16+int(p)]) for p in original.ravel()]).reshape(8, 8)
                selected = live if int(color) in recipe.get('source_palettes', []) else live & np.isin(desired, recipe['source_colors'][str(int(color))])
                output[selected] = desired[selected]
            used = set(map(int, output[live]))
            choices = [b for b in range(2) if used <= banks[b]]
            assert choices, (zone, meta, k, used)
            old_bank = attr >> 13 & 1
            bank = old_bank if old_bank in choices else choices[0]
            lookup = {c: i for i, c in reversed(list(enumerate(packed[bank]))) if i}
            converted = np.zeros((8, 8), np.uint8)
            for c in used:
                converted[live & (output == c)] = lookup[c]
            assert np.array_equal(np.array(packed[bank])[converted][live], output[live])
            tiles[n*32:n*32+32] = ((converted[:, ::2] << 4) | converted[:, 1::2]).tobytes()
            struct.pack_into('>H', attrs, n*2, (attr & ~0x2000) | bank << 13)
            restored += int(np.sum(live & (output != actual)))
    assert restored == recipe['restored_pixels'], (zone, restored)


def restore_zone16_blue(tiles, attrs, palettes, metas, source, colors):
    # An exact two-bank packing of existing rendered colors plus the missing
    # palette-19 blue steps. Star colors keep their original pen numbers.
    banks = [{0, 6, 8, 12, 14, 110, 1166, 1670, 1710, 2216, 2560, 2688, 2730, 3822},
             {0, 4, 6, 8, 64, 74, 104, 578, 1024, 1092, 1124, 1600, 1670, 2112, 2656}]
    old_words = [[md_word(c) for c in bank] for bank in palettes]
    old_pal = [v for bank in old_words for v in [0]+bank+[0]*(15-len(bank))]
    packed_words = []
    for b, wanted in enumerate(banks):
        ordered = list(dict.fromkeys(c for c in old_words[b] if c in wanted))
        ordered += sorted(wanted-set(ordered))
        assert ordered[:3 if b == 0 else 2] == old_words[b][:3 if b == 0 else 2]
        assert len(ordered) <= 15
        packed_words.append([0]+ordered+[0]*(15-len(ordered)))
        palettes[b] = [(v >> 1 & 7, v >> 5 & 7, v >> 9 & 7) for v in ordered]
    restored = []
    for meta, (code, color) in enumerate(metas):
        for k in range(16):
            n = meta*16+k
            attr = struct.unpack_from('>H', attrs, n*2)[0]
            raw = np.frombuffer(bytes(tiles[n*32:n*32+32]), np.uint8).reshape(8, 4)
            pens = np.stack((raw >> 4, raw & 15), -1).reshape(8, 8)
            live = pens != 0
            if not live.any():
                continue
            actual = np.array(old_pal)[((attr >> 13)&1)*16+pens]
            output = actual.copy()
            if int(color) == 19:
                original = source[code, k//4*8:k//4*8+8, k%4*8:k%4*8+8]
                desired = np.array([md_word(colors[19*16+int(p)]) for p in original.ravel()]).reshape(8, 8)
                blue = live & ((desired >> 9 & 7) > (desired >> 1 & 7)) & ((desired >> 9 & 7) > (desired >> 5 & 7))
                output[blue] = desired[blue]
            used = set(map(int, output[live]))
            choices = [b for b in range(2) if used <= banks[b]]
            assert choices, (meta, k, used)
            old_bank = attr >> 13 & 1
            bank = old_bank if old_bank in choices else choices[0]
            lookup = {c: i for i, c in reversed(list(enumerate(packed_words[bank]))) if i}
            converted = np.zeros((8, 8), np.uint8)
            for c in used:
                converted[live & (output == c)] = lookup[c]
            assert np.array_equal(np.array(packed_words[bank])[converted][live], output[live])
            tiles[n*32:n*32+32] = ((converted[:, ::2] << 4) | converted[:, 1::2]).tobytes()
            struct.pack_into('>H', attrs, n*2, (attr & ~0x2000) | bank << 13)
            count = int(np.sum(live & (output != actual)))
            if count:
                restored.append(dict(meta=meta, subtile=k, pixels=count))
    assert sum(r['pixels'] for r in restored) == 526
    return restored


def restore_local_shades(zone, tiles, attrs, palettes, metas, source, colors):
    """Restore selected source pixels using existing banks, after broad repairs."""
    import hashlib
    records = json.loads((Path(__file__).parent/'data/normal_local_shade_repairs.json').read_text())['repairs']
    recipe = next((r for r in records if r['zone'] == zone), None)
    if recipe is None:
        return
    words = [v for bank in palettes for v in
             [0]+[md_word(c) for c in bank]+[0]*(15-len(bank))]
    for name, raw in (('tiles', tiles), ('attr', attrs), ('pal', struct.pack('>32H', *words))):
        assert hashlib.sha256(raw).hexdigest() == recipe['input_sha256'][name], (zone, name)
    restored = 0
    for change in recipe['changes']:
        meta, k, bank = change['meta'], change['subtile'], change['bank']
        n = meta*16+k
        attr = struct.unpack_from('>H', attrs, n*2)[0]
        raw = np.frombuffer(bytes(tiles[n*32:n*32+32]), np.uint8).reshape(8, 4)
        pens = np.stack((raw >> 4, raw & 15), -1).reshape(8, 8)
        live = pens != 0
        before = np.array(words)[((attr >> 13)&1)*16+pens]
        code, color = metas[meta]
        src = source[code, k//4*8:k//4*8+8, k%4*8:k%4*8+8]
        desired = np.array([md_word(colors[int(color)*16+int(p)]) for p in src.ravel()]).reshape(8, 8)
        selected = live & (before != desired) & np.isin(desired, change['source_words'])
        assert int(selected.sum()) == change['pixels']
        output = np.where(selected, desired, before)
        palette = words[bank*16:bank*16+16]
        lookup = {word: pen for pen, word in reversed(list(enumerate(palette))) if pen}
        converted = np.zeros((8, 8), np.uint8)
        for word in np.unique(output[live]):
            converted[live & (output == word)] = lookup[int(word)]
        assert np.array_equal(np.array(palette)[converted][live], output[live])
        tiles[n*32:n*32+32] = ((converted[:, ::2] << 4) | converted[:, 1::2]).tobytes()
        struct.pack_into('>H', attrs, n*2, (attr & ~0x2000) | (bank << 13))
        restored += int(selected.sum())
    assert restored == recipe['repaired_pixels']


def restore_selective_files(generated, source, codes, color_ids, colors):
    """Repack exact source shades after generating base and Home variants.

    Home cutouts share the base palette. Re-encode their existing displayed
    colors too, without regenerating their authored shapes with a new fit.
    """
    import hashlib
    import zones
    recipes = json.loads((Path(__file__).parent/'data/normal_selective_shade_repairs.json').read_text())['repairs']
    for recipe in recipes:
        zone = recipe['zone']
        blobs = {}
        for name, digest in recipe['input_sha256'].items():
            stem = f'zone{zone}h_{name[5:]}' if name.startswith('home_') else f'zone{zone}_{name}'
            blobs[name] = (generated/(stem+'.bin')).read_bytes()
            assert hashlib.sha256(blobs[name]).hexdigest() == digest, (zone, name)
        prior = np.frombuffer(blobs['pal'], '>u2')
        banks = recipe['banks']
        assert all(len(bank) == 16 and bank[0] == 0 for bank in banks)
        assert banks[0][1:4] == list(prior[1:4]) and banks[1][1:3] == list(prior[17:19])
        x, y, width, height = zones.ZONES[zone]['rect']
        metas = sorted({(int(codes[r, c]), int(color_ids[r, c]))
                        for r in range(y, y+height) for c in range(x, x+width)})
        restored = 0
        for home in (False, True) if 'home_tiles' in blobs else (False,):
            prefix = 'home_' if home else ''
            attrs = np.frombuffer(blobs[prefix+'attr'], '>u2').copy()
            raw = np.frombuffer(blobs[prefix+'tiles'], np.uint8).reshape(-1, 8, 4)
            pens = np.stack((raw >> 4, raw & 15), -1).reshape(-1, 8, 8)
            converted = np.zeros_like(pens)
            for n, original in enumerate(pens):
                attr = int(attrs[n]); live = original != 0
                before = prior[((attr >> 13)&1)*16+original]
                wanted = before.copy()
                if not home:
                    code, color = metas[n//16]; k = n % 16
                    src = source[code, k//4*8:k//4*8+8, k%4*8:k%4*8+8]
                    desired = np.array([md_word(colors[color*16+int(p)]) for p in src.ravel()]).reshape(8, 8)
                    selected = live & np.isin(desired, recipe['source_colors'].get(str(color), []))
                    wanted[selected] = desired[selected]
                    restored += int((live & (wanted != before)).sum())
                used = set(map(int, wanted[live]))
                choices = [b for b in (0, 1) if used <= set(banks[b][1:])]
                assert choices, (zone, home, n)
                old_bank = (attr >> 13)&1
                bank = old_bank if old_bank in choices else choices[0]
                lookup = {word: pen for pen, word in reversed(list(enumerate(banks[bank]))) if pen}
                for word in used:
                    converted[n][live & (wanted == word)] = lookup[word]
                assert np.array_equal(np.array(banks[bank])[converted[n]][live], wanted[live])
                attrs[n] = (attr & 0xdfff) | (bank << 13) if attr else 0
            stem = f'zone{zone}' + ('h' if home else '')
            (generated/(stem+'_tiles.bin')).write_bytes(((converted[:, :, ::2] << 4) | converted[:, :, 1::2]).tobytes())
            (generated/(stem+'_attr.bin')).write_bytes(attrs.astype('>u2').tobytes())
        assert restored == recipe['restored_pixels'], zone
        (generated/f'zone{zone}_pal.bin').write_bytes(np.array(banks, dtype='>u2').tobytes())
