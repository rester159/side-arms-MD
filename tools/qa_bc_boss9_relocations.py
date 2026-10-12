#!/usr/bin/env python3
"""Compare original and round-nine boss frame addresses in the real renderer."""
import json
import struct
import numpy as np
from run_rom import ROOT, Runner
r=Runner(); r.run(2600)
cases=[
    (0x36b6,-0xdd7,[0xb4db,0xb4d6]),
    (0x36c4,0x7ef,[0xaec6,0xaee3,0xaf10,0xaf3d]),
    (0x36bc,0x527,[0xad00,0xad1d,0xad4a]),
    (0x36be,0x4c4,[0xaa1f,0xaa34,0xaa71]),
    (0x36b8,0x153b,[0xaeb2,0xaecf]),
    (0x36ba,-0x586,[0xb0a1,0xb0c2,0xb0ef]),
    (0x36c6,0xec9,[0xad2e,0xad7b,0xad98]),
    (0x36c0,0xcaa,[0xb2d2,0xb2ef,0xb324]),
    (0x36c2,0,[0xc77b,0xc7a0,0xc7cd]),
]
checked=0
for encounter,(ref,shift,frames) in enumerate(cases,1):
    selections=[(ref,frame) for frame in frames]
    if encounter==4:selections.append((0x36c8,0xab1d))
    if encounter==5:selections.extend((0x36ca,f) for f in (0xaf7d,0xaf97,0xafc9))
    original=[]
    for source in (0,9):
        r.write('dbg_bc_boss_preview',struct.pack('>H',encounter))
        r.write('dbg_bc_boss_source_round',struct.pack('>H',source))
        r.write('dbg_bc_actor_pose',bytes(224))
        r.write('dbg_bc_robot_preview',b'\0\1');r.run(8)
        drops=r.u32('spr_dbg_dropped');remaps=r.u32('spr_dbg_remap')
        for i,(base,frame) in enumerate(selections):
            if source:frame+=shift
            r.write('dbg_bc_actor_pose',struct.pack('>7H',base,0,frame,0x88,176,112,128))
            r.run(4)
            assert not r.u16('dbg_bc_actor_unmapped'),(encounter,source,hex(frame))
            if not source:original.append(r.frame.copy())
            else:
                assert np.array_equal(original[i],r.frame),(encounter,hex(frame))
                checked+=1
        assert r.u32('spr_dbg_dropped')==drops and r.u32('spr_dbg_remap')==remaps
        r.write('dbg_bc_robot_preview',b'\0\0');r.run(30)
        assert 255 not in r.read('slot_refs',56)
result=dict(encounters=9,matched_frames=checked,sprite_drops=0,runtime_remaps=0,
            native_round_nine_gameplay=False)
print(json.dumps(result,indent=2))
