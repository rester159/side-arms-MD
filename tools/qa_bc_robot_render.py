#!/usr/bin/env python3
"""Render BC-selected poses using our robot assets in a Genesis debug view.
This is an artwork/cache test, not a playable BC scene or a frame-rate test.
"""
import argparse
import json
from pathlib import Path
import struct
import numpy as np
from run_rom import Runner,ROOT

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--code',type=Path,required=True)
p.add_argument('--rom',type=Path,default=ROOT/'out/release/rom.bin')
p.add_argument('--out',type=Path,default=ROOT/'.local/bc-robot-render')
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
program=a.code.read_bytes()
def word(address):return struct.unpack_from('<H',program,address-0x4000)[0]
shift=program.index(bytes.fromhex('bdcc2df0273a9dcc2dd02c'))+0x4000-0x9204
script=word(0x9ba7+shift+30)
source=[word(0x9c07+shift+18+i*2) for i in range(4)]+[word(script+2+i*2) for i in range(5)]
death_records=json.loads((ROOT/'res/generated/bc_player_death_shapes.json').read_text())
genesis=[0x22,0x26,0x62,0x72]+[record['code'] for record in death_records]
r=Runner(rom=a.rom);r.run(2600)
r.write('dbg_bc_robot_art',struct.pack('>18H',*(source+genesis)))
r.write('dbg_bc_robot_preview',b'\0\1')
results=[]
for name,index,attributes in [('idle-right',0,0x1180),('idle-left',0,0x1980),('firing-right',1,0x1180),('entry-early',2,0x1180),('entry-late',3,0x1180)]+[(f'death-{i}',4+i,0x1181) for i in range(5)]:
    for i,x in enumerate((40,96,152,208)):
        r.write('dbg_bc_robot_pose',struct.pack('>5H',128 if index<4 else 64,x,112,source[index],attributes),i*10)
    r.run(16);assert r.u16('dbg_bc_robot_unmapped')==0,name
    regions=[r.frame[96:128,56+i*56:88+i*56,:3] for i in range(4)]
    assert all(np.any(region) for region in regions),(name,'missing robot')
    if index<4:
        assert not np.array_equal(regions[0],regions[2]),(name,'P3 recolor missing')
        assert not np.array_equal(regions[1],regions[3]),(name,'P4 recolor missing')
    path=a.out/(name+'.png');r.capture(path)
    results.append(dict(pose=name,path=str(path),unmapped=0))
projectile_results=[]
frames=list(range(0x1a8,0x1c8,2))+[0x1d4,0x1d6,0x1e0,0x1e2,0x1e4,0x1e6]
r.write('dbg_bc_robot_pose',bytes(40))
for facing in (0,1):
    for batch in range(0,len(frames),16):
        selected=frames[batch:batch+16]
        r.write('dbg_bc_projectile_pose',bytes(160))
        for i,frame in enumerate(selected):
            x,y=32+(i%4)*64,40+(i//4)*48
            r.write('dbg_bc_projectile_pose',struct.pack('>5H',frame,x,y,0,facing),i*10)
        r.run(16)
        assert r.u16('dbg_bc_projectile_unmapped')==0
        for i,frame in enumerate(selected):
            x,y=64+(i%4)*64,40+(i//4)*48
            assert np.any(r.frame[y-8:y+8,x-8:x+8,:3]),(hex(frame),'missing projectile')
        path=a.out/('projectiles-%d-%d.png'%(facing,batch//16))
        r.capture(path)
        projectile_results.append(dict(facing=facing,frames=[hex(v) for v in selected],path=str(path)))
r.write('dbg_bc_robot_preview',b'\0\0');r.run(120)
assert r.u32('flow_state')==0,'Inspection must return to the mode-selection screen'
result=dict(module='Genesis BC artwork inspection',poses=results,projectiles=projectile_results,returned_to_game=True,
            playable_bc=False,performance_verified=False)
(a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
