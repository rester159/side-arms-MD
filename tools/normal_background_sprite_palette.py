"""Build-time exact background repairs using the already-loaded sprite colors."""
import hashlib
import json
from pathlib import Path
import numpy as np
from quantize import md_word
import parallax_split
import zones


def apply(generated, source, colors):
    from arcade_source import Source, bgmap_cells
    codes, color_ids, flags = bgmap_cells(Source().region('bgmap'))
    recipe = json.loads((Path(__file__).parent / 'data/normal_background_sprite_palette_repairs.json').read_text())
    sprite_bytes = (generated / 'sprite_pal.bin').read_bytes()
    assert hashlib.sha256(sprite_bytes).hexdigest() == recipe['sprite_palette_sha256']
    sprite = np.frombuffer(sprite_bytes, '>u2')
    for record in recipe['records']:
        zone = record['zone']
        stem = f'zone{zone}' + ('h' if record['kind'] == 'home' else '')
        for name, digest in record['input_sha256'].items():
            assert hashlib.sha256((generated / name).read_bytes()).hexdigest() == digest, name
        x, y, width, height = zones.ZONES[zone]['rect']
        metas = sorted({(int(codes[r, c]), int(color_ids[r, c]))
                        for r in range(y, y + height) for c in range(x, x + width)})
        patterns = [(i, source[code]) for i, (code, color) in enumerate(metas)]
        if record['kind'] == 'home':
            # Home's cutout/wheel-fill geometry must supply the source pixels.
            # Cut masks must retain the source map flips.
            patterns, _ = parallax_split.home_variant(
                zone, codes, color_ids, flags, {key: i for i, key in enumerate(metas)},
                lambda color: min(range(15), key=lambda pen: sum(colors[color * 16 + pen])))
        palette = np.concatenate((np.frombuffer((generated / f'zone{zone}_pal.bin').read_bytes(), '>u2'), sprite))
        attrs = np.frombuffer((generated / f'{stem}_attr.bin').read_bytes(), '>u2').copy()
        raw = np.frombuffer((generated / f'{stem}_tiles.bin').read_bytes(), np.uint8).reshape(-1, 8, 4)
        pens = np.stack((raw >> 4, raw & 15), -1).reshape(-1, 8, 8)
        restored = 0
        for change in record['changes']:
            meta, tile, bank = change['meta'], change['subtile'], change['bank']
            assert bank in (2, 3)
            owner, pattern = patterns[meta]
            assert owner == change['owner']
            n = meta * 16 + tile
            old_attr = int(attrs[n])
            live = pens[n] != 0
            old = palette[((old_attr >> 13) & 3) * 16 + pens[n]]
            source_pens = pattern[tile // 4 * 8:tile // 4 * 8 + 8, tile % 4 * 8:tile % 4 * 8 + 8]
            color = metas[owner][1]
            desired = np.array([md_word(colors[color * 16 + int(pen)]) for pen in source_pens.flat]).reshape(8, 8)
            selected = live & np.isin(desired, change['source_words'])
            wanted = old.copy()
            wanted[selected] = desired[selected]
            changed = int((live & (wanted != old)).sum())
            assert changed == change['pixels'], (zone, meta, tile, changed)
            restored += changed
            available = list(map(int, palette[bank * 16:bank * 16 + 16]))
            converted = np.zeros((8, 8), np.uint8)
            for word in np.unique(wanted[live]):
                pen = next(i for i in range(1, 16) if available[i] == word)
                converted[live & (wanted == word)] = pen
            assert np.array_equal(np.array(available)[converted][live], wanted[live])
            pens[n] = converted
            attrs[n] = (old_attr & 0x9fff) | (bank << 13)
        assert restored == record['exact_pixels']
        outputs = {f'{stem}_tiles.bin': ((pens[:, :, ::2] << 4) | pens[:, :, 1::2]).tobytes(),
                   f'{stem}_attr.bin': attrs.astype('>u2').tobytes()}
        for name, data in outputs.items():
            assert hashlib.sha256(data).hexdigest() == record['output_sha256'][name], name
            (generated / name).write_bytes(data)
