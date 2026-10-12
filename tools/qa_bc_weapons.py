#!/usr/bin/env python3
"""Compare the integrated BC main-weapon pool with source RAM and contact events.
With contacts.bin, native overlap/damage replaces contact-event replay. Enemy
movement/phase/score and audio remain outside this check. For captures with
tasks crossing video-frame boundaries, use qa_bc_weapon_tasks.py instead.
"""
import argparse
import csv
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import Beam, decode, ROOT
from qa_bc_shots import Shot
from qa_bc_rules import Charge, Terrain


class Weapons(C.Structure):
    _fields_ = [('shots', Shot * 30), ('charge', Charge), ('returning', C.c_uint8),
                ('option_shots',C.c_uint8*2),('trail',C.c_uint8*16)]


class Event(C.Structure):
    _fields_ = [(n, C.c_uint8) for n in ('shots','beams','shot_sound','charge_sound','recoil','option_shots')]


class Target(C.Structure):
    _fields_=[('x',C.c_uint16),('y',C.c_uint16)]+[(n,C.c_uint8) for n in
        ('half_x','half_y','flags','hp','cooldown','damage_lock')]


class Hit(C.Structure):
    _fields_=[(n,C.c_uint8) for n in ('contacts','damaged','depleted','slot')]


def verify(capture, code, input_path=None):
    raw=(capture/'state.bin').read_bytes();assert raw and len(raw)%8196==0
    records=[(struct.unpack_from('<I',raw,i)[0],raw[i+4:i+8196]) for i in range(0,len(raw),8196)]
    program=code.read_bytes();data=(C.c_uint8*len(program)).from_buffer_copy(program)
    cells=(C.c_uint8*16384).from_buffer_copy(program[0xc000:])
    signature=bytes.fromhex('bdcc2df0273a9dcc2dd02c')
    assert program.count(signature)==1
    relocation=program.index(signature)+0x4000-0x9204
    custom={a+relocation for a in (0x9204,0x9399,0x923e,0x9413,0x953a,0x998a,0x9ca8,0x9d22)}
    injected={}
    if input_path:
        for line in input_path.read_text().splitlines():
            p=line.split()
            if len(p)==4 and p[1]=='poke' and int(p[2],16) in (0x1f0a64,0x1f0a65) and int(p[3],16)==0x40:
                injected.setdefault(int(p[0]),[]).append(int(p[2],16)-0x1f0a48)
    hits={}
    with (capture/'writes.csv').open() as f:
        for row in csv.DictReader(f):
            if row['pc']=='a0ba' and row['value']=='40':
                hits.setdefault(int(row['frame']),[]).append(int(row['address'],16)-0x1f0a48)
    scans={}
    contact_file=capture/'contacts.bin'
    if contact_file.exists():
        contact_raw=contact_file.read_bytes();stride=8198
        assert contact_raw and len(contact_raw)%(stride*2)==0
        for off in range(0,len(contact_raw),stride*2):
            f,index,phase=struct.unpack_from('<IBB',contact_raw,off)
            f2,i2,p2=struct.unpack_from('<IBB',contact_raw,off+stride)
            assert (f,index,phase)==(f2,i2,0) and p2 in (1,2)
            scans.setdefault(f,[]).append((index,contact_raw[off+6:off+stride],
                                           contact_raw[off+stride+6:off+stride*2],p2))
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'rules.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
                        '-I'+str(ROOT/'inc'),str(ROOT/'src/bc_rules.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path))
        lib.bc_weapons_step.argtypes=[C.POINTER(Weapons)]+[C.c_uint8]*6+[C.c_uint16]*4+[C.POINTER(Terrain)]
        lib.bc_weapons_step.restype=Event
        lib.bc_weapons_record_position.argtypes=[C.POINTER(Weapons),C.c_uint16,C.c_uint16]
        lib.bc_shot_hit.argtypes=[C.POINTER(Shot)]
        lib.bc_enemy_shots.argtypes=[C.POINTER(Target),C.POINTER(Weapons)]
        lib.bc_enemy_shots.restype=Hit
        w=Weapons();r=records[0][1]
        assert not any(r[0xa48:0xa64]), 'Start fixture before projectile launches'
        for i in range(30): w.shots[i].body=decode(r,i)
        w.charge=Charge(r[0x56],r[0x55],r[0x57],r[0xaa]==0x52);w.returning=r[0x5a]
        w.option_shots[:]=r[0x5b:0x5d];w.trail[:]=r[0xb4:0xc4]
        for i in (28,29):
            if not w.shots[i].body.state:continue
            s=w.shots[i];s.kind=4;s.tier=r[0xdea+i];s.launch_wait=r[0xc28+i]
            s.body.accelerating=1;s.body.facing=r[0xdae+i]==0x52
        option_launches=0
        updates=0;spawned=0;beams=0;contacts=0;blocked_beams=0;families=set()
        for (old_frame,old),(frame,r) in zip(records,records[1:]):
            assert frame==old_frame+1
            attrs=old[0x44]+old[0x45]*256-0xa000+0x6000
            terrain=Terrain(cells,C.cast(C.byref(data,attrs),C.POINTER(C.c_uint8)))
            active=[bool(s.body.state) for s in w.shots]
            for i in injected.get(frame,[]):lib.bc_shot_hit(C.byref(w.shots[i]))
            event=lib.bc_weapons_step(C.byref(w),r[0x228],r[0x22d],r[0x94]==0x80,r[0xad],r[0xa5],r[0xae],
                       r[0x95]*256+r[0x96],r[0x98]*256+r[0x99],r[0x2e]*256+r[0x2f],r[0x31]*256+r[0x32],C.byref(terrain))
            spawned+=event.shots;beams+=event.beams
            option_launches+=event.option_shots
            if old[0x56]>=40 and not r[0x56] and any(old[0xa5c:0xa61]):
                assert not event.beams
                blocked_beams+=1
            if event.recoil:assert r[0xa8]==event.recoil-1,(frame,'recoil',event.recoil,r[0xa8])
            for index,before,after,phase in scans.get(frame,[]):
                target=Target(before[0xe28+index]*256+before[0xe48+index],
                              before[0xe88+index]*256+before[0xea8+index],
                              before[0x1068+index],before[0x1088+index],before[0x1148+index],
                              before[0x1028+index],before[0x10c8+index],before[0x1108+index])
                hit=lib.bc_enemy_shots(C.byref(target),C.byref(w))
                assert target.hp==after[0x1028+index],(frame,index,'native enemy damage')
                assert bool(hit.depleted)==(phase==2),(frame,index,'native depletion')
                for j,s in enumerate(w.shots):
                    assert s.body.state==after[0xa48+j],(frame,index,j,'native contact',s.body.state,after[0xa48+j])
            for i in ([] if contact_file.exists() else hits.get(frame,[])):
                assert w.shots[i].body.state==0x80
                lib.bc_shot_hit(C.byref(w.shots[i]));contacts+=1
            lib.bc_weapons_record_position(C.byref(w),r[0x95]*256+r[0x96],r[0x98]*256+r[0x99])
            assert tuple(getattr(w.charge,n) for n,_ in Charge._fields_)==(r[0x56],r[0x55],r[0x57],int(r[0xaa]==0x52)),(frame,'charge')
            assert w.returning==r[0x5a],(frame,'return counter')
            assert bytes(w.option_shots)==r[0x5b:0x5d],(frame,'option counters',bytes(w.option_shots),r[0x5b:0x5d])
            assert bytes(w.trail)==r[0xb4:0xc4],(frame,'trail')
            for i,s in enumerate(w.shots):
                expected=decode(r,i)
                assert s.body.state==expected.state,(frame,i,'state',s.kind,s.body.state,expected.state)
                if active[i] or s.body.state:
                    updates+=1;families.add(s.kind)
                    expected.facing=(r[0xac] if s.kind==3 else r[0xdae+i])==0x52
                    expected.accelerating=(r[0xcdc+i]*256+r[0xcfa+i]) in custom
                    for field,_ in Beam._fields_:
                        actual,want=getattr(s.body,field),getattr(expected,field)
                        assert actual==want,(frame,i,s.kind,field,actual,want)
                    if s.kind==2:assert s.launch_wait==r[0xc28+i]
                    if s.kind==4:assert s.tier==r[0xdea+i]
        return dict(capture=capture.name,frames=len(records)-1,active_slot_updates=updates,
                    ordinary_launches=spawned,option_launches=option_launches,beam_segments=beams,families=sorted(families),
                    replayed_enemy_contacts=contacts,native_collision_scans=sum(len(v) for f,v in scans.items() if f>records[0][0]),
                    blocked_beam_releases=blocked_beams,whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);p.add_argument('--input',type=Path);a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code,a.input),indent=2))
