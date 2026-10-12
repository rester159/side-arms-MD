#!/usr/bin/env python3
"""Build native BC scenery from reusable Normal materials and BC-specific art.

Source cell IDs select the per-round material recipes. Matching Normal art is
reused with preserved shade ramps; BC-specific contours and original patterns
are imported where the Normal geometry does not match. These resources serve
both gameplay and the development preview, without runtime PCE emulation.
"""
from pathlib import Path
import struct
import json
from zones import SCENE_ONLY_ZONES
from bc_background_r1 import replace_r1_ledge_family
from bc_background_r8 import compose as compose_round_eight, materials as round_eight_materials
from bc_background_r9 import compose as compose_round_nine, materials as round_nine_materials
from bc_background_r4_shading import compose as round_four_source_shades
from bc_background_r10_shading import materials as round_ten_materials
from bc_background_r3_shading import materials as round_three_materials
from bc_background_r3 import flip_character as flip_bg_character
from bc_background_storage import pack as pack_character_storage
from bc_background_r5_shading import materials as round_five_materials, normalize_water
from bc_background_r2 import materials as round_two_materials, compose as compose_round_two
from bc_background_r6 import materials as round_six_materials
from bc_background_r7 import materials as round_seven_materials, compose as compose_round_seven
from bc_background_r3 import compose as compose_round_three
from bc_background_r4 import compose as compose_round_four, MAPPING as ROUND_FOUR_MAPPING

# Every 512-byte tile block is DMA-aligned: DMA_queueDmaFast must not cross
# a 128 KiB ROM boundary. This applies to every generated round.
ROOT = Path(__file__).resolve().parents[1]
G = ROOT / 'res/generated'
# Our existing zone-zero metatiles chosen by subject and edge orientation.
# The explicit R1 contour replacements below refine these gameplay selections.
# Cells 1A/1B need the water-to-cliff transition (54/56), not the broad
# blue shelf (53) followed by an unrelated solid rock face (61).
METAS = [
    5,4,9,22,27,28,12,32,0,17,17,29,33,38,15,8,
    38,19,19,48,49,52,51,21,30,55,54,56,60,46,61,71,
    34,79,34,37,67,68,74,67,83,73,73,72,70,66,75,75,
    81,34,64,87,51,84,80,81,73,34,79,79,68,73,15,
]
assert len(METAS) == 63

# Preserve the original Genesis material colors, per the background review.
PALETTE = struct.unpack('>32H', (G/'bc_r1_donor_pal.bin').read_bytes())
assert len(PALETTE) == 32 and all((c & ~0xeee) == 0 for c in PALETTE)


SCENERY = []


def array(ctype,name,values,fmt):
    alignment=' __attribute__((aligned(512)))' if name.endswith('_tiles') else ''
    return f'const {ctype} {name}[{len(values)}]{alignment} = '+'{\n'+''.join(
        '    '+','.join(fmt%v for v in values[i:i+16])+',\n'
        for i in range(0,len(values),16))+'};\n'


def write_scenery(round_number, packed, templates, palette, source_map):
    """Collect source cells; emit all rounds together after material authoring."""
    assert len(packed)%512==0 and len(templates)==len(packed)//32
    assert len(source_map)==256 and len(palette)==32
    for index, word in enumerate(templates):
        assert word or not any(packed[index*32:(index+1)*32]), (
            round_number, index//16, index%16,
            'Nonempty character would be hidden by the inactive template sentinel')
    SCENERY.append((round_number,bytes(packed),tuple(templates),tuple(palette),source_map))


