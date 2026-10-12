#!/usr/bin/env python3
"""Verify all Home bonus tables on four independent native BC scores."""
from run_rom import Runner

tables = [[100000], [100000,200000,300000,400000,500000],
          [150000,300000,450000,600000], [200000,400000,600000], []]
for option, thresholds in enumerate(tables):
    r=Runner();r.run(2600)
    r.write('home_session',b'\1');r.write('game_cfg',bytes([option]),3)
    for name,value in [('dbg_bc_native_players',4),('dbg_bc_native_start_round',9),
                       ('dbg_bc_native_protect',1),('dbg_bc_native',1)]:
        r.write(name,value.to_bytes(2,'big'))
    r.write('dbg_pad_override',b'\1');r.write('pad',bytes(8));r.run(180)
    assert r.read('home_extend_count',1)[0]==len(thresholds)
    initial=[r.u16('dbg_bc_native_party_lives',i*2) for i in range(4)]
    awarded=[0]*4
    # Cross each boundary one player at a time; queued zero-point commands
    # exercise the actual score task without depending on a particular enemy.
    for threshold in thresholds+[9000000]:
        for score_value in (threshold-1,threshold):
            for i in range(4):
                name='score' if i==0 else 'peer_scores';offset=0 if i==0 else (i-1)*35
                r.write(name,bytes(map(int,f'{score_value:08d}')),offset)
                r.write(name,b'\0'+b'\xff'*15,offset+16)
                r.write(name,b'\0\1',offset+32)
                if awarded[i]<len(thresholds) and score_value>=thresholds[awarded[i]]:
                    awarded[i]+=1
                for _ in range(15):
                    r.run(1)
                    if r.read(name,1,offset+32)==b'\1':break
                assert r.read(name,1,offset+32)==b'\1'
                # The debugger lives snapshot is drawn after score consumption.
                r.run(2)
                assert [r.u16('dbg_bc_native_party_lives',j*2) for j in range(4)]==[
                    initial[j]+awarded[j] for j in range(4)],(option,i,score_value,awarded)
                assert r.read(name,1,offset+34)[0]==awarded[i]
    assert bool(r.u32('dbg_bc_native_actor_sfx_mask') & (1<<22))==bool(thresholds)
    r.lib.retro_unload_game();r.lib.retro_deinit()
print('PASS: all five Home bonus policies, four independent award cursors, below/exact thresholds, exhausted tables and NONE')
