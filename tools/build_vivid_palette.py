#!/usr/bin/env python3
"""Finalize Vivid after Normal and BC palettes and shade metadata are built."""
import hashlib
import itertools
import json
from pathlib import Path
import struct

from vivid_palette import base_lut, guard, index, light, rgb, word

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT/'res/generated'


def read_words(path):
    raw = path.read_bytes()
    return list(struct.unpack('>'+str(len(raw)//2)+'H', raw))


def constraints(gen=GEN):
    paths = sorted(p for p in gen.glob('zone*_pal.bin') if p.name != 'zone0_vivid_pal.bin') + [gen/name for name in (
        'sprite_pal.bin', 'bc_sprite_pal.bin', 'organic_belly_pal.bin',
        'bc_r1_material_pal.bin', 'bc_r2_material_pal.bin', 'bc_r3_material_pal.bin', 'bc_r4_material_pal.bin', 'bc_r5_material_pal.bin', 'bc_r6_material_pal.bin', 'bc_r7_material_pal.bin', 'bc_r8_material_pal.bin', 'bc_r9_material_pal.bin', 'bc_r10_material_pal.bin')]
    palettes = {}
    for path in paths:
        values = read_words(path)
        if path.stem == 'zone0_pal':
            # Stage 1 uses its dedicated v1.2 Vivid palette. Keep the shared
            # guard's v2 constraints stable for all other stages and sprites.
            fit = json.loads((ROOT/'tools/data/normal_zone0_palette_fit.json').read_text())
            values = [v for bank in fit['banks'] for v in [0] + bank]
        if path.stem == 'bc_r1_material_pal':
            values = read_words(gen/'bc_r1_donor_pal.bin')
            values[31] = 0x0464
        assert len(values) % 16 == 0
        for offset in range(0, len(values), 16):
            palettes[f'{path.stem}:{offset//16}'] = values[offset:offset+16]
    # Match bc_scene.c:gallery_colors, including its white highlight.
    for bank in range(2):
        gold = [0]
        for pen, value in enumerate(palettes[f'sprite_pal:{bank}'][1:], 1):
            if pen == 15:
                value = 0  # gallery_colors preserves its original spare pen
            r, g, b = rgb(value)
            level = ((r*6+g*12+b*2)//10) & 14
            gold.append(word((7, 7, 7) if level == 14 else
                             (level//2, level*5//14, level*2//14)))
        palettes[f'gallery:{bank}'] = gold
    edges = set()
    for palette in palettes.values():
        colors = sorted(set(palette[1:]), key=lambda v: (light(v), v))
        for a, b in itertools.combinations(colors, 2):
            # Only componentwise shade steps: do not order unrelated hues.
            if all(x <= y for x, y in zip(rgb(a), rgb(b))):
                edges.add((a, b, min(200, light(b)-light(a))))

    ramps = []
    for name in ('bc_sprite_recolors', 'bc_boss_shots', 'bc_serpent_shapes',
                 'bc_player_death_shapes', 'bc_player_projectile_shapes',
                 'bc_boss_geometry'):
        data = json.loads((gen/(name+'.json')).read_text())
        if name == 'bc_boss_geometry':
            data = [p for bank in data['banks'] for p in bank['poses']]
        for record in data:
            bank = record.get('palette')
            if not record.get('shade_ramps'):
                continue
            normal = name == 'bc_sprite_recolors' and 'geometry_source' not in record
            # Beam metadata explicitly numbers source pens 1..5; fit_shades
            # imports number the 15 opaque source colors from zero.
            shift = 0 if normal or record.get('geometry_source') == 'bc_beam_shapes' else 1
            palette_name = 'gallery' if normal and record['source_palette'] == 15 else 'bc_sprite_pal'
            palette = palettes[f'{palette_name}:{bank}']
            for ramp in record['shade_ramps']:
                values = []
                for pens, expected in zip(ramp['pens'], ramp['luminance']):
                    colors = {palette[record['pen_lut'][p+shift]] for p in pens}
                    assert len(colors) == 1, (name, record.get('id'), pens)
                    value = colors.pop()
                    assert abs(light(value)/1000-expected) < .001, (name, pens, expected, rgb(value))
                    values.append(value)
                for a, b in zip(values, values[1:]):
                    edges.add((a, b, 200))
                ramps.append(dict(source=name, id=record.get('id', record.get('frame', record.get('source_pose'))),
                                  colors=values))
    geometry = json.loads((gen/'bc_r2_material_shading.json').read_text())
    r2_colors = set(read_words(gen/'bc_r2_material_pal.bin'))
    for ramp in geometry.get('shade_ramps', []):
        values = ramp['colors']
        assert set(values) <= r2_colors
        assert len(set(values)) == len(values)
        for a,b in zip(values, values[1:]):
            assert light(a) < light(b)
            edges.add((a,b,min(200,light(b)-light(a))))
        ramps.append(dict(source='bc_r2_geometry', id=ramp['id'], colors=values))
    return palettes, sorted(edges), ramps


def main():
    palettes, edges, ramps = constraints()
    before = base_lut()
    after = guard(before, edges)
    # Shade recovery can change the greedy guard's fallback choices. Retain
    # explicitly reviewed existing Vivid colors when they still satisfy every
    # current palette and imported-art ramp constraint.
    repairs = json.loads((ROOT/'tools/data/normal_background_shade_repairs.json').read_text())
    fitted = [json.loads(path.read_text()) for path in sorted((ROOT/'tools/data').glob('normal_zone*_palette_fit.json'))]
    selective = json.loads((ROOT/'tools/data/normal_selective_shade_repairs.json').read_text())
    for repair in repairs['repairs'] + fitted + [selective]:
        for source, output in repair.get('vivid_preserve', {}).items():
            after[index(int(source))] = output
    assert all(light(after[index(b)])-light(after[index(a)]) >= gap
               for a, b, gap in edges), 'Preserved Vivid color violates a shade ramp'
    raw = struct.pack('>512H', *after)
    (GEN/'vivid_lut.bin').write_bytes(raw)
    report = dict(schema=1, palette_banks=len(palettes), explicit_ramps=len(ramps),
                  ordered_pairs=len(edges),
                  violations_before=sum(light(before[index(b)])-light(before[index(a)]) < gap
                                        for a, b, gap in edges),
                  violations_after=0,
                  changed_entries=sum(a != b for a, b in zip(before, after)),
                  lut_sha256=hashlib.sha256(raw).hexdigest(),
                  scope='Post-fit shade ordering in Vivid; does not recover upstream quantization losses.')
    (GEN/'vivid_shading.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
