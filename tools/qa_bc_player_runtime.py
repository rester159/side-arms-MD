#!/usr/bin/env python3
"""Carry native player/weapons state through player, enemy-common and trail tasks.
Stage/checkpoint initialization and enemy-family AI remain source inputs.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import Beam,decode,ROOT
from qa_bc_common import Event as ActorEvent,Player
from qa_bc_enemies import Data,Enemy
from qa_bc_factory import Actor,actor,BYTE_FIELDS,WORD_FIELDS
from qa_bc_player_flow import Control,Event as ControlEvent,state
from qa_bc_rules import Terrain,Charge
from qa_bc_weapons import Event as WeaponEvent,Weapons


class Event(C.Structure):
    _fields_=[('control',ControlEvent),('weapon',WeaponEvent),('graphics',C.c_uint8)]


def verify(capture,code):
    raw=(capture/'player-runtime.bin').read_bytes();stride=8198
    assert raw and len(raw)%stride==0
    program=code.read_bytes();rom=(C.c_uint8*len(program)).from_buffer_copy(program);data=Data(rom,0x4000)
    cells=(C.c_uint8*16384).from_buffer_copy(program[0xc000:])
    signature=bytes.fromhex('bdcc2df0273a9dcc2dd02c');assert program.count(signature)==1
    shift=program.index(signature)+0x4000-0x9204
    custom={a+shift for a in (0x9204,0x9399,0x923e,0x9413,0x953a,0x998a,0x9ca8,0x9d22)}
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'player.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        *(str(ROOT/f'src/{name}.c') for name in ('bc_rules','bc_world','bc_player')),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));lib.bc_player_step.argtypes=[C.POINTER(Control),C.c_uint8,C.c_uint8]+[C.c_uint16]*4+[
            C.POINTER(Terrain),C.POINTER(Data),C.c_uint16];lib.bc_player_step.restype=Event
        lib.bc_player_step_into.argtypes=[C.POINTER(Event)]+lib.bc_player_step.argtypes
        lib.bc_actor_common.argtypes=[C.POINTER(Actor),C.POINTER(Player),C.POINTER(Data),C.POINTER(C.c_uint8)]
        lib.bc_actor_common.restype=ActorEvent
        lib.bc_weapons_record_position.argtypes=[C.POINTER(Weapons),C.c_uint16,C.c_uint16]
        p=None;pending=None;enemy=None;player_updates=enemy_updates=trails=checkpoints=segments=launches=deaths=0
        def compare(r,f,task):
            expected=state(r)
            for field,_ in Control._fields_[1:]:
                assert getattr(p,field)==getattr(expected,field),(f,task,field,getattr(p,field),getattr(expected,field))
            for field in ('x','y','state','invulnerability'):
                assert getattr(p.world,field)==getattr(expected.world,field),(f,task,field,getattr(p.world,field),getattr(expected.world,field))
            assert bytes(p.world.inventory)==bytes(expected.world.inventory),(f,task,'inventory')
            w=p.world.weapons
            assert bytes(w.charge)==bytes(expected.world.weapons.charge),(f,task,'charge',bytes(w.charge),bytes(expected.world.weapons.charge))
            assert w.returning==r[0x5a] and bytes(w.option_shots)==r[0x5b:0x5d],(f,task,'weapon counters')
            assert bytes(w.trail)==r[0xb4:0xc4],(f,task,'trail')
            for i,s in enumerate(w.shots):
                want=decode(r,i);want.facing=(r[0xac] if s.kind==3 else r[0xdae+i])==0x52
                want.accelerating=r[0xcdc+i]*256+r[0xcfa+i] in custom
                fields=[name for name,_ in Beam._fields_] if s.body.state else ('state','x','y','delay')
                for field in fields:
                    assert getattr(s.body,field)==getattr(want,field),(f,task,i,field,getattr(s.body,field),getattr(want,field))
                if s.body.state and s.kind in (2,4):assert s.launch_wait==r[0xc28+i]
                if s.body.state and s.kind==4:assert s.tier==r[0xdea+i]
        for off in range(0,len(raw),stride):
            f,task,i=struct.unpack_from('<IBB',raw,off);r=raw[off+6:off+stride]
            if p is None:
                if task!=0:continue
                assert not any(r[0xa48:0xa66]),'Initialize only at an empty-pool stage/checkpoint entry'
                p=state(r);segments+=1
            if task==0:
                assert pending is None and enemy is None
                compare(r,f,'player entry')
                attrs=r[0x44]+r[0x45]*256-0x4000
                terrain=Terrain(cells,C.cast(C.byref(rom,attrs),C.POINTER(C.c_uint8)))
                before=Control.from_buffer_copy(bytes(p))
                args=(r[0x228],r[0x22d],int.from_bytes(r[0x2e:0x30],'big'),
                    int.from_bytes(r[0x31:0x33],'big'),int.from_bytes(r[0x40:0x42],'big'),int.from_bytes(r[0x42:0x44],'big'),
                    C.byref(terrain),C.byref(data),0x9c07+shift)
                pending=Event();C.memset(C.byref(pending),0xa5,C.sizeof(pending))
                lib.bc_player_step_into(C.byref(pending),C.byref(p),*args)
                legacy=lib.bc_player_step(C.byref(before),*args)
                assert bytes(pending)==bytes(legacy) and bytes(p)==bytes(before),(f,'output API')
            elif task in (1,2):
                assert pending is not None and enemy is None
                compare(r,f,'player exit');assert bool(pending.control.checkpoint)==(task==2)
                if task==2:
                    assert bytes(pending.weapon)==bytes(C.sizeof(WeaponEvent)) and pending.graphics==0,(f,'checkpoint outputs')
                player_updates+=1;launches+=pending.weapon.shots;pending=None
                if task==2:p=None;checkpoints+=1
            elif task==3:
                assert pending is None and enemy is None
                compare(r,f,'enemy entry')
                a=actor(r,i,program);count=C.c_uint8(r[0x59])
                event=lib.bc_actor_common(C.byref(a),C.byref(p.world),C.byref(data),C.byref(count))
                enemy=(i,a,count,event)
            elif task in (4,5):
                assert pending is None and enemy is not None and enemy[0]==i
                _,a,count,event=enemy;expected=actor(r,i,program)
                compare(r,f,'enemy exit')
                for field,_ in Enemy._fields_:
                    assert getattr(a.body,field)==getattr(expected.body,field),(f,i,'actor',field)
                for field in (*WORD_FIELDS,*BYTE_FIELDS):assert getattr(a,field)==getattr(expected,field),(f,i,field)
                assert count.value==r[0x59],(f,i,'limited count')
                enemy_updates+=1;deaths+=event.player_died;enemy=None
            else:
                assert task==6 and pending is None and enemy is None
                compare(r,f,'trail')
                lib.bc_weapons_record_position(C.byref(p.world.weapons),p.world.x>>8,p.world.y>>8);trails+=1
        assert pending is None and enemy is None,'Capture ends inside a task'
        return dict(module='continuous native player/weapons and common enemy interactions',player_updates=player_updates,
                    common_enemy_updates=enemy_updates,trail_updates=trails,main_shots=launches,
                    player_deaths=deaths,checkpoint_requests=checkpoints,source_initialized_life_segments=segments,
                    replayed_hit_notifications=0,whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code),indent=2))
