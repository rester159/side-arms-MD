#!/usr/bin/env python3
"""Check BC R1 tile-mapping isolation and shared source-quadrant consistency."""
import argparse, hashlib, json, struct
from pathlib import Path
from bc_background_equivalence import symbols, rendered_cell, compare_round
from bc_background_r1_cave import CELLS
from vivid_palette import base_lut, index
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--before',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
old=(a.before/'rom.bin').read_bytes();rom=Path('out/release/rom.bin').read_bytes()
os=symbols(a.before/'symbol.txt');sy=symbols(Path('out/release/symbol.txt'))
previous=struct.unpack_from('>256H',old,os['bc_bg_remap']);remap=struct.unpack_from('>256H',rom,sy['bc_bg_remap'])
pal=struct.unpack_from('>32H',rom,sy['bc_bg_palette'])
# The layout labels must agree with the original BC quadrant table.
for cell,patterns in CELLS.items():
    at=sy['bc_round1_code']+0x6220+cell*8
    assert patterns==tuple((rom[at+q*2],rom[at+q*2+1]>>4) for q in range(4)),('source quadrant table',cell)
changed=[];opaque=0;water=0;seen={};quadrants=0
for cell,(x,y) in enumerate(zip(previous,remap)):
    assert (x==4095)==(y==4095)
    if x==4095:continue
    before=rendered_cell(old,os,'bc_bg',x);after=rendered_cell(rom,sy,'bc_bg',y)
    opaque+=len(before)
    if before!=after:
        assert cell in set(CELLS),('unrelated cell',cell)
        changed.append(cell)
    if cell in (0x13,0x14,0x15):
        for b,c in zip(before,after):
            color=pal[((b[1]>>13)&1)*16+b[0]] if b and b[0] else 0
            if color and not color&14 and color&0xe00:
                assert b==c,('water phase',cell);water+=1
    if cell in CELLS:
        for q,key in enumerate(CELLS[cell]):
            block=[after[(q//2*16+j)*32+q%2*16+i] for j in range(16) for i in range(16)]
            if key in seen:assert block==seen[key],('cave join',cell,q,key)
            seen[key]=block;quadrants+=1
for name,size in [('bc_round1_code',65536),('bc_bg_palette',64),('vivid_lut',1024),('zone0_vivid_pal',64)]:
    assert old[os[name]:os[name]+size]==rom[sy[name]:sy[name]+size],name
normal=0
for path in Path('res/generated').glob('zone*.bin'):
    if path.stem not in sy or path.stem not in os:continue
    size=path.stat().st_size
    assert old[os[path.stem]:os[path.stem]+size]==rom[sy[path.stem]:sy[path.stem]+size],path.stem
    normal+=1
classic=base_lut()
assert struct.unpack_from('>32H',rom,sy['bc_bg_vivid_palette'])==tuple(classic[index(c)] for c in pal)
rounds=[compare_round(old,os,rom,sy,n) for n in range(2,11)]
assert changed and water and quadrants
report=dict(passed=True,rom_sha256=hashlib.sha256(rom).hexdigest(),changed_cells=changed,
    resolved_pixels=opaque,shared_cave_quadrants=quadrants,water_pixels=water,
    normal_blobs_unchanged=normal,other_bc_rounds_unchanged=rounds,
    source_collision_and_events_unchanged=True,vivid_uses_normal_original_transform=True)
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
