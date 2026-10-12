#!/usr/bin/env python3
"""Compare common enemy animation/motion and HP-exhaustion transitions with PCE.
Family-specific AI, scoring application and rendering remain outside the check.
"""
import argparse
import re
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import ROOT


# Fixtures describe source 16.8 values. Only enemy storage changes; player,
# beam and other coordinate structures retain their original representations.
_layout=re.search(r'^#define BC_ENEMY_STORAGE_SHIFT (0|8)$',
                  (ROOT/'inc/bc_rules.h').read_text(),re.M)
enemy_storage_shift=int(_layout[1]) if _layout else 0
_velocity_layout=re.search(r'^#define BC_ENEMY_VELOCITY_SHIFT (0|8)$',
                           (ROOT/'inc/bc_rules.h').read_text(),re.M)
enemy_velocity_shift=int(_velocity_layout[1]) if _velocity_layout else 0
_velocity_type=C.c_int32 if enemy_velocity_shift else C.c_int16

class Enemy(C.Structure):
    _fields_=[('x',C.c_uint32),('y',C.c_uint32),('vx',_velocity_type),('vy',_velocity_type)]+[
        (n,C.c_uint16) for n in ('sprite','attributes','animation','sprite_base')]+[
        (n,C.c_uint8) for n in ('state','timer','flags','move_delay','hp','bars','cooldown','damage_lock','score_id')]


    def __getattribute__(self,name):
        value=super().__getattribute__(name)
        if name in ('x','y') and enemy_storage_shift:
            assert value & ((1<<enemy_storage_shift)-1)==0, ('enemy padding',name,value)
            return value >> enemy_storage_shift
        if name in ('vx','vy') and enemy_velocity_shift:
            assert value%256==0 and -8388608<=value<=8388352, ('enemy velocity',name,value)
            return value//256
        return value

    def __setattr__(self,name,value):
        if name in ('x','y'):value <<= enemy_storage_shift
        if name in ('vx','vy') and enemy_velocity_shift:
            value=C.c_int16(value).value << enemy_velocity_shift
        super().__setattr__(name,value)


class Data(C.Structure):
    _fields_=[('bytes',C.POINTER(C.c_uint8)),('origin',C.c_uint16)]


class DeathEvent(C.Structure):
    _fields_=[(n,C.c_uint8) for n in ('award_score','score_id','sound')]


def decode(r,i,program):
    def word(hi,lo):return r[hi+i]*256+r[lo+i]
    def signed(v):return v if v<32768 else v-65536
    base=word(0x11e8,0x1208)-0x4000
    sprite_base=(int.from_bytes(r[base+0x2000:base+0x2002],'big') if -0x2000<=base<-1 else
                 int.from_bytes(program[base:base+2],'big') if 0<=base<len(program)-1 else 0)
    return Enemy(word(0xe28,0xe48)*256+r[0xe68+i],word(0xe88,0xea8)*256+r[0xec8+i],
                 signed(word(0xf68,0xf88)),signed(word(0xfa8,0xfc8)),word(0xf28,0xf48),
                 word(0xee8,0xf08),word(0x12a8,0x12c8),sprite_base,
                 *(r[a+i] for a in (0xe08,0x1128,0x1148,0x10a8,0x1028,0x10e8,0x10c8,0x1108,0x1188)))


def verify(capture,code):
    raw=(capture/'enemy.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    program=code.read_bytes();rom=(C.c_uint8*len(program)).from_buffer_copy(program);data=Data(rom,0x4000)
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'rules.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        str(ROOT/'src/bc_rules.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));lib.bc_enemy_motion.argtypes=[C.POINTER(Enemy),C.POINTER(Data),C.POINTER(C.c_uint8)]
        lib.bc_enemy_motion.restype=C.c_uint8
        lib.bc_enemy_depleted.argtypes=[C.POINTER(Enemy)];lib.bc_enemy_depleted.restype=DeathEvent
        motion=0;retired=0;dying=0;depleted=0;bars=0;awards=0;composites=0;delayed=0
        for off in range(0,len(raw),stride*2):
            f,i,phase=struct.unpack_from('<IBB',raw,off);f2,i2,end=struct.unpack_from('<IBB',raw,off+stride)
            assert (f,i)==(f2,i2)
            before=raw[off+6:off+stride];after=raw[off+stride+6:off+stride*2]
            enemy=decode(before,i,program);expected=decode(after,i,program)
            count=C.c_uint8(before[0x59])
            if phase==0:
                result=lib.bc_enemy_motion(C.byref(enemy),C.byref(data),C.byref(count))
                assert result=={1:0,2:1,3:2}[end],(f,i,'exit',result,end)
                assert count.value==after[0x59],(f,i,'limited counter')
                motion+=1;retired+=result==1;dying+=result==2
                composites+=bool(enemy.flags&8);delayed+=bool(before[0x10a8+i])
            else:
                assert phase==4 and end==5,(f,i,phase,end)
                result=lib.bc_enemy_depleted(C.byref(enemy));depleted+=1
                bars+=result.sound==4;awards+=result.award_score
            for field,_ in Enemy._fields_:
                assert getattr(enemy,field)==getattr(expected,field),(f,i,phase,field,getattr(enemy,field),getattr(expected,field))
        assert motion
        return dict(module='common enemy animation/motion and HP exhaustion only',motion_updates=motion,
                    retirements=retired,death_animation_updates=dying,composite_updates=composites,
                    delayed_updates=delayed,hp_exhaustions=depleted,boss_bar_refills=bars,score_events=awards,
                    whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code),indent=2))
