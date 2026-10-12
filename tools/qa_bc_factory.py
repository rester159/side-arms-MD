#!/usr/bin/env python3
"""Compare native enemy allocation/template application with original execution.
Family birth logic, immediate first update and world scheduling are separate.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import ROOT
from qa_bc_enemies import Enemy,Data,decode


class Actor(C.Structure):
    _fields_=[('body',Enemy)]+[(n,C.c_uint16) for n in ('routine','death_routine','sprite_base_ref')]+[
        (n,C.c_uint8) for n in ('half_x','half_y','pickup','speed','auxiliary',
                              'direction','wait','phase','turn','fired','probe_x','probe_y','dash_started','health_fraction')]


BYTE_FIELDS=dict(half_x=0x1068,half_y=0x1088,pickup=0x1168,speed=0x11c8,auxiliary=0x15e8,
                 direction=0x11a8,wait=0x1308,phase=0x1328,turn=0x1348,fired=0x1368,
                 probe_x=0xfe8,probe_y=0x1008,dash_started=0x1388)
WORD_FIELDS=dict(routine=(0x1228,0x1248),death_routine=(0x1268,0x1288),sprite_base_ref=(0x11e8,0x1208))


def actor(r,i,program):
    a=Actor();a.body=decode(r,i,program)
    for name,(hi,lo) in WORD_FIELDS.items():setattr(a,name,r[hi+i]*256+r[lo+i])
    for name,address in BYTE_FIELDS.items():setattr(a,name,r[address+i])
    return a


def verify(capture,code):
    raw=(capture/'factory.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    program=code.read_bytes()
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'world.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        str(ROOT/'src/bc_rules.c'),str(ROOT/'src/bc_world.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));lib.bc_actor_allocate.argtypes=[C.POINTER(Actor),C.c_uint8]
        lib.bc_actor_allocate.restype=C.c_int16
        lib.bc_actor_template.argtypes=[C.POINTER(Actor),C.POINTER(C.c_uint8),C.c_uint16]
        allocations=[0,0];failures=templates=composites=reused_fraction=retained_lock=0;records=set()
        for off in range(0,len(raw),stride*2):
            f,i,phase=struct.unpack_from('<IBB',raw,off);f2,i2,end=struct.unpack_from('<IBB',raw,off+stride)
            assert f2>=f
            before=raw[off+6:off+stride];after=raw[off+stride+6:off+stride*2]
            if phase<2:
                assert end==2
                pool=(Actor*32)()
                for j in range(32):pool[j].body.state=before[0xe08+j]
                result=lib.bc_actor_allocate(pool,phase)
                assert result==(-1 if i2>=32 else i2),(f,phase,'allocation',result,i2)
                assert bytes(a.body.state for a in pool)==after[0xe08:0xe28]
                allocations[phase]+=1;failures+=result<0
            else:
                assert phase==3 and end==4 and i==i2
                pointer=before[0x18]+before[0x19]*256
                assert 0x4000<=pointer<=0x10000-19
                record=program[pointer-0x4000:pointer-0x4000+19]
                records.add(pointer)
                ref=int.from_bytes(record[11:13],'little')
                base=(int.from_bytes(before[ref-0x2000:ref-0x2000+2],'big') if 0x2000<=ref<0x3fff else
                      int.from_bytes(program[ref-0x4000:ref-0x4000+2],'big'))
                a=actor(before,i,program);expected=actor(after,i,program)
                lib.bc_actor_template(C.byref(a),(C.c_uint8*19).from_buffer_copy(record),base)
                for field,_ in Enemy._fields_:
                    assert getattr(a.body,field)==getattr(expected.body,field),(f,i,hex(pointer),field,getattr(a.body,field),getattr(expected.body,field))
                for field in (*WORD_FIELDS,*BYTE_FIELDS):
                    assert getattr(a,field)==getattr(expected,field),(f,i,hex(pointer),field,getattr(a,field),getattr(expected,field))
                templates+=1;composites+=bool(record[2]&8)
                reused_fraction+=bool((a.body.x|a.body.y)&255);retained_lock+=bool(a.body.damage_lock)
        assert templates and sum(allocations)
        births=0;birth_failures=0;birth_directions=set();fractional_births=0
        birth_path=capture/'bullet-birth.bin'
        if birth_path.exists() and birth_path.stat().st_size:
            birth_raw=birth_path.read_bytes();assert len(birth_raw)%(stride*2)==0
            signature=bytes.fromhex('bdcc2df0273a9dcc2dd02c');assert program.count(signature)==1
            shift=program.index(signature)+0x4000-0x9204
            rom=(C.c_uint8*len(program)).from_buffer_copy(program);data=Data(rom,0x4000)
            lib.bc_actor_spawn_bullet.argtypes=[C.POINTER(Actor),C.c_uint8,C.c_uint8,C.POINTER(Data)]+[C.c_uint16]*3
            lib.bc_actor_spawn_bullet.restype=C.c_int16
            for off in range(0,len(birth_raw),stride*2):
                f,parent,phase=struct.unpack_from('<IBB',birth_raw,off)
                f2,slot,end=struct.unpack_from('<IBB',birth_raw,off+stride)
                assert parent<32 and phase==0 and end in (1,2) and f2>=f
                before=birth_raw[off+6:off+stride];after=birth_raw[off+stride+6:off+stride*2]
                pool=(Actor*32)(*(actor(before,j,program) for j in range(32)))
                result=lib.bc_actor_spawn_bullet(pool,parent,before[0x27],C.byref(data),0x8aa4+shift,
                    int.from_bytes(before[0x1698:0x169a],'big'),0x8479+shift)
                assert result==(-1 if end==2 else slot),(f,'bullet allocation',result,slot,end)
                for j,a in enumerate(pool):
                    expected=actor(after,j,program)
                    for field,_ in Enemy._fields_:
                        assert getattr(a.body,field)==getattr(expected.body,field),(f,j,'birth',field,getattr(a.body,field),getattr(expected.body,field))
                    for field in (*WORD_FIELDS,*BYTE_FIELDS):
                        assert getattr(a,field)==getattr(expected,field),(f,j,'birth',field)
                births+=result>=0;birth_failures+=result<0
                if result>=0:
                    birth_directions.add(pool[result].direction)
                    fractional_births+=bool((pool[result].body.x|pool[result].body.y)&255)
        return dict(module='enemy allocation, templates and straight-shot birth',forward_allocations=allocations[0],
                    reverse_allocations=allocations[1],allocation_failures=failures,templates=templates,
                    composite_templates=composites,templates_with_fractional_positions=reused_fraction,
                    templates_retaining_damage_lock=retained_lock,template_addresses=[hex(p) for p in sorted(records)],
                    bullet_births=births,bullet_allocation_failures=birth_failures,
                    fractional_bullet_births=fractional_births,bullet_directions=sorted(birth_directions),
                    whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code),indent=2))
