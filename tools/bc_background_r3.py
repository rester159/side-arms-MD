"""Compose the cyan cavern from corresponding Normal characters and shades."""

def flip_character(raw, flip):
    if flip & 1:
        raw = bytes((raw[y*4+3-x]&15)<<4 | raw[y*4+3-x]>>4
                    for y in range(8) for x in range(4))
    if flip & 2:
        raw = b''.join(raw[y*4:(y+1)*4] for y in range(7,-1,-1))
    return raw


def compose(tiles, attrs, definition, cell_count=131):
    packed = bytearray()
    templates = []
    assert [r['cell'] for r in definition['cells']] == list(range(cell_count))
    for row in definition['cells']:
        assert len(row['characters']) == 16
        for k, donor in enumerate(row['characters']):
            source = donor['meta']*16 + donor['subtile']
            raw = flip_character(tiles[source*32:(source+1)*32], donor['flip'])
            word = (attrs[source]&0xe000) | k if any(raw) else 0
            if any(raw) and not word:
                # Keep PAL0's first character distinct from the blank sentinel.
                raw = flip_character(raw, 1)
                word = 0x0800
            packed.extend(raw)
            templates.append(word)
    return packed, templates, list(range(cell_count)) + [4095]*(256-cell_count)
