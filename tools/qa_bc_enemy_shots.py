#!/usr/bin/env python3
"""Compare native straight/homing enemy-shot preparation with original AI traces.
Unsupported families are counted explicitly and are not claimed as ported.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import ROOT
from qa_bc_enemies import Enemy, Data, decode
from qa_bc_rules import Terrain


class Bullet(C.Structure):
    _fields_=[('body',Enemy)]+[(n,C.c_uint8) for n in ('direction','speed','turn_timer','probe_x','probe_y')]


class BulletData(C.Structure):
    _fields_=[('data',Data)]+[(n,C.c_uint16) for n in
        ('speed_table','direction_animations','death_animation','death_sprite_base')]


def verify(capture,code):
    raw=(capture/'ai.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    program=code.read_bytes();rom=(C.c_uint8*len(program)).from_buffer_copy(program)
    cells=(C.c_uint8*16384).from_buffer_copy(program[0xc000:])
    signature=bytes.fromhex('bdcc2df0273a9dcc2dd02c');assert program.count(signature)==1
    shift=program.index(signature)+0x4000-0x9204
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'rules.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        str(ROOT/'src/bc_rules.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path))
        lib.bc_enemy_bullet_prepare.argtypes=[C.POINTER(Bullet),C.c_uint8]+[C.c_uint16]*4+[C.POINTER(Terrain),C.POINTER(BulletData)]
        lib.bc_enemy_bullet_prepare.restype=C.c_uint8
        lib.bc_enemy_bullet_death.argtypes=[C.POINTER(Bullet),C.c_uint8,C.POINTER(BulletData)]
        lib.bc_enemy_bullet_death.restype=C.c_uint8
        ordinary=0;homing=0;turns=0;terrain_hits=0;death=0;homing_death=0;unsupported={}
        for off in range(0,len(raw),stride*2):
            f,i,phase=struct.unpack_from('<IBB',raw,off);f2,i2,end=struct.unpack_from('<IBB',raw,off+stride)
            assert phase==0
            before=raw[off+6:off+stride];after=raw[off+stride+6:off+stride*2]
            def word(hi,lo):return before[hi+i]*256+before[lo+i]
            routine=word(0x1228,0x1248) if before[0xe08+i]==0x80 else word(0x1268,0x1288)
            canonical=routine-shift
            if canonical not in (0x8a61,0x8b17,0x8a72,0x8e95):
                unsupported[f'{routine:04x}']=unsupported.get(f'{routine:04x}',0)+1;continue
            assert (f,i)==(f2,i2),(f,i,f2,i2,hex(routine))
            b=Bullet(decode(before,i,program),*(before[a+i] for a in (0x11a8,0x11c8,0x1308,0xfe8,0x1008)))
            data=BulletData(Data(rom,0x4000),0x8479+shift,0x8b79+shift,0x8abc+shift,
                            int.from_bytes(before[0x167a:0x167c],'big'))
            if canonical in (0x8a72,0x8e95):
                is_homing=canonical==0x8e95
                if is_homing:
                    data.death_animation=0x8f15+shift
                    data.death_sprite_base=int.from_bytes(before[0x167c:0x167e],'big')
                sound=lib.bc_enemy_bullet_death(C.byref(b),is_homing,C.byref(data));death+=1
                homing_death+=is_homing
                assert sound==(4 if is_homing else 0)
                assert end==1 and after[0x1268+i]*256+after[0x1288+i]==0x9eb1
            else:
                attrs=before[0x44]+before[0x45]*256-0x4000
                terrain=Terrain(cells,C.cast(C.byref(rom,attrs),C.POINTER(C.c_uint8)))
                result=lib.bc_enemy_bullet_prepare(C.byref(b),canonical==0x8b17,
                    before[0x95]*256+before[0x96],before[0x98]*256+before[0x99],
                    before[0x2e]*256+before[0x2f],before[0x31]*256+before[0x32],C.byref(terrain),C.byref(data))
                assert end==(2 if result else 1),(f,i,'exit',result,end)
                terrain_hits+=result;ordinary+=canonical==0x8a61;homing+=canonical==0x8b17
                turns+=b.direction!=before[0x11a8+i]
            expected=decode(after,i,program)
            for field,_ in Enemy._fields_:
                assert getattr(b.body,field)==getattr(expected,field),(f,i,hex(routine),field,getattr(b.body,field),getattr(expected,field))
            for field,address in [('direction',0x11a8),('speed',0x11c8),('turn_timer',0x1308),('probe_x',0xfe8),('probe_y',0x1008)]:
                assert getattr(b,field)==after[address+i],(f,i,field,getattr(b,field),after[address+i])
        assert ordinary+homing+death>0
        return dict(module='straight and homing enemy-shot AI only',straight_updates=ordinary,
                    homing_updates=homing,direction_changes=turns,terrain_hits=terrain_hits,
                    death_initializations=death,homing_deaths=homing_death,
                    unsupported_routines=unsupported,whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code),indent=2))
