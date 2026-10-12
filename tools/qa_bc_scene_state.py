#!/usr/bin/env python3
"""Verify scene-comparison coverage and its intentional pointer exclusions."""
import bc_scene_state as state

def encode_player(source):
    out=bytearray(source[:8])
    for slot in range(30):
        shot=source[8+slot*32:8+(slot+1)*32]
        for at in (0,4):
            a,b,c,d=shot[at:at+4]
            out.extend((b,c,d,a) if state.beam_rotation() else (a,b,c,d))
        if state.VELOCITY_SHIFT:
            for at in (8,10):out.extend((int.from_bytes(shot[at:at+2],'big',signed=True)*256).to_bytes(4,'big',signed=True))
            out.extend(shot[12:])
        else:out.extend(shot[8:])
    out.extend(source[968:])
    assert len(out)==state.PLAYER_BYTES
    return bytes(out)

class Memory:
    def __init__(self):
        self.ram = bytearray((i*19+7) & 255 for i in range(65536))
        self.symbols = dict(player=0x1000, stage=0x2000, score=0x2100,
                            peer_scores=0x2200, seed=0x2300, credits=0x2310,
                            unused_continues=0x2320, continue_prompts=0x2330,
                            continue_pending=0x2340, continue_shown=0x2341,
                            party_count=0x2342, peers=0x0800)
        self.primary_source=bytes((i*19+7)&255 for i in range(1024))
        for member in range(4):
            address=self.symbols['player'] if member==0 else 0x3000+(member-1)*state.PLAYER_BYTES
            for offset,value in enumerate(encode_player(self.primary_source)):
                self.ram[(address+offset)^1]=value
        for i, v in enumerate((0x3000).to_bytes(4, 'big')):
            self.ram[(0x800+i)^1] = v
    def read(self, name, n):
        return bytes(self.ram[(self.symbols[name]+i)^1] for i in range(n))
    def u32(self, name):
        return int.from_bytes(self.read(name, 4), 'big')

state.validate_native_layout()
r = Memory()
actors = bytes((i*11) & 255 for i in range(1600))
state.read_actor_pool = lambda runner: actors
checks = 0
for players in range(1, 5):
    r.ram[r.symbols['party_count']^1] = players
    baseline = state.canonical_scene_bytes(r, players)
    assert len(baseline) == state.state_layout(players)['total_hashed_bytes']
    primary=r.primary_source
    old_solo = (actors + r.read('stage', 24) + primary[:1000] + primary[1008:] +
                r.read('seed', 2) + r.read('score', 35) + r.read('credits', 1) +
                r.read('unused_continues', 4))
    assert baseline[:2682] == old_solo
    included = []
    excluded = []
    for i in range(4):
        base = r.symbols['player'] if i == 0 else 0x3000+(i-1)*state.PLAYER_BYTES
        for offset in (0, 1, 511, state.NATIVE_LAYOUT["pointer_start"]-1, state.NATIVE_LAYOUT["pointer_end"], state.PLAYER_BYTES-1):
            (included if i < players else excluded).append(base+offset)
        excluded.extend(base+offset for offset in range(state.NATIVE_LAYOUT["pointer_start"], state.NATIVE_LAYOUT["pointer_end"]))
    for name, size in [('stage',24), ('seed',2), ('score',35), ('credits',1), ('unused_continues',4)]:
        included.extend(r.symbols[name]+i for i in range(size))
    for i in range(105):
        (included if i < (players-1)*35 else excluded).append(r.symbols['peer_scores']+i)
    for name, size in [('continue_prompts',12), ('continue_pending',1), ('continue_shown',1)]:
        (included if players > 1 else excluded).extend(r.symbols[name]+i for i in range(size))
    for addresses, changes in ((included, True), (excluded, False)):
        for address in addresses:
            r.ram[address^1] ^= 0x80
            assert (state.canonical_scene_bytes(r, players) != baseline) == changes, (players,hex(address))
            r.ram[address^1] ^= 0x80
            checks += 1
print(f'PASS: {checks} scene-state coverage/exclusion mutations across 1–4P; solo prefix unchanged')
