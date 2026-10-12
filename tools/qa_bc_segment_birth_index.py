#!/usr/bin/env python3
"""Compare segment-birth shot caching with the original eight-contact loop."""
import ctypes as C
import subprocess
import tempfile
from pathlib import Path
from qa_bc_beam import ROOT
from qa_bc_common import Player, Event as Contact
from qa_bc_factory import Actor
from qa_bc_enemies import Data
from qa_bc_stage import Stage
from qa_bc_stage_runtime import Resources, Event

Sink = C.CFUNCTYPE(None, C.c_uint8, C.POINTER(Contact), C.c_void_p)
class Party(C.Structure):
    _fields_ = [('players', C.POINTER(Player)*4), ('count', C.c_uint8),
        ('contact_policy', C.c_uint8), ('contact', Sink), ('context', C.c_void_p)] + [
        (n, C.c_uint8) for n in ('shot_bounds_valid', 'shot_min_x', 'shot_max_x',
        'shot_min_y', 'shot_max_y', 'shot_half_x', 'shot_half_y', 'body_bounds_valid')] + [
        (n, C.c_uint16) for n in ('body_min_x', 'body_max_x', 'body_min_y', 'body_max_y')]
class ShotIndex(C.Structure):
    _fields_ = [('slots', C.c_uint8*28), ('count', C.c_uint8),
        ('x', C.c_uint8*28), ('y', C.c_uint8*28)] + [(n, C.c_uint8) for n in
        ('min_x', 'max_x', 'min_y', 'max_y', 'half_x', 'half_y')]


def main():
    source = (ROOT/'src/bc_runtime.c').read_text()
    start = source.index('static void __attribute__((noinline)) segment_birth_contacts(')
    end = source.index('static signed short __attribute__((noinline)) segment_birth(', start)
    reference = source[:start] + source[end:]
    call = '    segment_birth_contacts(actors, members, p, data, count);'
    assert reference.count(call) == 1
    reference = reference.replace(call, '''    for (unsigned char i = 0; i < 8; i++) {
        BcActorEvent event;
        bc_actor_common_into(&event, &actors[members[i]], p, &data->data, count);
        stage_birth_effects(data, members[i], &event);
    }''')
    cases = contacts = hits = failed = 0
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        libs = []
        for name, code in [('indexed', source), ('reference', reference)]:
            path = tmp/(name+'.c'); path.write_text(code)
            out = tmp/(name+'.dylib')
            subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                '-I'+str(ROOT/'inc'), str(path), *(str(ROOT/f'src/{n}.c') for n in
                ('bc_rules', 'bc_world', 'bc_stage', 'bc_score', 'bc_player', 'bc_palette', 'bc_audio')),
                '-o', str(out)], check=True)
            lib = C.CDLL(str(out))
            lib.bc_runtime_stage_event.argtypes = [C.POINTER(Stage), C.POINTER(Actor),
                C.POINTER(Player), C.POINTER(Resources), C.POINTER(C.c_uint8)]
            lib.bc_runtime_stage_event.restype = Event
            lib.bc_shot_index.argtypes = [C.POINTER(ShotIndex), C.c_void_p]
            libs.append(lib)
        for rnd, handler in [(1,0xba7c),(2,0xb5c1),(3,0xb6f6),(4,0xb6bb),(6,0xb705),(7,0xbe25)]:
            program = bytearray((ROOT/f'.local/pce-reference/round{rnd+1:02d}-reference/code-002160.bin').read_bytes())
            signature = bytes.fromhex('bdcc2df0273a9dcc2d')
            assert program.count(signature) == 1
            shift = program.index(signature)+0x4000-0x9204
            for variant in range(2):
                h = handler+variant*4
                program[0x3000:0x3004] = bytes((0,h&255,h>>8,255))
                for n in range(1,5):
                    for scenario in range(12):
                        outputs = []
                        for lib in libs:
                            rom = (C.c_uint8*len(program)).from_buffer_copy(program)
                            resources = Resources(); resources.data = Data(rom,0x4000)
                            resources.round = rnd; resources.relocation = shift
                            resources.segment_bases[:] = [0x100+i*32 for i in range(6)]
                            pool = (Actor*32)(); players = (Player*4)(); indices = (ShotIndex*4)()
                            party_events = []; birth_events = []
                            cb = Sink(lambda i,e,c: party_events.append((i, bytes(e.contents))))
                            birth = Sink(lambda i,e,c: birth_events.append((i, bytes(e.contents))))
                            party = Party(); party.count = n; party.contact = cb
                            resources.birth_sink = C.cast(birth,C.c_void_p)
                            for i,p in enumerate(players):
                                p.x = 264<<8; p.y = 168<<8; p.state = 128
                                p.inventory.lives = 3
                                p.invulnerability = 200 if scenario in (0,8,9,10,11) else 0
                                if scenario == 8 or (scenario == 9 and i%2):p.state = 0
                                if scenario == 11 and i == 0:p.invulnerability = 0
                                if scenario in (1,2,3,5,6,7,10):
                                    for j,s in enumerate(p.weapons.shots[:28]):
                                        s.body.state = 128 if scenario != 3 or j%3 == 0 else 64
                                        s.body.x = (252 if j%2 == 0 else 40)<<8; s.body.y = 168<<8
                                        s.body.half_x = 20; s.body.half_y = 8
                                        s.body.damage = 1+(j%4); s.kind = 2 if scenario == 2 else 0
                                if scenario == 5:
                                    lib.bc_shot_index(C.byref(indices[i]), C.byref(p.weapons))
                                    p.shot_index = C.addressof(indices[i])
                                party.players[i] = C.pointer(p)
                                if n > 1:p.party = C.addressof(party)
                            if scenario == 6 and n>1:party.players[n-1] = C.POINTER(Player)()
                            if scenario == 7:
                                for a in pool[:3]:a.body.state = 128
                            if scenario == 4:
                                for a in pool:a.body.state = 128
                            before_indices = [p.shot_index for p in players]
                            stage = Stage(); stage.script = 0x7000; count = C.c_uint8()
                            event = lib.bc_runtime_stage_event(C.byref(stage),pool,C.byref(players[0]),C.byref(resources),C.byref(count))
                            assert [p.shot_index for p in players] == before_indices, 'index not restored'
                            assert party.contact_policy == 0, 'temporary contact policy leaked'
                            # Pointers differ between fixtures; all gameplay bytes must agree.
                            state = tuple(bytes(p)[:Player.shot_index.offset] for p in players)
                            outputs.append((bytes(stage),bytes(pool),state,count.value,bytes(event),party_events,birth_events))
                            if lib == libs[0]:
                                contacts += len(party_events)
                                hits += sum(s.body.state == 64 for p in players for s in p.weapons.shots) if scenario != 3 else 0
                                if scenario == 4:
                                    assert event.slot == -1 and not birth_events
                                    failed += 1
                                else:assert len(birth_events) == 8, (rnd,variant,n,scenario,len(birth_events))
                        assert outputs[0] == outputs[1], (rnd,variant,n,scenario)
                        cases += 1
    assert contacts and hits and failed
    print(f'PASS: {cases} segment births, {contacts} ordered party contacts, {hits} consumed shots, {failed} allocation failures; all six rounds, both variants, 1–4P, index restoration, null member and occupied prefixes')

if __name__ == '__main__':main()
