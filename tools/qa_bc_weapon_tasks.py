#!/usr/bin/env python3
"""Compare native weapons/contacts/trail in original task execution order.

Video-frame snapshots can cut between (or within) cooperative source tasks.
This trace compares completed tasks while carrying native state continuously.
Enemy motion/HP inputs still come from the source, not a complete native world.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import Beam,decode,ROOT
from qa_bc_rules import Charge,Terrain
from qa_bc_weapons import Weapons,Event,Target,Hit


def verify(capture,code):
    raw=(capture/'weapon-tasks.bin').read_bytes();stride=8198
    assert raw and len(raw)%stride==0
    program=code.read_bytes();rom=(C.c_uint8*len(program)).from_buffer_copy(program)
    cells=(C.c_uint8*16384).from_buffer_copy(program[0xc000:])
    signature=bytes.fromhex('bdcc2df0273a9dcc2dd02c');assert program.count(signature)==1
    shift=program.index(signature)+0x4000-0x9204
    custom={a+shift for a in (0x9204,0x9399,0x923e,0x9413,0x953a,0x998a,0x9ca8,0x9d22)}
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'rules.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        str(ROOT/'src/bc_rules.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path))
        lib.bc_weapons_step.argtypes=[C.POINTER(Weapons)]+[C.c_uint8]*6+[C.c_uint16]*4+[C.POINTER(Terrain)]
        lib.bc_weapons_step.restype=Event
        lib.bc_weapons_step_into.argtypes=[C.POINTER(Event)]+lib.bc_weapons_step.argtypes
        lib.bc_weapons_step_into.restype=None
        lib.bc_weapons_record_position.argtypes=[C.POINTER(Weapons),C.c_uint16,C.c_uint16]
        lib.bc_enemy_shots.argtypes=[C.POINTER(Target),C.POINTER(Weapons)];lib.bc_enemy_shots.restype=Hit
        w=Weapons();initial=raw[6:stride]
        assert not any(initial[0xa48:0xa64]),'Start before ordinary projectile launches'
        for i in range(30):
            s=w.shots[i];s.body=decode(initial,i)
            if s.body.state:
                assert i>=28 and s.body.state==0x80
                s.kind=4;s.tier=initial[0xdea+i];s.launch_wait=initial[0xc28+i]
                s.body.accelerating=1;s.body.facing=initial[0xdae+i]==0x52
        w.charge=Charge(initial[0x56],initial[0x55],initial[0x57],initial[0xaa]==0x52)
        w.returning=initial[0x5a];w.option_shots[:]=initial[0x5b:0x5d];w.trail[:]=initial[0xb4:0xc4]
        pending=None;contact=None;updates=ordinary=options=beams=scans=trails=0;families=set()
        def compare(r,f,phase):
            assert w.returning==r[0x5a],(f,phase,'return counter',w.returning,r[0x5a])
            assert bytes(w.option_shots)==r[0x5b:0x5d],(f,phase,'option counters')
            assert bytes(w.trail)==r[0xb4:0xc4],(f,phase,'trail')
            for i,s in enumerate(w.shots):
                expected=decode(r,i)
                assert s.body.state==expected.state,(f,phase,i,'state',s.body.state,expected.state)
                if not s.body.state:continue
                expected.facing=(r[0xac] if s.kind==3 else r[0xdae+i])==0x52
                expected.accelerating=(r[0xcdc+i]*256+r[0xcfa+i]) in custom
                for field,_ in Beam._fields_:
                    assert getattr(s.body,field)==getattr(expected,field),(f,phase,i,s.kind,field,getattr(s.body,field),getattr(expected,field))
                if s.kind in (2,4):assert s.launch_wait==r[0xc28+i],(f,phase,i,'launch wait')
                if s.kind==4:assert s.tier==r[0xdea+i],(f,phase,i,'HP')
        for off in range(0,len(raw),stride):
            f,task,i=struct.unpack_from('<IBB',raw,off);r=raw[off+6:off+stride]
            if task==0:
                assert pending is None and contact is None,(f,'nested weapon task')
                compare(r,f,'entry')
                attrs=r[0x44]+r[0x45]*256-0x4000
                terrain=Terrain(cells,C.cast(C.byref(rom,attrs),C.POINTER(C.c_uint8)))
                before=Weapons.from_buffer_copy(bytes(w))
                args=(r[0x228],r[0x22d],r[0x94]==0x80,r[0xad],r[0xa5],r[0xae],
                    r[0x95]*256+r[0x96],r[0x98]*256+r[0x99],r[0x2e]*256+r[0x2f],r[0x31]*256+r[0x32],C.byref(terrain))
                event=Event();C.memset(C.byref(event),0xa5,C.sizeof(event))
                lib.bc_weapons_step_into(C.byref(event),C.byref(w),*args)
                legacy=lib.bc_weapons_step(C.byref(before),*args)
                assert bytes(event)==bytes(legacy) and bytes(w)==bytes(before),(f,'weapon output API')
                pending=event
            elif task==1:
                assert pending is not None,(f,'unmatched weapon exit')
                compare(r,f,'exit');updates+=1
                ordinary+=pending.shots;options+=pending.option_shots;beams+=pending.beams
                if pending.recoil:assert pending.recoil==r[0xa8],(f,'recoil')
                assert tuple(getattr(w.charge,n) for n,_ in Charge._fields_)==(r[0x56],r[0x55],r[0x57],int(r[0xaa]==0x52)),(f,'charge')
                families.update(s.kind for s in w.shots if s.body.state);pending=None
            elif task==2:
                assert pending is None and contact is None,(f,'trail inside task')
                compare(r,f,'trail')
                lib.bc_weapons_record_position(C.byref(w),r[0x95]*256+r[0x96],r[0x98]*256+r[0x99]);trails+=1
            elif task==3:
                assert pending is None and contact is None,(f,'nested contact')
                compare(r,f,'contact')
                t=Target(r[0xe28+i]*256+r[0xe48+i],r[0xe88+i]*256+r[0xea8+i],
                    r[0x1068+i],r[0x1088+i],r[0x1148+i],r[0x1028+i],r[0x10c8+i],r[0x1108+i])
                hit=lib.bc_enemy_shots(C.byref(t),C.byref(w));contact=(i,t,hit)
            else:
                assert task in (4,5) and contact is not None and contact[0]==i,(f,task,'contact exit')
                _,t,hit=contact
                assert t.hp==r[0x1028+i] and bool(hit.depleted)==(task==5),(f,i,'enemy damage')
                compare(r,f,'contact exit');contact=None;scans+=1
        assert pending is None and contact is None,'Capture ended inside a task'
        return dict(module='continuous weapon pool in source task order',weapon_updates=updates,
                    main_launches=ordinary,option_launches=options,beam_segments=beams,
                    native_collision_scans=scans,trail_updates=trails,families=sorted(families),whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code),indent=2))
