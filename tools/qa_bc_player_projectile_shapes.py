#!/usr/bin/env python3
"""Verify original weapon pixels, live capture correspondence and native flipped uploads."""
import hashlib
import json
import struct
from run_rom import ROOT, Runner
from qa_bc_beam import decode

records = json.loads((ROOT/'res/generated/bc_player_projectile_shapes.json').read_text())
required = set(range(0x1a8,0x1c8,2)) | {0x1d4,0x1d6,0x1e0,0x1e2,0x1e4,0x1e6}
assert len(records)==len(required) and {rec['source_pose'] for rec in records}==required
rom = (ROOT/'out/release/rom.bin').read_bytes()
r = Runner(); r.run(2600); r.write('dbg_bc_robot_preview', b'\0\1')
out = ROOT/'.local/bc-player-projectile-render'; out.mkdir(exist_ok=True)
pixels = cases = 0
before = (r.u32('spr_dbg_dropped'), r.u32('spr_dbg_remap'))
for rec in records:
    path = ROOT/rec['ram']
    raw = {kind: path.with_name(path.name.replace('-ram','-'+kind)).read_bytes()
           for kind in ('ram','sat','vram','palette')}
    assert all(hashlib.sha256(data).hexdigest()==rec['source_hashes'][kind] for kind,data in raw.items())
    beam = decode(raw['ram'],rec['slot'])
    sat = struct.unpack('<256H',raw['sat'])
    y,x,pattern,attrs = sat[rec['sat_slot']*4:rec['sat_slot']*4+4]
    assert beam.state and pattern==beam.sprite==rec.get('source_anchor_pose',rec['source_pose']) and attrs==beam.attributes
    assert (x-24,y-56)==(beam.x>>8,beam.y>>8)
    pattern = rec['source_pose']
    vram = struct.unpack('<32768H',raw['vram'])
    entry = struct.unpack_from('>H',rom,r.symbols['spr_bank_index']+rec['key']*2)[0]
    offset = r.symbols['spr_bank']+((entry&32767)-1)*128
    block = rom[offset:offset+128]
    normal_block = None
    if rec['decision'] in ('keep','recolor'):
        normal_key = rec['normal_code'] | rec['normal_colour'] << 11
        normal_entry = struct.unpack_from('>H',rom,r.symbols['spr_bank_index']+normal_key*2)[0]
        normal_offset = r.symbols['spr_bank']+((normal_entry&32767)-1)*128
        normal_block = rom[normal_offset:normal_offset+128]
        if rec['decision']=='keep':
            assert block==normal_block and entry==normal_entry
    silhouette_differences = 0
    for y in range(16):
        for x in range(16):
            source = sum(((vram[(pattern>>1)*64+y+plane*16]>>(15-x))&1)<<plane for plane in range(4))
            assert source==int(rec['source_rows'][y][x],16)
            b = block[((x//8)*2+y//8)*32+y%8*4+x%8//2]
            pen = b>>4 if x%2==0 else b&15
            region = source
            if normal_block is not None:
                n = normal_block[((x//8)*2+y//8)*32+y%8*4+x%8//2]
                region = n>>4 if x%2==0 else n&15
                assert region==int(rec['normal_rows'][y][x],16)
            assert pen==rec['pen_lut'][region] and bool(pen)==bool(region)
            silhouette_differences += bool(pen)!=bool(source)
            pixels += 1
    assert silhouette_differences==rec.get('silhouette_difference_pixels',0)
    for ramp in rec['shade_ramps']:
        assert all(b-a>.20 for a,b in zip(ramp['luminance'],ramp['luminance'][1:]))
    for facing in (0,1):
        expected_entry,expected_block = entry,block
        if 'directional_codes' in rec:
            key=rec['directional_codes'][facing] | rec['normal_colour']<<11
            expected_entry=struct.unpack_from('>H',rom,r.symbols['spr_bank_index']+key*2)[0]
            start=r.symbols['spr_bank']+((expected_entry&32767)-1)*128
            expected_block=rom[start:start+128]
        for flip,attrs in enumerate((0,0x800,0x8000,0x8800)):
            r.write('dbg_bc_projectile_pose',struct.pack('>5H',pattern,128,112,attrs,facing))
            r.run(8); assert not r.u16('dbg_bc_projectile_unmapped')
            y,size,attr,x = struct.unpack('>4H',r.read('vdpSpriteCache',8))
            expected_flip=0 if 'directional_codes' in rec else flip
            assert (x-128,y-128,size>>8,attr>>11&3,attr>>13&3)==(152,104,5,expected_flip,(expected_entry>>15)+2)
            start=(attr&2047)*32
            assert bytes(r.vram[(start+j)^1]for j in range(128))==expected_block
            preview_facing=rec['facing'] if 'directional_codes' in rec else 0
            if facing==preview_facing and not flip:r.capture(out/f'projectile-{pattern:03x}.png')
            cases += 1
assert before==(r.u32('spr_dbg_dropped'),r.u32('spr_dbg_remap'))
r.write('dbg_bc_robot_preview',b'\0\0'); r.run(120); assert r.u32('flow_state')==0
report=dict(passed=True,rom_sha256=hashlib.sha256(rom).hexdigest(),source_pixel_checks=pixels,
            classified_weapon_poses=len(records),decisions={kind:sum(r['decision']==kind for r in records) for kind in ('keep','recolor','new')},
            loaded_bank_poses=[r['source_pose'] for r in records if r.get('source_kind')=='loaded-bank'],
            native_flip_facing_cases=cases,ordered_shading=True,software_drops=0,runtime_remaps=0)
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2))