def write_shared_scenery():
    """Intern exact logical patterns, then share mirrored characters without recoloring.

    Palette words stay per round. Only byte-identical pattern/template blocks
    share logical IDs. Whole-block orientations stay distinct; their characters
    share DMA storage through hardware tile flips.
    The source table reuses exact Normal characters at their existing aligned
    addresses. A cache miss reads one source pointer; no decompression or new
    pixel conversion is needed. Zone templates and source remaps stay logical.
    """
    unique={};tiles=bytearray();attrs=[];rounds=[];local_total=0
    for number,packed,templates,palette,source_map in SCENERY:
        remap=[];local=set()
        for entry in source_map:
            if entry==4095:
                remap.append(4095);continue
            source=entry&4095
            pixels=packed[source*512:(source+1)*512]
            words=templates[source*16:(source+1)*16]
            assert len(pixels)==512 and len(words)==16
            if entry & 0xc000:
                # Bake pre-authored map flips before sharing characters. Keep
                # existing character flags and the active-zero sentinel valid.
                transformed, transformed_words = bytearray(), []
                flip = (entry >> 14) & 3
                for y in range(4):
                    for x in range(4):
                        sx = 3-x if flip & 1 else x
                        sy = 3-y if flip & 2 else y
                        word = words[sy*4+sx]
                        raw = pixels[(word&0x7ff)*32:(word&0x7ff)*32+32] if word else bytes(32)
                        raw = flip_bg_character(raw, flip)
                        target = (word&0xf800) | (y*4+x) if word else 0
                        if word and not target:
                            raw = flip_bg_character(raw, 1)
                            target = 0x0800
                        transformed.extend(raw)
                        transformed_words.append(target)
                pixels, words = bytes(transformed), tuple(transformed_words)
            key=(pixels,words);local.add(key)
            # Keep logical whole-cell orientations distinct. Character-level
            # canonical packing below shares their storage without combining
            # per-character flips with the renderer's additive whole-cell flags.
            if key not in unique:
                unique[key]=len(unique);tiles.extend(pixels);attrs.extend(words)
            remap.append(unique[key])
        local_total+=len(local)
        rounds.append((number,palette,remap,len(local)))
    assert len(unique)<1024, 'Renderer meta_slot limit'
    # Reindex exact characters into Normal donors or shared private DMA blocks.
    normal_banks=[(path.stem,path.read_bytes()) for path in sorted(G.glob('zone*_tiles.bin'))
                  if path.stem not in {f'zone{z}_tiles' for z in SCENE_ONLY_ZONES}]
    tiles,attrs,sources,reused=pack_character_storage(bytes(tiles),attrs,normal_banks)
    pool='/* Generated shared BC character bank; exact materials, hardware tile flips. */\n#include "gen/assets.h"\n'
    pool+=array('u8','bc_bg_shared_tiles',tiles,'0x%02x')
    pool+=array('u16','bc_bg_shared_templates',attrs,'0x%04x')
    # Emit the pointer table with the early assembly resources. Its word-aligned
    # bytes can occupy padding before the mandatory 32 KiB sound-bank boundary,
    # instead of extending the late LTO data section. The runtime table is exact.
    source_asm = ['/* Generated exact BC DMA-source pointers. */',
                  '.section .rodata', '.balign 2', '.global bc_bg_sources',
                  'bc_bg_sources:']
    source_asm += [f'.long {name} + {offset}' for name,offset in sources]
    (ROOT/'src/gen/bc_background_sources.s').write_text('\n'.join(source_asm)+'\n')
    palette_asm = ['/* Generated BC palettes and R5 remap, in pre-sound alignment padding. */', '.section .rodata', '.balign 2']
    for number,palette,remap,local_count in rounds:
        prefix='bc_bg'+(str(number) if number>1 else '')
        output='/* Generated BC scenery; source IDs and per-round colors preserved. */\n#include "gen/assets.h"\n'
        for ctype,suffix,size in [('u8','tiles',len(tiles)),('u16','templates',len(attrs))]:
            output+=f'extern const {ctype} {prefix}_{suffix}[{size}];\n'
            pool+=f'extern const {ctype} {prefix}_{suffix}[{size}] __attribute__((alias("bc_bg_shared_{suffix}"), used, externally_visible));\n'
        if number == 5:
            # This small map plus the palettes fits before the Z80 alignment.
            output+=f'extern const u16 {prefix}_remap[256];\n'
            palette_asm += [f'.global {prefix}_remap', f'{prefix}_remap:', '.word '+','.join(hex(v) for v in remap)]
        else:
            output+=array('u16',prefix+'_remap',remap,'0x%04x')
        output+=f'extern const u16 {prefix}_palette[32];\n'
        palette_asm += [f'.global {prefix}_palette', f'{prefix}_palette:', '.word '+','.join(hex(v) for v in palette)]
        output+=f'const Zone {prefix}_draft = '+'{'+f'0,0,128,128,{len(unique)},{prefix}_tiles,{prefix}_templates,NULL,{prefix}_palette'+'};\n'
        name='bc_background'+(str(number) if number>1 else '')+'.c'
        (ROOT/'src/gen'/name).write_text(output)
        print(f'BC round {number}: {sum(e!=4095 for e in remap)} source cells, {local_count} referenced unique blocks')
    (ROOT/'src/gen/bc_background_pool.c').write_text(pool)
    (ROOT/'src/gen/bc_background_palettes.s').write_text('\n'.join(palette_asm)+'\n')
    print(f'BC block sources: {reused} reused from Normal; {len(tiles)//512} private blocks')
    print(f'BC logical bank: {local_total} per-round blocks -> {len(unique)} shared; {(local_total-len(unique))*544} bytes removed before Normal-source reuse')


