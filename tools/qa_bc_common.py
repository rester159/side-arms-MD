#!/usr/bin/env python3
"""Compare the complete native common enemy task with original entry/exit RAM.
Family AI and the surrounding stage scheduler remain source-provided inputs.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import Beam,decode,ROOT
from qa_bc_enemies import Enemy,Data
from qa_bc_factory import Actor,actor,BYTE_FIELDS,WORD_FIELDS
from qa_bc_pickups import Inventory
from qa_bc_weapons import Weapons


class Player(C.Structure):
    _fields_=[('x',C.c_uint32),('y',C.c_uint32),('weapons',Weapons),('inventory',Inventory),
              ('state',C.c_uint8),('invulnerability',C.c_uint8),('shot_index',C.c_void_p),('party',C.c_void_p)]


class Event(C.Structure):
    _fields_=[(n,C.c_uint8) for n in ('retired','score_pending','score_id','sound',
                                    'refresh_lives','pickup','option_absorbed','player_died')]


def verify(capture,code,party=False):
    raw=(capture/'common.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    program=code.read_bytes();rom=(C.c_uint8*len(program)).from_buffer_copy(program);data=Data(rom,0x4000)
    signature=bytes.fromhex('bdcc2df0273a9dcc2dd02c');assert program.count(signature)==1
    shift=program.index(signature)+0x4000-0x9204
    custom={a+shift for a in (0x9204,0x9399,0x923e,0x9413,0x953a,0x998a,0x9ca8,0x9d22)}
    def body(r,i):
        b=decode(r,i);b.accelerating=r[0xcdc+i]*256+r[0xcfa+i] in custom
        b.facing=r[0xdae+i]==0x52
        return b
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'world.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        str(ROOT/'src/bc_rules.c'),str(ROOT/'src/bc_world.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));lib.bc_actor_common.argtypes=[C.POINTER(Actor),C.POINTER(Player),C.POINTER(Data),C.POINTER(C.c_uint8)]
        lib.bc_actor_common.restype=Event
        if party:
            lib.bc_actor_party_common_into.argtypes=[C.POINTER(Event),C.POINTER(Actor),
                C.POINTER(C.POINTER(Player)),C.c_uint8,C.POINTER(Data),C.POINTER(C.c_uint8)]
        def step(actor,player,data,count):
            if not party:return lib.bc_actor_common(C.byref(actor),C.byref(player),C.byref(data),C.byref(count))
            events=(Event*4)();players=(C.POINTER(Player)*4)(C.pointer(player))
            lib.bc_actor_party_common_into(events,C.byref(actor),players,1,C.byref(data),C.byref(count))
            return events[0]
        updates=retired=scores=deaths=absorbed=bars=dying=permanent=0;pickups={}
        for off in range(0,len(raw),stride*2):
            f,i,phase=struct.unpack_from('<IBB',raw,off);f2,i2,end=struct.unpack_from('<IBB',raw,off+stride)
            assert phase==0 and end in (1,2) and i==i2 and f2>=f
            before=raw[off+6:off+stride];after=raw[off+stride+6:off+stride*2]
            assert not before[0x49],'Debug invincibility is outside native rules; use player blink protection instead'
            a=actor(before,i,program);expected=actor(after,i,program)
            p=Player();p.x=int.from_bytes(before[0x95:0x98],'big');p.y=int.from_bytes(before[0x98:0x9b],'big')
            p.state=before[0x94];p.invulnerability=before[0xaf]
            p.inventory=Inventory(*(before[address] for address in (0xa5,0xae,0x5d,0x4d,0x64)))
            w=p.weapons;w.returning=before[0x5a];w.option_shots[:]=before[0x5b:0x5d];w.trail[:]=before[0xb4:0xc4]
            w.charge.charge=before[0x56];w.charge.held=before[0x55]
            w.charge.latch=before[0x57];w.charge.facing=before[0xaa]==0x52
            for slot,s in enumerate(w.shots):
                s.body=body(before,slot);s.kind=4 if slot>=28 else 2 if before[0xd90+slot] else 0
                s.tier=before[0xdea+slot];s.launch_wait=before[0xc28+slot]
            count=C.c_uint8(before[0x59]);event=step(a,p,data,count)
            for field,_ in Enemy._fields_:
                assert getattr(a.body,field)==getattr(expected.body,field),(f,i,field,getattr(a.body,field),getattr(expected.body,field))
            for field in (*WORD_FIELDS,*BYTE_FIELDS):
                assert getattr(a,field)==getattr(expected,field),(f,i,field)
            assert count.value==after[0x59],(f,i,'limited counter')
            assert p.state==after[0x94] and p.invulnerability==after[0xaf],(f,i,'player')
            for field,address in [('weapon',0xa5),('power',0xae),('bonus_chain',0x5d),('lives',0x4d),('life_pickups',0x64)]:
                assert getattr(p.inventory,field)==after[address],(f,i,field)
            assert p.x==int.from_bytes(after[0x95:0x98],'big') and p.y==int.from_bytes(after[0x98:0x9b],'big')
            for slot,s in enumerate(w.shots):
                expected_shot=body(after,slot)
                for field,_ in Beam._fields_:
                    assert getattr(s.body,field)==getattr(expected_shot,field),(f,i,slot,'shot',field,getattr(s.body,field),getattr(expected_shot,field))
                if slot>=28:assert s.tier==after[0xdea+slot] and s.launch_wait==after[0xc28+slot]
            assert event.retired==(after[0xe08+i]==0),(f,i,'retirement')
            assert event.player_died==(before[0x94]==0x80 and after[0x94]==0x40)
            if before[0x51]:
                assert after[0x93]==(before[0x93]+event.score_pending)&15,(f,i,'score queue')
                if event.score_pending:assert after[0x82+before[0x93]]==event.score_id
            updates+=1;retired+=event.retired;scores+=event.score_pending;deaths+=event.player_died
            absorbed+=bool(event.option_absorbed);bars+=event.sound==4
            dying+=before[0xe08+i]==0x40;permanent+=before[0x10c8+i]==255
            if event.pickup:pickups[event.pickup]=pickups.get(event.pickup,0)+1
        assert updates
        return dict(module='complete common enemy task, source family-AI inputs',party_single_player=party,updates=updates,
                    retirements=retired,score_events=scores,player_deaths=deaths,option_absorptions=absorbed,
                    boss_bar_refills=bars,death_animation_updates=dying,permanent_protection_updates=permanent,
                    pickups=pickups,whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);p.add_argument('--party',action='store_true');a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code,a.party),indent=2))
