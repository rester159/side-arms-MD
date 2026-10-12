#!/usr/bin/env python3
"""Verify pickup effects against controlled calls through original contact code.

Score accumulation, its threshold awards, audio playback and HUD rendering are
separate tasks. Their command IDs are checked here, not their implementation.
"""
import argparse
import csv
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import Beam,decode,ROOT
from qa_bc_weapons import Weapons


class Inventory(C.Structure):
    _fields_=[(n,C.c_uint8) for n in ('weapon','power','bonus_chain','lives','life_pickups')]


class Event(C.Structure):
    _fields_=[(n,C.c_uint8) for n in ('consumed','score_id','sound','option_slot','refresh_lives')]


def verify(capture):
    raw=(capture/'player-contact.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    commands={}
    for row in csv.DictReader((capture/'pickup-commands.csv').open()):
        commands.setdefault(int(row['sequence']),[]).append((row['kind'],int(row['value'])))
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'rules.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        str(ROOT/'src/bc_rules.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path))
        lib.bc_pickup_apply.argtypes=[C.POINTER(Inventory),C.POINTER(Weapons),C.c_uint8,C.c_uint16,C.c_uint16]
        lib.bc_pickup_apply.restype=Event
        counts={};refills=[0,0];full=wraps=0
        def body(r,i):
            b=decode(r,i);b.facing=r[0xdae+i]==0x52
            b.accelerating=r[0xcdc+i]*256+r[0xcfa+i] in (0x9ca8,0x9d22)
            return b
        for off in range(0,len(raw),stride*2):
            seq=off//(stride*2)+1
            f,i,phase=struct.unpack_from('<IBB',raw,off);f2,i2,end=struct.unpack_from('<IBB',raw,off+stride)
            assert (f,i,phase,end)==(f2,i2,0,1)
            before=raw[off+6:off+stride];after=raw[off+stride+6:off+stride*2]
            item=before[0x1168+i];assert 1<=item<=9
            inv=Inventory(*(before[a] for a in (0xa5,0xae,0x5d,0x4d,0x64)))
            w=Weapons();w.charge.facing=before[0xaa]==0x52
            for slot in (28,29):
                w.shots[slot].body=body(before,slot);w.shots[slot].tier=before[0xdea+slot]
                w.shots[slot].launch_wait=before[0xc28+slot]
            event=lib.bc_pickup_apply(C.byref(inv),C.byref(w),item,
                before[0x95]*256+before[0x96],before[0x98]*256+before[0x99])
            assert event.consumed and after[0xe08+i]==0,(f,item,'consumption')
            for field,address in [('weapon',0xa5),('power',0xae),('bonus_chain',0x5d),('lives',0x4d),('life_pickups',0x64)]:
                if event.score_id and field=='lives':continue # original score task can award a threshold life
                assert getattr(inv,field)==after[address],(f,item,field,getattr(inv,field),after[address])
            assert [value for kind,value in commands.get(seq,[]) if kind=='score']==([event.score_id] if event.score_id else []),(f,item,'score command',commands.get(seq))
            sounds=[value for kind,value in commands.get(seq,[]) if kind=='sound']
            assert sounds and sounds[-1]==event.sound,(f,item,'sound',sounds,event.sound)
            assert event.refresh_lives==(item==9)
            for slot in (28,29):
                expected=body(after,slot);s=w.shots[slot]
                for field,_ in Beam._fields_:
                    assert getattr(s.body,field)==getattr(expected,field),(f,item,slot,field,getattr(s.body,field),getattr(expected,field))
                assert s.tier==after[0xdea+slot] and s.launch_wait==after[0xc28+slot]
            counts[item]=counts.get(item,0)+1
            if item==5:
                if event.option_slot:refills[event.option_slot-29]+=1
                else:full+=1
            if 2<=item<=4 and before[0xae]==255:wraps+=1
            if item==9 and before[0x4d]==255:wraps+=1
        assert set(counts)==set(range(1,10)) and all(refills) and full and wraps
        return dict(module='pickup direct effects and option replenishment',cases=sum(counts.values()),
                    item_cases=counts,option_refills=refills,full_option_noops=full,
                    wrapping_increment_cases=wraps,whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture),indent=2))
