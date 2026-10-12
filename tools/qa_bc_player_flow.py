#!/usr/bin/env python3
"""Compare native player control/death/entry and pose tasks with original RAM.
Checkpoint reconstruction and graphics rendering are outside this comparison.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import Beam,decode,ROOT
from qa_bc_common import Player
from qa_bc_enemies import Data
from qa_bc_pickups import Inventory
from qa_bc_rules import Terrain


class Control(C.Structure):
    _fields_=[('world',Player)]+[(n,C.c_uint16) for n in ('attributes','body_frame','weapon_frame','death_script')]+[
        ('vx',C.c_int16),('vy',C.c_int16)]+[(n,C.c_uint8) for n in ('entry','speed','recoil','death_clock')]


class Event(C.Structure):
    _fields_=[('checkpoint',C.c_uint8),('sound',C.c_uint8)]


def state(r):
    p=Control();w=p.world
    w.x=int.from_bytes(r[0x95:0x98],'big');w.y=int.from_bytes(r[0x98:0x9b],'big')
    w.state=r[0x94];w.invulnerability=r[0xaf]
    w.inventory=Inventory(*(r[a] for a in (0xa5,0xae,0x5d,0x4d,0x64)))
    for i in range(30):w.weapons.shots[i].body=decode(r,i)
    charge=w.weapons.charge;charge.charge=r[0x56];charge.held=r[0x55]
    charge.latch=r[0x57];charge.facing=r[0xaa]==0x52
    w.weapons.returning=r[0x5a];w.weapons.option_shots[:]=r[0x5b:0x5d];w.weapons.trail[:]=r[0xb4:0xc4]
    for name,address in [('attributes',0x9b),('body_frame',0x9d),('weapon_frame',0xa6)]:setattr(p,name,int.from_bytes(r[address:address+2],'big'))
    p.death_script=int.from_bytes(r[0xb2:0xb4],'little')
    p.vx=int.from_bytes(r[0x9f:0xa1],'big',signed=True);p.vy=int.from_bytes(r[0xa1:0xa3],'big',signed=True)
    p.entry=r[0xad];p.speed=r[0xa9];p.recoil=r[0xa8];p.death_clock=r[0xb1]
    return p


def verify(capture,code):
    raw=(capture/'player-flow.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    program=code.read_bytes();rom=(C.c_uint8*len(program)).from_buffer_copy(program);data=Data(rom,0x4000)
    cells=(C.c_uint8*16384).from_buffer_copy(program[0xc000:])
    signature=bytes.fromhex('bdcc2df0273a9dcc2dd02c');assert program.count(signature)==1
    shift=program.index(signature)+0x4000-0x9204
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'player.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        str(ROOT/'src/bc_rules.c'),str(ROOT/'src/bc_world.c'),str(ROOT/'src/bc_player.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));lib.bc_player_control.argtypes=[C.POINTER(Control),C.c_uint8]+[C.c_uint16]*4+[
            C.POINTER(Terrain),C.POINTER(Data),C.c_uint16];lib.bc_player_control.restype=Event
        lib.bc_player_finish.argtypes=[C.POINTER(Control),C.POINTER(Data),C.c_uint16];lib.bc_player_finish.restype=C.c_uint8
        controls=finishes=entries=dying=dead=checkpoints=clears=crushes=0;frames=set()
        for off in range(0,len(raw),stride*2):
            f,_,phase=struct.unpack_from('<IBB',raw,off);f2,_,end=struct.unpack_from('<IBB',raw,off+stride)
            assert f2>=f and ((phase==0 and end in (1,2)) or (phase==3 and end==4))
            before=raw[off+6:off+stride];after=raw[off+stride+6:off+stride*2]
            p=state(before);expected=state(after)
            if phase==0:
                attrs=before[0x44]+before[0x45]*256-0x4000
                terrain=Terrain(cells,C.cast(C.byref(rom,attrs),C.POINTER(C.c_uint8)))
                event=lib.bc_player_control(C.byref(p),before[0x228]>>4,
                    int.from_bytes(before[0x2e:0x30],'big'),int.from_bytes(before[0x31:0x33],'big'),
                    int.from_bytes(before[0x40:0x42],'big'),int.from_bytes(before[0x42:0x44],'big'),
                    C.byref(terrain),C.byref(data),0x9c07+shift)
                assert bool(event.checkpoint)==(end==2),(f,'checkpoint')
                assert event.sound==(3 if before[0x94]==0x80 and after[0x94]==0x40 else 0),(f,'crush sound')
                controls+=1;checkpoints+=event.checkpoint;crushes+=event.sound==3
                entries+=bool(before[0xad]);dying+=not before[0xad] and before[0x94] not in (0,128)
                dead+=not before[0xad] and before[0x94]==0
                clears+=not before[0xad] and before[0x94] not in (0,128) and before[0xb1]==0
            else:
                lib.bc_player_finish(C.byref(p),C.byref(data),0x9c07+shift);finishes+=1
            for field,_ in Control._fields_[1:]:
                assert getattr(p,field)==getattr(expected,field),(f,phase,field,getattr(p,field),getattr(expected,field))
            for field in ('x','y','state','invulnerability'):
                assert getattr(p.world,field)==getattr(expected.world,field),(f,phase,field,getattr(p.world,field),getattr(expected.world,field))
            assert bytes(p.world.inventory)==bytes(expected.world.inventory),(f,phase,'inventory')
            assert bytes(p.world.weapons)==bytes(expected.world.weapons),(f,phase,'weapons')
            frames.add(p.body_frame)
        assert controls and finishes
        return dict(module='player control and pose/countdowns',control_updates=controls,pose_updates=finishes,
                    entry_updates=entries,dying_updates=dying,dead_wait_updates=dead,checkpoint_requests=checkpoints,
                    first_death_clears=clears,terrain_crushes=crushes,frame_ids=[hex(v) for v in sorted(frames)],
                    whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code),indent=2))
