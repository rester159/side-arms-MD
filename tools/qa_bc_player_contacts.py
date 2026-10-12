#!/usr/bin/env python3
"""Compare native enemy/player contact with original routine entry/exit snapshots.

Pickup application and debug invincibility are explicitly excluded. This is an
isolated routine comparison, not a complete player death/respawn simulation.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import ROOT
from qa_bc_enemies import Enemy, decode


class Player(C.Structure):
    _fields_=[('x',C.c_uint16),('y',C.c_uint16),('state',C.c_uint8),
              ('invulnerability',C.c_uint8),('options',C.c_uint8*2)]


class Event(C.Structure):
    _fields_=[(n,C.c_uint8) for n in ('contact','pickup','option','sound')]


def verify(capture,code):
    raw=(capture/'player-contact.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    program=code.read_bytes()
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'rules.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        str(ROOT/'src/bc_rules.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path))
        lib.bc_enemy_player.argtypes=[C.POINTER(Enemy),C.c_uint8,C.c_uint8,C.c_uint8,C.POINTER(Player)]
        lib.bc_enemy_player.restype=Event
        scans=contacts=deaths=enemy_deaths=skipped=0;options=[0,0]
        for off in range(0,len(raw),stride*2):
            f,i,phase=struct.unpack_from('<IBB',raw,off)
            f2,i2,end=struct.unpack_from('<IBB',raw,off+stride)
            assert (f,i,phase,end)==(f2,i2,0,1)
            before=raw[off+6:off+stride];after=raw[off+stride+6:off+stride*2]
            if before[0x49] or before[0x1168+i]:
                skipped+=1;continue
            e=decode(before,i,program);expected=decode(after,i,program)
            p=Player(before[0x95]*256+before[0x96],before[0x98]*256+before[0x99],
                     before[0x94],before[0xaf],(C.c_uint8*2)(*before[0xa64:0xa66]))
            event=lib.bc_enemy_player(C.byref(e),before[0x1068+i],before[0x1088+i],0,C.byref(p))
            scans+=1;contacts+=event.contact
            deaths+=before[0x94]==0x80 and p.state==0x40
            enemy_deaths+=before[0xe08+i]==0x80 and e.state==0x40
            if event.option:
                options[event.option-1]+=1
                slot=event.option-1
                # Original routine switches the consumed option to its saved
                # impact handler; the native caller receives this slot event.
                assert after[0xd16+slot]==before[0xd52+slot]
                assert after[0xcf8+slot]==before[0xd34+slot]
            for field,_ in Enemy._fields_:
                assert getattr(e,field)==getattr(expected,field),(f,i,field,getattr(e,field),getattr(expected,field))
            assert p.state==after[0x94],(f,i,'player state',p.state,after[0x94])
            assert p.invulnerability==after[0xaf],(f,i,'invulnerability',p.invulnerability,after[0xaf])
            assert bytes(p.options)==after[0xa64:0xa66],(f,i,'options')
        assert scans
        return dict(module='enemy/player contact only',scans=scans,contacts=contacts,
                    player_deaths=deaths,enemy_deaths=enemy_deaths,option_absorptions=options,
                    skipped_pickup_or_debug_scans=skipped,whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code),indent=2))
