#!/usr/bin/env python3
"""Regression for selected lookahead inputs matching the first forecast action.

Uses a deterministic shadow runner to force alternate selection and unavoidable
collisions; it is not a game, survival, or performance verification.
"""
import ctypes as C
import bc_pilot_lookahead as pilot

class Layout:
    o={'bc_state':8,'bc_player_size':16}

class FakeRunner:
    def __init__(self,phase,mode,shadow=False):
        self.ram=(C.c_uint8*65536)();self.symbols={'player':0};self.tick=phase;self.start_tick=phase;self.mode=mode
        self.pads=bytes(8);self.trace=[];self.setpos(100,100);self.ram[8^1]=0x80
        if not shadow:self._pilot_shadow=FakeRunner(phase,mode,True)
    def setpos(self,x,y):
        for off,val in [(0,x<<8),(4,y<<8)]:
            for k,b in enumerate(val.to_bytes(4,'big')):self.ram[(off+k)^1]=b
    def u16(self,name):return 1 if name=='dbg_bc_native_players' else 0
    def u32(self,name):return self.tick if name=='dbg_bc_native_ticks' else 0
    def write(self,name,data):
        assert name=='pad';self.pads=bytes(data);self.trace.append((self.tick,bytes(data)))
    def run(self,n):
        assert n==1
        direction=self.pads[0]&15;self.tick+=1;elapsed=self.tick-self.start_tick
        dx=(bool(direction&1)-bool(direction&2));dy=(bool(direction&4)-bool(direction&8))
        self.setpos(100+elapsed*dx,100+elapsed*dy)
        if self.mode=='all_die':limit=1 if direction==1 else 3 if direction==2 else 2
        elif self.mode=='alternative':limit=1 if direction==1 else 999
        else:limit=999
        if elapsed>=limit:self.ram[8^1]=0x40

class Snapshot:
    def __init__(self,r):self.r=r;self.tick=r.tick;self.raw=bytes(r.ram);self.pads=r.pads
    def restore(self,target=None):
        r=target or self.r;r.tick=self.tick;r.start_tick=self.tick;r.ram[:]=self.raw;r.pads=self.pads


original_snapshot = pilot.PilotSnapshot
pilot.PilotSnapshot = Snapshot
checks = 0
try:
    for phase in range(6):
        for horizon in (4, 12, 16):
            for survival in (False, True):
                for rapid in (False, True):
                    for mode in ('proposed_survives', 'alternative', 'all_die'):
                        proposed = 1 | (0x20 if phase < 3 else 0)
                        pads = bytes([proposed, proposed, 2, 2, 4, 4, 8, 8])
                        sides = (0x20, 0, 0, 0) if rapid else None
                        r = FakeRunner(phase, mode)
                        before = bytes(r.ram)
                        chosen = pilot.choose_move(r, Layout(), proposed, 0,
                            (100, 100), horizon=horizon,
                            survival_tiebreak=survival, statistics={},
                            party_pads=pads, rapid_fire_sides=sides)
                        assert bytes(r.ram) == before and r.tick == phase
                        assert chosen & 0x30 == proposed & 0x30, (phase, horizon, survival, rapid, mode)
                        if mode == 'proposed_survives':
                            assert chosen == proposed
                        else:
                            assert chosen & 15 != proposed & 15, 'Did not exercise alternative selection'
                        assert not r._pilot_shadow._pilot_search
                        checks += 1
finally:
    pilot.PilotSnapshot = original_snapshot
print(f'PASS: {checks} first-action fire cases; alternate/surviving/all-dying branches, all fire phases, horizons4/12/16, both tie-break modes and unchanged live state')
