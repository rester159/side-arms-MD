#!/usr/bin/env python3
"""Exercise native death/restart/game-over flow; not a complete transition test."""
import argparse
import json
from run_rom import ROOT,Runner
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--late',action='store_true');a=p.parse_args()
r=Runner();r.run(2600)
r.write('dbg_bc_native_protect',b'\0\1');r.write('dbg_bc_native',b'\0\1')
def step():
    if r.u16('dbg_bc_native_status')==4:r.write('dbg_bc_native_audio_ack',b'\0\1')
    r.run(1)
    assert r.u16('dbg_bc_native_status') in (0,4,7)
for _ in range(180):step()
if a.late:
    for _ in range(9000):
        if r.u32('dbg_bc_native_ticks')>=5500:break
        step()
    assert r.u32('dbg_bc_native_ticks')>=5500
assert r.u16('dbg_bc_native_lives')==3
results=[]
for death in range(4):
    initial=r.u32('dbg_bc_native_ticks')
    r.write('dbg_bc_native_die',b'\0\1')
    for elapsed in range(700):
        step()
        if r.u16('dbg_bc_native_resets')==death+1 or r.u16('dbg_bc_native_status')==7:break
    else:raise AssertionError('death did not complete')
    expected=2-death if death<3 else 255
    assert r.u16('dbg_bc_native_lives')==expected
    assert r.u32('dbg_bc_native_ticks')>initial
    if death<3:
        assert r.u16('dbg_bc_native_resets')==death+1
        assert r.u16('dbg_bc_native_actors')==0
        assert r.u16('dbg_bc_native_camera')==(2304 if a.late else 512)
        for _ in range(100):step()
        assert r.u16('dbg_bc_native_status') in (0,4)
    else:
        assert r.u16('dbg_bc_native_status')==7
        tick=r.u32('dbg_bc_native_ticks')
        for _ in range(100):step()
        assert r.u32('dbg_bc_native_ticks')==tick
    results.append(dict(death=death+1,remaining=expected,resets=r.u16('dbg_bc_native_resets'),frames=elapsed+1))
r.write('dbg_bc_native',b'\0\0');r.run(120);assert r.u32('flow_state')==0
result=dict(late_checkpoint=a.late,deaths=results,returned_to_menu=True,transition_presentation_verified=False)
path=ROOT/('.local/pce-reference/native-checkpoints-late.json' if a.late else '.local/pce-reference/native-checkpoints.json');path.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
