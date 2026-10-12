#!/usr/bin/env python3
"""Simultaneous native continue requests with one shared credit or unlimited."""
import argparse
from run_rom import Runner
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--players',type=int,choices=(2,3,4),required=True)
a=p.parse_args()
for policy in (1,2):
    r=Runner();r.run(2600)
    r.write('home_session',b'\1')
    r.write('game_cfg',bytes([1,3,1,4,1,policy,1,1]))
    r.write('home_cfg',bytes([2 if policy==1 else 1]),4)
    for name,value in [('dbg_bc_native_players',a.players),('dbg_bc_native_start_round',0),
                       ('dbg_bc_native_protect',1),('dbg_bc_native',1)]:
        r.write(name,value.to_bytes(2,'big'))
    r.write('dbg_pad_override',b'\1');r.write('pad',bytes(8));r.run(200)
    def wait(check):
        for _ in range(2500):
            r.run(1)
            if check():return
        raise AssertionError((policy,r.u16('dbg_bc_native_status'),r.read('continue_prompts',12).hex()))
    scores=[]
    for i in range(a.players):
        name='score' if i==0 else 'peer_scores';offset=0 if i==0 else (i-1)*35
        digits=bytes(map(int,f'{12345+i*10000:08d}'))
        r.write(name,digits,offset);r.write(name,digits,offset+8)
        scores.append((name,offset,digits))
    mask=(1<<a.players)-1
    r.write('dbg_bc_native_die_mask',mask.to_bytes(2,'big'))
    wait(lambda:r.u16('dbg_bc_native_status')==7 and r.read('continue_pending',1)[0]==mask)
    r.run(8)
    r.write('pad',bytes([0x80,0x80]*a.players+[0,0]*(4-a.players)))
    r.run(8);r.write('pad',bytes(8))
    wait(lambda:r.u16('dbg_bc_native_status') in (0,4))
    r.run(12)
    accepted=1 if policy==1 else a.players
    assert r.read('credits',1)==b'\0', 'shared credit underflow/double-spend'
    assert r.read('continue_pending',1)==b'\0'
    assert r.read('scene_paused',1)==b'\0'
    for i,(name,offset,digits) in enumerate(scores):
        resumed=i<accepted
        assert r.u16('dbg_bc_native_party_lives',i*2)==(0 if resumed else 255)
        assert r.read('unused_continues',1,i)[0]==(4 if resumed else 5)
        assert r.read(name,8,offset)==(bytes(8) if resumed else digits)
        assert r.read(name,8,offset+8)==digits
    # Later updates must not repeat the accepted requests or spend again.
    r.run(30)
    assert r.read('credits',1)==b'\0' and r.read('unused_continues',a.players)==bytes(
        [4]*accepted+[5]*(a.players-accepted))
    r.lib.retro_unload_game();r.lib.retro_deinit()
print(f'PASS {a.players}P: simultaneous limited requests spend exactly one credit in slot order; unlimited restores all; scores/highs/ranks isolated; no pause or repeated acceptance')
