#!/usr/bin/env python3
"""Exercise native 4P continues, shared credits, restart and bonus ranks."""
from run_rom import ROOT,Runner
r=Runner();r.run(2600)
r.write('home_session',b'\1')
r.write('game_cfg',bytes([1,3,1,4,1,1,1,1]))
r.write('home_cfg',b'\2',4)
for name,value in [('dbg_bc_native_players',4),('dbg_bc_native_start_round',0),
                   ('dbg_bc_native_protect',1),('dbg_bc_native',1)]:r.write(name,value.to_bytes(2,'big'))
r.write('dbg_pad_override',b'\1');r.write('pad',bytes(8));r.run(200)
def wait(check):
    for _ in range(2500):
        r.run(1)
        if check():return
    raise AssertionError(('timeout',r.u16('dbg_bc_native_status'),r.read('continue_prompts',12).hex()))
def start(ids):
    pad=bytearray(8)
    for i in ids:pad[i*2:i*2+2]=b'\x80\x80'
    r.write('pad',pad);r.run(6);r.write('pad',bytes(8))
def lives():return [r.u16('dbg_bc_native_party_lives',i*2) for i in range(4)]
assert r.read('credits',1)==b'\1'
r.write('score',bytes(map(int,'00012345')))
r.write('peer_scores',bytes(map(int,'00045678')),70)
r.write('peer_scores',bytes(map(int,'00999999')),78)
r.write('dbg_bc_native_die_mask',b'\0\10')
wait(lambda:r.read('continue_pending',1)==b'\10')
out=ROOT/'.local/bc-continue-scene';out.mkdir(exist_ok=True)
r.run(8);r.capture(out/'p4-prompt.png')
before=r.u32('dbg_bc_native_ticks');start([3])
wait(lambda:lives()[3]==0 and r.read('continue_pending',1)==b'\0')
assert r.u32('dbg_bc_native_ticks')>before and r.u16('dbg_bc_native_current_round')==0
assert r.read('credits',1)==b'\0' and r.read('unused_continues',4)==bytes([5,5,5,4])
assert r.read('peer_scores',8,70)==bytes(8) and r.read('peer_scores',8,78)==bytes(map(int,'00999999'))
assert r.read('score',8)==bytes(map(int,'00012345')) and r.read('scene_paused',1)==b'\0'
# With no limited credits remaining, another exhausted player gets no prompt.
r.write('dbg_bc_native_die_mask',b'\0\1');wait(lambda:lives()[0]==255)
r.run(5);assert not r.read('continue_pending',1)[0]&1
# Unlimited offers do not need or consume credits. All-out acceptance restarts
# the current round, restoring only the accepting member.
r.write('game_cfg',b'\2',5)
r.write('dbg_bc_native_die_mask',b'\0\16')
wait(lambda:r.u16('dbg_bc_native_status')==7 and r.read('continue_pending',1)[0]&2)
r.run(8);r.capture(out/'team-prompt.png');start([1])
wait(lambda:r.u16('dbg_bc_native_status') in (0,4) and lives()[1]==0)
assert lives()[0]==255 and lives()[2:]==[255,255]
assert r.read('credits',1)==b'\0' and r.read('unused_continues',4)==bytes([5,4,5,4])
assert r.read('scene_paused',1)==b'\0'
# Timeout the remaining prompts and keep the accepted teammate playing.
wait(lambda:r.read('continue_pending',1)==b'\0')
assert r.read('continue_pending',1)==b'\0' and r.u16('dbg_bc_native_status') in (0,4)
r.capture(out/'continued.png')
# Move through the real round handoffs, then verify the continued player's
# final bonus uses four unused-continue ranks (160K per surviving robot).
for round_index in range(1,10):
    for _ in range(2500):
        if r.u16('dbg_bc_native_current_round')==round_index:break
        r.write('dbg_bc_native_status',b'\0\6');r.run(1)
    assert r.u16('dbg_bc_native_current_round')==round_index
    r.run(12)
for _ in range(100):
    if r.read('ending_bonus_phase',1)==b'\1':break
    r.write('dbg_bc_native_status',b'\0\6');r.run(1)
assert r.read('ending_bonus_phase',1)==b'\1'
assert r.read('ending_bonus_units',8)==b'\0\0\0\x10\0\0\0\0'
# Restart a fresh solo session to exercise the original all-out path directly.
r.lib.retro_unload_game();r.lib.retro_deinit()
r=Runner();r.run(2600);r.write('home_session',b'\1')
r.write('game_cfg',bytes([1,3,1,4,1,1,1,1]));r.write('home_cfg',b'\2',4)
for name,value in [('dbg_bc_native_players',1),('dbg_bc_native_start_round',0),
                   ('dbg_bc_native_protect',1),('dbg_bc_native',1)]:r.write(name,value.to_bytes(2,'big'))
r.write('dbg_pad_override',b'\1');r.write('pad',bytes(8));r.run(200)
r.write('score',bytes(map(int,'00012345')))
r.write('dbg_bc_native_die_mask',b'\0\1')
wait(lambda:r.u16('dbg_bc_native_status')==7 and r.read('continue_pending',1)==b'\1')
start([0]);wait(lambda:r.u16('dbg_bc_native_status') in (0,4))
assert r.read('credits',1)==b'\0' and r.read('unused_continues',1)==b'\4'
assert r.read('score',8)==bytes(8) and r.u16('dbg_bc_native_lives')==0
# OFF must suppress a new offer even if a credit is available.
r.write('credits',b'\1');r.write('game_cfg',b'\0\0',4)
r.write('dbg_bc_native_die_mask',b'\0\1');wait(lambda:r.u16('dbg_bc_native_status')==7)
r.run(4);assert r.read('continue_pending',1)==b'\0'
start([0]);wait(lambda:not r.u16('dbg_bc_native') and r.u32('flow_state')==9)
print('PASS: P4 limited continue, independent scores/highs/ranks, exhausted credits, unlimited all-out restart, no inactive-player revival/pause, prompt expiry')
