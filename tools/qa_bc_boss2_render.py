#!/usr/bin/env python3
"""Verify the BC-specific round-two boss patterns, palettes and articulated hardware positions."""
import json
import struct
import numpy as np
from run_rom import ROOT,Runner
meta=json.loads((ROOT/'res/generated/bc_boss2_geometry.json').read_text())
r=Runner();r.run(2600)
r.write('dbg_bc_boss_preview',b'\0\2');r.write('dbg_bc_robot_preview',b'\0\1')
r.run(30)
assert r.read('slot_refs',56).count(255)==meta['block_count']
out=ROOT/'.local/bc-boss2-render';out.mkdir(parents=True,exist_ok=True)
rom=(ROOT/'out/release/rom.bin').read_bytes();addr=r.symbols['bc_boss2_patterns']
# Resident blocks are allocated in the background cache; verify the exact ROM patterns.
slots=[i for i,v in enumerate(r.read('slot_refs',56)) if v==255]
for i,slot in enumerate(reversed(slots)):
    at=(160+slot*16)*32
    assert bytes(r.vram[(at+j)^1] for j in range(512))==rom[addr+i*512:addr+(i+1)*512]
initial=r.u32('spr_dbg_remap');captures=[]
for phase in (24,32,42):
    for i,(frame,x,y) in enumerate(((0xaec6,120,112),(0xaee3,128,112-phase),(0xaf10,128,112+phase),(0xaf3d,88,112))):
        r.write('dbg_bc_actor_pose',struct.pack('>7H',0x36c4,0,frame,0x88,x,y,128),i*14)
    r.run(12)
    assert not r.u16('dbg_bc_actor_unmapped') and np.count_nonzero(r.frame)>1000
    expected=[]
    for frame,x,y in ((0xaec6,120,112),(0xaee3,128,112-phase),(0xaf10,128,112+phase)):
        pose=next(p for p in meta['poses'] if p['frame']==frame)
        for piece in meta['pieces'][pose['first']:pose['first']+pose['count']]:
            expected.append((x+32+piece['x'],y+piece['y'],pose['palette']+2,piece['flags']))
    sat=struct.unpack('>44H',r.read('vdpSpriteCache',88))
    assert [(sat[i*4+3]-128,sat[i*4]-128,sat[i*4+2]>>13&3,sat[i*4+2]>>11&3) for i in range(11)]==expected
    assert all(sat[i*4+1]>>8==15 for i in range(11))
    assert [sat[i*4+1]&127 for i in range(11)]==list(range(1,11))+[0]
    path=out/f'opening-{phase}.png';r.capture(path);captures.append(str(path))
assert r.u32('spr_dbg_remap')==initial
r.write('dbg_bc_robot_preview',b'\0\0');r.run(120)
assert r.u32('flow_state')==0 and 255 not in r.read('slot_refs',56)
result=dict(captures=captures,resident_blocks=meta['block_count'],runtime_remaps=0,returned_to_menu=True,
            source_geometry_verified=True,genesis_palette_approximation=True,native_round_two_gameplay=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
