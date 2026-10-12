#!/usr/bin/env python3
"""Inspect real Genesis-rendered BC enemy creature/projectile/effect art selections."""
import json
import struct
import numpy as np
from run_rom import ROOT,Runner
r=Runner();r.run(2600);r.write('dbg_bc_robot_preview',b'\0\1')
cases=[]
for ref,base,offsets,attr in [(0x3696,0x400,[0,8,16,18,20],0x1188),(0x36ce,0x400,[0,2],0x81),(0x367c,0x1e0,range(0,8,2),0x81),
        (0x367e,0x1e8,range(0,56,8),0x1181),(0x3682,0x220,range(0,10,2),0x85),
        (0x3684,0x230,range(0,10,2),0x85),(0x3698,0x23a,[0],0x81),
        (0x36cc,0x400,range(0,32,2),0x82),
        (0x36cc,0x400,range(14,32,2),0x81),
        (0x36c8,0x358,[0,2],0x81),(0x367a,0x1a8,[0x20,0x24,0x26,0x28,0x2a,0x2c,0x2e,0x30,0x32,0x34,0x36],0x81),
        (0x368c,0x288,range(0,64,8),0x1186),(0x3692,0x2c8,range(0,40,8),0x1187),
        (0x368e,0x250,range(0,56,8),0x1185),(0x3686,0x2f0,range(0,24,8),0x1183),
        (0x3686,0x2f0,range(0,24,8),0x1184),
        (0x3694,0x400,range(0,32,8),0x1187),(0x36aa,0x400,range(0,10,2),0x89),(0x369c,0x400,[0],0x10d),
        (0x369c,0x400,[0],0x10e),(0x36b0,0x400,[0,8,16,24],0x118b),(0x36b2,0x400,[0,8],0x118c),
        (0x369a,0x400,[0,8,16,24],0x1183),(0x36ac,0x400,[0,8],0x1187),
        (0x36b4,0x400,[0],0x89),(0x36ae,0x400,[0,8],0x1188),(0x368a,0x400,range(0,40,8),0x118b),
        (0x3690,0x400,range(0,64,8),0x118b),
        (0x369e,0x400,range(0,10,2),0x89),(0x36a0,0x400,range(0,10,2),0x89),
        (0x36a2,0x400,range(0,10,2),0x89),(0x36a4,0x400,range(0,10,2),0x8a),
        (0x36a6,0x400,range(0,10,2),0x8a),(0x36a8,0x400,range(0,10,2),0x8a),
        (0x3682,0x220,[10,12,14],0x85),(0x3688,0x308,range(0,56,8),0x1185)]:
    for flip in ((0,0x800,0x8000,0x8800) if ref in (0x3696,0x36ce,0x367a,0x3682,0x3684,0x36c8,0x36cc,0x368c,0x3692,0x368e,0x3686,0x3688,0x3694,0x36aa,0x369c,0x36ae,0x36b0,0x36b2,0x369a,0x36ac,0x36b4,0x368a,0x3690,0x369e,0x36a0,0x36a2,0x36a4,0x36a6,0x36a8) else (0,)):
        for offset in offsets:cases.append((ref,base,base+offset,attr|flip))
out=ROOT/'.local/bc-actor-render';out.mkdir(parents=True,exist_ok=True)
results=[]
initial_remaps=r.u32('spr_dbg_remap');initial_drops=r.u32('spr_dbg_dropped')
for batch in range(0,len(cases),12):
    selected=cases[batch:batch+12];r.write('dbg_bc_actor_pose',bytes(224))
    for i,case in enumerate(selected):
        x,y=32+(i%3)*80,32+(i//3)*48
        r.write('dbg_bc_actor_pose',struct.pack('>7H',*case,x,y,128),i*14)
    r.run(24);assert r.u16('dbg_bc_actor_unmapped')==0
    for i,case in enumerate(selected):
        x,y=64+(i%3)*80,32+(i//3)*48
        assert np.any(r.frame[y-16:y+16,x-16:x+16]),('missing pixels',case)
    path=out/('batch-%02d.png'%(batch//12));r.capture(path)
    results.append(dict(path=str(path),cases=[[hex(v) for v in case] for case in selected]))
remaps=r.u32('spr_dbg_remap')-initial_remaps;drops=r.u32('spr_dbg_dropped')-initial_drops
r.write('dbg_bc_robot_preview',b'\0\0');r.run(120)
assert r.u32('flow_state')==0
result=dict(rendered_selections=len(cases),batches=results,runtime_remaps=remaps,sprite_drops=drops,returned_to_menu=True,complete_enemy_art=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
