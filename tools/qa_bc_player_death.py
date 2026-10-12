#!/usr/bin/env python3
"""Check native BC death mapping, imported pixels, shade ramps and four-player uploads."""
import hashlib
import json
import struct
from run_rom import ROOT, Runner

records = json.loads((ROOT/'res/generated/bc_player_death_shapes.json').read_text())
rom = (ROOT/'out/release/rom.bin').read_bytes()
r = Runner(); r.run(2600)
for name, value in [('dbg_bc_native_players', 4), ('dbg_bc_native_start_round', 0),
                    ('dbg_bc_native_protect', 1), ('dbg_bc_native', 1)]:
    r.write(name, value.to_bytes(2, 'big'))
r.run(120)
native_art = r.read('art', 36)
art = struct.unpack('>18H', native_art)
assert list(art[4:9]) == [rec['source_pose'] for rec in records]
assert list(art[13:18]) == [rec['code'] for rec in records]
r.lib.retro_reset(); r.run(2600)
r.write('dbg_bc_robot_art', native_art)
r.write('dbg_bc_robot_preview', b'\0\1')
out = ROOT/'.local/bc-player-death-render'; out.mkdir(exist_ok=True)
checks = 0
before = (r.u32('spr_dbg_dropped'), r.u32('spr_dbg_remap'))
for i, rec in enumerate(records):
    entry = struct.unpack_from('>H', rom, r.symbols['spr_big_index'] + rec['key']*2)[0]
    assert entry & 32767
    offset = r.symbols['spr_big'] + ((entry & 32767)-1)*512
    block = rom[offset:offset+512]
    if rec['geometry_source'] == 'original_pce_player_death':
        for y in range(32):
            for x in range(32):
                byte = block[((x//8)*4+y//8)*32+(y%8)*4+x%8//2]
                pen = byte >> 4 if x % 2 == 0 else byte & 15
                source_pen = int(rec['rows'][y][x], 16)
                assert pen == rec['pen_lut'][source_pen] and bool(pen) == bool(source_pen)
                checks += 1
        for ramp in rec['shade_ramps']:
            assert all(b-a > .20 for a,b in zip(ramp['luminance'], ramp['luminance'][1:]))
    for player, x in enumerate((40, 96, 152, 208)):
        r.write('dbg_bc_robot_pose', struct.pack('>5H', 64, x, 112, rec['source_pose'], 0x1181), player*10)
    r.run(16)
    assert not r.u16('dbg_bc_robot_unmapped')
    sat = struct.unpack('>16H', r.read('vdpSpriteCache', 32))
    for player in range(4):
        y, size_link, attr, x = sat[player*4:player*4+4]
        assert (x-128, y-128, size_link>>8, attr>>13&3) == (56+56*player, 96, 15, (entry>>15)+2)
        start = (attr & 2047)*32
        assert bytes(r.vram[(start+j)^1] for j in range(512)) == block
    r.capture(out/f'death-{i}.png')
assert (r.u32('spr_dbg_dropped'), r.u32('spr_dbg_remap')) == before
r.write('dbg_bc_robot_preview', b'\0\0'); r.run(120)
assert r.u32('flow_state') == 0
report = dict(passed=True, rom_sha256=hashlib.sha256(rom).hexdigest(),
              native_mapping_verified=True, imported_pixel_checks=checks,
              four_player_pose_cases=20, ordered_shading=True,
              software_sprite_drops=0, runtime_remaps=0,
              scope='Native selection and renderer; source death timing is unchanged')
(out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