def round_two():
    # Original Normal source shades; cave geometry remains under reconstruction.
    definition=json.loads((ROOT/'tools/data/bc_background_r2_materials.json').read_text())
    mapping={r['cell']:r['characters'][0]['meta'] for r in definition['cells']}
    tiles,attrs,palette,orders=round_two_materials(definition)
    packed,templates,source_map=compose_round_two(tiles,attrs,definition,orders)
    write_scenery(2,packed,templates,palette,source_map)

def round_three():
    # Detailed Normal cyan rock and the corresponding embedded machinery.
    definition=json.loads((ROOT/'tools/data/bc_background_r3_materials.json').read_text())
    mapping={r['cell']:r['characters'][0]['meta'] for r in definition['cells']}
    tiles,attrs,palette=round_three_materials(definition)
    packed,templates,source_map=compose_round_three(tiles,attrs,definition)
    write_scenery(3,packed,templates,palette,source_map)


def round_four():
    # Corresponding Normal organic ledges and complete oval machinery.
    packed,templates,palette,source_map=round_four_source_shades()
    write_scenery(4,packed,templates,palette,source_map)


def round_five():
    # Corresponding pink/purple Normal cavern, complete skulls and machinery.
    definition=json.loads((ROOT/'tools/data/bc_background_r5_materials.json').read_text())
    mapping={r['cell']:r['characters'][0]['meta'] for r in definition['cells']}
    tiles,attrs,palette=round_five_materials(definition)
    packed,templates,source_map=compose_round_three(tiles,attrs,definition,cell_count=73)
    packed=normalize_water(packed,templates,definition)
    write_scenery(5,packed,templates,palette,source_map)


def round_six():
    # Corresponding industrial shaft: whole Normal characters and source shades.
    definition=json.loads((ROOT/'tools/data/bc_background_r6_materials.json').read_text())
    mapping={r['cell']:r['characters'][0]['meta'] for r in definition['cells']}
    tiles,attrs,palette=round_six_materials(definition)
    packed,templates,source_map=compose_round_three(tiles,attrs,definition)
    write_scenery(6,packed,templates,palette,source_map)


def round_seven():
    # Corresponding foundry materials, retaining all original source shades.
    definition=json.loads((ROOT/'tools/data/bc_background_r7_materials.json').read_text())
    mapping={r['cell']:r['characters'][0]['meta'] for r in definition['cells']}
    tiles,attrs,palette,lut=round_seven_materials(definition)
    packed,templates,source_map=compose_round_seven(tiles,definition,lut,palette)
    write_scenery(7,packed,templates,palette,source_map)


def round_eight():
    # Corresponding Normal red pipes/panels. The cylinder bodies are shortened
    # at quadrant boundaries for the PCE three-quadrant repeat; each circular
    # front retains all four original Normal quadrants and their shading.
    definition=json.loads((ROOT/'tools/data/bc_background_r8_materials.json').read_text())
    mapping={r['cell']:definition['patterns'][f"{r['patterns'][0]:02x}"]['normal_meta'] for r in definition['cells']}
    tiles,attrs,palette=round_eight_materials(definition)
    packed,templates,source_map=compose_round_eight(tiles,attrs,definition)
    write_scenery(8,packed,templates,palette,source_map)


def round_nine():
    # Corresponding Normal chamber walls, panels and suspended ornament.
    # Whole characters retain their original shades and palette banks.
    definition=json.loads((ROOT/'tools/data/bc_background_r9_materials.json').read_text())
    mapping={r['cell']:next((d['normal_meta'] for p in r['patterns'] for d in definition['patterns'][f'{p:02x}'] if d is not None),0) for r in definition['cells']}
    tiles,attrs,palette=round_nine_materials(definition)
    packed,templates,source_map=compose_round_nine(tiles,attrs,definition)
    write_scenery(9,packed,templates,palette,source_map)


