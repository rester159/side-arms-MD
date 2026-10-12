#!/usr/bin/env python3
"""Choose Home Lives through Options; verify BC reserves, deaths and progression."""
import argparse
from run_rom import Runner, PAD, ROOT
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--players',type=int,choices=(1,2,3,4),required=True)
p.add_argument('--lives',type=int,choices=range(1,8),required=True)
a=p.parse_args();r=Runner();r.run(2600)
def tap(button):r.run(5,PAD[button]);r.run(20)
def wait(check,label):
    for _ in range(2200):
        r.run(1)
        if check():return
    raise AssertionError(label)
def reserves():return [r.u16('dbg_bc_native_party_lives',i*2) for i in range(a.players)]
tap('DOWN');tap('START');assert r.u32('flow_state')==9
for _ in range(3):tap('DOWN')
tap('A');assert r.u32('flow_state')==1
tap('DOWN')
for _ in range((a.lives-3)%7):tap('RIGHT')
# This test exercises final game over; continue acceptance has its own test.
tap('DOWN');tap('DOWN')
for _ in range((-r.read('home_cfg',1,3)[0])%3):tap('RIGHT')
tap('B');assert r.u32('flow_state')==9
assert r.read('home_cfg',1,1)==bytes([a.lives])
while r.read('home_cursor',1)!=b'\1':tap('UP')
selected=r.read('home_cfg',1,5)[0]
tap('A')
for _ in range((a.players-selected)%4):tap('DOWN')
tap('A');r.write('dbg_bc_native_protect',b'\0\1')
wait(lambda:r.u32('dbg_bc_native_ticks')>100,'initial entry')
assert r.u16('dbg_bc_native_players')==a.players
assert reserves()==[a.lives-1]*a.players,(a,reserves())
assert r.read('life_offset',1)==b'\1'
# Give the shared round a clear handoff: configured lives must not refill.
r.write('dbg_bc_native_die_mask',b'\0\1')
wait(lambda:reserves()[0]==(a.lives-2 if a.lives>1 else 255),'P1 life debit')
assert reserves()[1:]==[a.lives-1]*(a.players-1)
if a.lives==1:
    if a.players>1:
        assert r.u16('dbg_bc_native_status') in (0,4)
        r.write('dbg_bc_native_die_mask',((1<<a.players)-2).to_bytes(2,'big'))
    wait(lambda:r.u16('dbg_bc_native_status')==7,'last life game over')
    assert reserves()==[255]*a.players
else:
    before=reserves();r.write('dbg_bc_native_status',b'\0\6')
    wait(lambda:r.u16('dbg_bc_native_current_round')==1 and r.u16('dbg_bc_native_status')==0,'round advance')
    assert reserves()==before,(before,reserves())
    r.write('dbg_bc_native_status',b'\0\7')
r.run(20)
out=ROOT/f'.local/bc-home-lives-{a.lives}-{a.players}p';out.mkdir(exist_ok=True)
r.capture(out/'result.png')
tap('START');assert r.u32('flow_state')==9
tap('A');tap('A');r.write('dbg_bc_native_protect',b'\0\1')
wait(lambda:r.u32('dbg_bc_native_ticks')>20 and r.u16('dbg_bc_native_current_round')==0,'reentry')
assert reserves()==[a.lives-1]*a.players
print(f'PASS: Home Options {a.lives} total lives, {a.players}P modal, raw reserves, individual debit, last-life/progression and new-run refill')
