#!/usr/bin/env python3
"""Compare score timing/state to original HuCard execution, at every sound tick.
Instrument envelopes and modulation are intentionally outside this score check.
"""
import argparse,struct
from pathlib import Path
from inspect_hucard_music import ROOT
from hucard_score_model import Score
p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);a=p.parse_args()
raw=(a.capture/'sound-state.bin').read_bytes();assert len(raw)%177==0
rows=[raw[i:i+177] for i in range(0,len(raw),177)]
start=next(i for i,r in enumerate(rows) if struct.unpack_from('<I',r,4)[0]>=65)
r=rows[start];g=r[16:39]
model=Score((ROOT/'.local/pce-hucard/SideArms - Hyper Dyne (USA).pce').read_bytes(),[list(r[39+c*23:39+(c+1)*23])for c in range(6)],g[0xa8-0x99]*256+g[0xa9-0x99],g[0xac-0x99],g[0xaa-0x99]*256+g[0xab-0x99],g[0xad-0x99])
for i,r in enumerate(rows[start+1:],start+1):
    model.tick();g=r[16:39]
    assert (model.phase,model.clock,model.tempo,model.transpose)==(g[15]*256+g[16],g[19],g[17]*256+g[18],g[20]),('global',i)
    for channel,c in enumerate(model.channels):
        source=r[39+channel*23:39+(channel+1)*23]
        # Flags include an instrument-change acknowledgement in the envelope
        # path; compare score-owned bits, not the envelope's private latch.
        for field in range(17):
            mask=0xef if field==5 else 255
            assert c[field]&mask==source[field]&mask,('score mismatch',i,channel,field,c[field],source[field],hex(c[0]+256*c[1]))
print(f'PASS: {len(rows)-start-1} original driver ticks, {len(model.events)} decoded note/rest events, six channels')