def round_ten():
    # Normal final chamber, zone 21: the same mechanical face seen in PCE BC.
    # Reproduce its complete 4x5 metatile composition, including mirrored right
    # half, instead of substituting unrelated zone-one machinery. The PCE face
    # is redrawn and offset slightly inside its cells; this is the corresponding
    # intact Genesis artwork, with its original palette. Source IDs/collision
    # remain unchanged. Cell 01 is filler beside the narrower bottom jaw.
    metas = [17,17,21,21,22,20,20,22,23,24,24,23,15,16,16,15,25,19,19,25]
    flips = {3,6,7,10,11,14,15,18,19}
    tiles,attrs,palette=round_ten_materials(metas)
    packed,templates=bytearray(),[]
    for meta in metas:
        for i in range(16):
            source=meta*16+i
            raw=tiles[source*32:source*32+32]
            packed.extend(raw)
            templates.append((attrs[source]&0xe000)|i if any(raw) else 0)
    # The existing stage renderer supports the same metatile mirror bits as
    # Normal. Share complete left/right blocks without changing their pixels.
    mapping=[i | (0x4000 if i in flips else 0) for i in range(20)]
    write_scenery(10,packed,templates,palette,mapping+[4095]*236)


def main():
    SCENERY.clear()
    tiles = (G / 'bc_r1_donor_tiles.bin').read_bytes()
    attrs = struct.unpack('>' + str(len(tiles)//32) + 'H', (G / 'bc_r1_donor_attr.bin').read_bytes())
    contours = json.loads((ROOT/'tools/data/bc_background_r1_edge_contours.json').read_text())
    edges = {row['cell']: row for row in contours['cells']}
    assert all(METAS[cell] == row['normal_meta'] for cell, row in edges.items())
    packed, templates = bytearray(), []
    for cell, meta in enumerate(METAS):
        for ty in range(4):
            for tx in range(4):
                sx, sy = tx, ty
                blank = False
                # Continue the sea's dithered lower ramp, not the flat cyan
                # sky half of a city metatile.
                if cell == 2:
                    meta = 4
                    sy = 2 + ty % 2
                # Roof silhouette only rises in the bottom half of this cell.
                if cell == 3:
                    blank = ty < 2
                    sy = max(0, ty-2)
                # Keep the small tower roof at the bottom of its sky cell;
                # continue its shaft with the lower half of our tower artwork.
                if cell == 0x0a:
                    blank = ty < 2
                    sy = max(0, ty-2)
                if cell == 9:
                    sy = 2 + ty % 2
                # BC 0D is a low skyline against black sky. Normal tile 38
                # supplies the city, but its unrelated blue hill must not
                # appear above it. Retain the original lower-half pixels.
                if cell == 0x0d:
                    blank = ty < 2
                # BC 10 ends the low city at the water: buildings occupy the
                # left half only. The previous whole horizon tile added a
                # large hill. Keep our skyline on the left and water on the
                # right, with black sky above both original materials.
                if cell == 0x10:
                    blank = ty < (2 if tx < 2 else 3)
                if cell == 0x28:
                    # Move the donor's textured upper ledge to the foot of
                    # the source cell, before trimming its low ridge outline.
                    sy = max(0, ty-2)
                # Source horizon: black sky with a narrow blue line at its foot.
                # Reuse our horizon's lowest blue band, with no new pixel art.
                if cell == 0:
                    blank = ty < 3
                    sy = 3
                if cell in (0x2a, 0x2f, 0x3b, 0x3d):
                    sx = 3-tx
                source = meta*16 + sy*4 + sx
                if cell == 0x10 and tx >= 2:
                    source = 5*16 + ty*4 + tx
                # Match the skyline's quadrant joins, not whole donor cells.
                # 0F shares its lower facade with 0E; donor 8 incorrectly
                # inserted a flat grey slab. 12 shares 0F's left facade and
                # the open sea on its right. 11 ends the city in the water.
                if cell == 0x0f:
                    source = (19 if ty < 2 else 15)*16 + ty*4 + tx
                if cell == 0x11:
                    donor = 15 if ty < 2 and tx < 2 else 41
                    source = donor*16 + ty*4 + tx
                    if ty >= 2 and tx >= 2:
                        source = 4*16 + ty*4 + tx
                if cell == 0x12:
                    source = ((19 if ty < 2 else 15)*16 + ty*4 + tx) if tx < 2 else (4*16 + (2+ty%2)*4 + tx)
                # BC 07 is a striped tower foot, not distant city blocks.
                # Mirror our striped facade to the left; its bottom band
                # joins the same Normal blue ground/sky material as cell 02.
                if cell == 7:
                    source = (9*16+tx) if ty == 3 else (32*16+ty*4+max(0,2-tx))
                if cell == 0x1b and tx == 0:
                    # Restore BC's left water strip at an eight-pixel tile
                    # boundary (the source strip is eleven pixels wide).
                    # Preserve Normal water's own palette bank;
                    # the other three columns retain the Normal rock face.
                    source = 4*16+ty*4+1
                raw = tiles[source*32:source*32+32]
                attr = attrs[source]
                if (cell == 0x0d or (cell == 0x10 and tx < 2)) and not attr & 0x2000:
                    # Palette-zero pen 5 is the donor's blue sky, not city
                    # material. Cut it out around the retained roof outline.
                    raw = bytes((0 if b >> 4 == 5 else b & 0xf0) |
                                (0 if b & 15 == 5 else b & 15) for b in raw)
                if cell in (0x2a, 0x2f, 0x3b, 0x3d) or (cell == 7 and ty < 3):
                    raw = bytes(((raw[y*4+3-x]&15)<<4)|(raw[y*4+3-x]>>4) for y in range(8) for x in range(4))
                if cell == 0x27:
                    # Source lower-right rock tip: first visible at y=26,
                    # widening from x=19 to x=16. Reuse Normal rock texture;
                    # this source cell was incorrectly mapped to blank.
                    clipped = bytearray(raw)
                    for py in range(8):
                        y = ty*8+py
                        left = 19 if y == 26 else 18 if y == 27 else 16
                        for px in range(8):
                            x = tx*8+px
                            if y < 26 or x < left or (y == 26 and x > 30):
                                at = py*4+px//2
                                clipped[at] &= 0x0f if px%2 == 0 else 0xf0
                    raw = bytes(clipped)
                    if not any(raw): attr = 0
                if cell in edges:
                    clipped = bytearray(raw)
                    for py in range(8):
                        left, right = edges[cell]['row_bounds'][ty*8+py]
                        for px in range(8):
                            if not left <= tx*8+px <= right:
                                at = py*4+px//2
                                clipped[at] &= 0x0f if px%2 == 0 else 0xf0
                    raw = bytes(clipped)
                    if not any(raw): attr = 0
                if blank:
                    raw, attr = bytes(32), 0
                packed.extend(raw)
                templates.append(0 if not attr else (attr & 0xe000) | ty*4+tx)
    # PCE quadrant 57 is plain floor, shared under rocks, arches and panels.
    # Whole Normal metatiles introduced unrelated supports into these halves.
    # Keep the reviewed upper shapes and use one consistent Normal floor below.
    floor = json.loads((ROOT/'tools/data/bc_background_r1_floor.json').read_text())
    for cell, quadrants in floor['quadrants'].items():
        cell = int(cell)
        for q in quadrants:
            for dy in range(2):
                for dx in range(2):
                    dest = cell*16 + (q//2*2+dy)*4 + q%2*2+dx
                    source = 34*16 + (2+dy)*4+dx
                    packed[dest*32:(dest+1)*32] = tiles[source*32:(source+1)*32]
                    templates[dest] = (attrs[source]&0xe000) | (dest%16)
    # Newly authored ledge/corner contours using our Normal stone/rock materials;
    # source-proven quadrant composition, not a whole-metatile identity match.
    replace_r1_ledge_family(tiles, attrs, packed, templates)
    from bc_background_r1_water import compose as compose_water
    compose_water(packed, templates, PALETTE)
    from bc_background_r1_cave import compose as compose_cave
    compose_cave(tiles, attrs, packed, templates)
    r1_palette = list(PALETTE)
    # Unused R1 PAL1 pen 15 restores the donor's darkest stone shade. Other
    # Normal/R1 material colors stay unchanged; the bright 445 -> 444 source
    # approximation is retained, with a distinct level in every relief ramp.
    r1_palette[31] = 0x0464  # RGB3 (2,3,2)
    (G/'bc_r1_material_pal.bin').write_bytes(struct.pack('>32H', *r1_palette))
    write_scenery(1, packed, templates, r1_palette, list(range(63))+[4095]*193)
    round_two()
    round_three()
    round_four()
    round_five()
    round_six()
    round_seven()
    round_eight()
    round_nine()
    round_ten()
    write_shared_scenery()

if __name__ == '__main__':
    main()
