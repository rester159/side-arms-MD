#!/usr/bin/env python3
"""Compare native shot/target overlap and HP changes with original collision scans.
Input snapshots are taken at source routine entry and either normal exit or HP
exhaustion, before death, score, boss phase, or player-contact handlers execute.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import decode, ROOT
from qa_bc_weapons import Weapons, Target, Hit


def verify(capture):
    raw=(capture/'contacts.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0,'Incomplete collision entry/exit pairs'
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'rules.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
                        '-I'+str(ROOT/'inc'),str(ROOT/'src/bc_rules.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));lib.bc_enemy_shots.argtypes=[C.POINTER(Target),C.POINTER(Weapons)]
        lib.bc_enemy_shots.restype=Hit
        scans=0;contacts=0;damaging=0;depleted=0;consumed=0;protected_hits=0;piercing_hits=0
        for offset in range(0,len(raw),stride*2):
            frame,index,phase=struct.unpack_from('<IBB',raw,offset)
            f2,i2,p2=struct.unpack_from('<IBB',raw,offset+stride)
            assert (frame,index,phase)==(f2,i2,0) and p2 in (1,2)
            before=raw[offset+6:offset+stride];after=raw[offset+stride+6:offset+stride*2]
            def word(hi,lo):return before[hi+index]*256+before[lo+index]
            target=Target(word(0xe28,0xe48),word(0xe88,0xea8),before[0x1068+index],
                          before[0x1088+index],before[0x1148+index],before[0x1028+index],
                          before[0x10c8+index],before[0x1108+index])
            w=Weapons()
            for i in range(30):
                w.shots[i].body=decode(before,i)
                # The four implemented families differ here only in piercing.
                w.shots[i].kind=2 if before[0xd90+i] else 0
            event=lib.bc_enemy_shots(C.byref(target),C.byref(w))
            scans+=1;contacts+=event.contacts;damaging+=event.damaged;depleted+=event.depleted
            assert target.hp==after[0x1028+index],(frame,index,'HP',target.hp,after[0x1028+index])
            assert bool(event.depleted)==(p2==2),(frame,index,'depleted')
            assert bool(event.damaged)==(before[0x1028+index]!=after[0x1028+index]),(frame,index,'damage')
            if event.damaged:piercing_hits+=bool(before[0xd90+event.slot])
            if event.contacts and not event.damaged:protected_hits+=1
            for i,s in enumerate(w.shots):
                assert s.body.state==after[0xa48+i],(frame,index,i,'shot state',s.body.state,after[0xa48+i])
                consumed+=before[0xa48+i]==0x80 and s.body.state==0x40
                # Hit notification must not change motion until the next update.
                expected=decode(after,i)
                for field in ('x','y','vx','vy','sprite','attributes','timer','flags','damage','half_x','half_y','delay'):
                    assert getattr(s.body,field)==getattr(expected,field),(frame,index,i,field)
        assert scans and contacts and damaging, "Fixture did not exercise damaging overlaps"
        return dict(module='native enemy projectile scan, before death/score/phase handlers',
                    scans=scans,contacts=contacts,damaging_hits=damaging,depleted_hp=depleted,
                    consumed_shots=consumed,protected_contact_scans=protected_hits,piercing_damage_hits=piercing_hits,
                    whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    a=p.parse_args();print(json.dumps(verify(a.capture),indent=2))
