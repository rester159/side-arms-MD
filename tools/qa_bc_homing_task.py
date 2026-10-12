#!/usr/bin/env python3
"""Compare the direct homing-bullet task with the general dispatcher.

Synthetic terrain covers solid/empty cells, wrapping cameras, scrolling,
damage-lock countdowns, turn-timer wrap and all ten round resources. This is a task differential,
not a source-game or whole-campaign fidelity claim.
"""
import ctypes as C
import random
import subprocess
import tempfile
from pathlib import Path
from qa_bc_beam import ROOT
from qa_bc_factory import Actor
from qa_bc_actor_step import StepData, Event
from qa_bc_common import Player, Event as CommonEvent
from qa_bc_enemies import Data
from qa_bc_rules import Terrain

rng = random.Random(0x8b17)
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)/'world.dylib'
    subprocess.run(['cc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-shared', '-fPIC', '-I'+str(ROOT/'inc'),
                    str(ROOT/'src/bc_rules.c'), str(ROOT/'src/bc_world.c'),
                    '-o', str(path)], check=True)
    lib = C.CDLL(str(path))
    lib.bc_actor_step.argtypes = [C.POINTER(Actor), C.c_uint8, C.POINTER(Player),
        C.POINTER(StepData), C.POINTER(C.c_uint8), C.c_uint8,
        C.c_int16, C.c_int16, C.c_uint8]
    lib.bc_actor_step.restype = Event
    lib.bc_actor_scroll.argtypes = [C.POINTER(Actor), C.c_int16, C.c_int16, C.c_uint8]
    lib.bc_actor_homing_common_into.argtypes = [C.POINTER(CommonEvent),
        C.POINTER(Actor), C.POINTER(Player), C.POINTER(StepData), C.POINTER(C.c_uint8)]
    lib.bc_actor_homing_map_into.argtypes = lib.bc_actor_homing_common_into.argtypes + [C.POINTER(C.c_uint8)]
    lib.bc_terrain_solid.argtypes = [C.POINTER(Terrain), C.c_uint16, C.c_uint16]
    lib.bc_terrain_solid.restype = C.c_uint8
    cells = (C.c_uint8*16384)(*(rng.randrange(256) for _ in range(16384)))
    attrs = (C.c_uint8*2048)(*(rng.choice((0, 0, 1, 2, 15, 16, 128)) for _ in range(2048)))
    programs=[]
    signature=bytes.fromhex('bdcc2df0273a9dcc2d')
    for n in range(10):
        folder='play-task-round1' if n==0 else f'round{n+1:02d}-reference'
        source=(ROOT/'.local/pce-reference'/folder/'code-002160.bin').read_bytes()
        programs.append(((C.c_uint8*65536).from_buffer_copy(source), source.index(signature)+0x4000-0x9204))
    data = StepData(); data.terrain = Terrain(cells, attrs)
    solid_map = (C.c_uint8*65536)(*(attrs[cells[((y//16)*16+x//16)*64+(y%16//2)*8+x%16//2]*8+(x&1)*2+(y&1)*4+1]&15 for y in range(256) for x in range(256)))
    hits = empty = 0
    for case in range(16000):
        data.round=case%10
        program,relocation=programs[data.round]
        data.data=Data(program,0x4000);data.relocation=relocation
        actors = (Actor*32)(); a = actors[0]
        a.direction = rng.randrange(16); a.speed = rng.choice((0,2,4,6))
        a.wait = rng.choice((0,1,2,5,255))
        a.routine = (0x8b17+relocation)&65535; a.death_routine = (0x8a72+relocation)&65535
        a.body.state = 0x80; a.body.timer = rng.randrange(2, 256)
        a.body.x = rng.randrange(1 << 24); a.body.y = rng.randrange(1 << 24)
        if case % 2:
            a.body.x = rng.randrange(256) << 8; a.body.y = rng.randrange(256) << 8
        a.body.vx = rng.randrange(-2048, 2049); a.body.vy = rng.randrange(-2048, 2049)
        a.body.flags = rng.choice((0, 2, 4, 16, 18))
        a.body.damage_lock = rng.choice((0, 1, 2, 255))
        a.body.hp = 2; a.half_x = a.half_y = 4
        a.probe_x = rng.randrange(256); a.probe_y = rng.randrange(256)
        p = Player(); p.state = rng.choice((0, 0x80)); p.invulnerability = rng.choice((0, 1, 255))
        p.x = rng.randrange(256) << 8; p.y = rng.randrange(256) << 8
        other = Actor.from_buffer_copy(a); peer = Player.from_buffer_copy(p)
        count = C.c_uint8(rng.randrange(256)); count2 = C.c_uint8(count.value)
        data.camera_x = rng.randrange(65536); data.camera_y = rng.randrange(65536)
        dx, dy, stopped = rng.randrange(-32, 33), rng.randrange(-32, 33), rng.randrange(2)
        event = CommonEvent.from_buffer_copy(bytes([0xa5])*C.sizeof(CommonEvent))
        mapped = Actor.from_buffer_copy(other); mapped_player = Player.from_buffer_copy(peer)
        mapped_count = C.c_uint8(count2.value); mapped_event = CommonEvent.from_buffer_copy(event)
        want = lib.bc_actor_step(actors, 0, C.byref(p), C.byref(data), C.byref(count), 32, dx, dy, stopped)
        lib.bc_actor_scroll(C.byref(other), dx, dy, stopped)
        # Solid probes must overwrite the poisoned event with zeros, bypass
        # common motion and decrement damage_lock exactly once.
        old_lock = other.body.damage_lock
        solid = lib.bc_terrain_solid(C.byref(data.terrain),
            data.camera_x + (other.body.x >> 8), data.camera_y + (other.body.y >> 8))
        lib.bc_actor_homing_common_into(C.byref(event), C.byref(other), C.byref(peer), C.byref(data), C.byref(count2))
        lib.bc_actor_scroll(C.byref(mapped), dx, dy, stopped)
        lib.bc_actor_homing_map_into(C.byref(mapped_event), C.byref(mapped), C.byref(mapped_player), C.byref(data), C.byref(mapped_count), solid_map)
        assert bytes(mapped)==bytes(other) and bytes(mapped_event)==bytes(event), (case, 'direct-map actor/event')
        assert bytes(mapped_player)==bytes(peer) and mapped_count.value==count2.value, (case, 'direct-map player/count')
        assert want.handled and bytes(event) == bytes(want.actor_event), (case, 'event')
        assert bytes(a) == bytes(other), (case, 'actor')
        assert bytes(p) == bytes(peer) and count.value == count2.value, (case, 'player/count')
        if solid:
            assert other.body.state == 0x40 and not any(bytes(event))
            hits += 1
            assert other.body.damage_lock == max(0, old_lock-1)
        else:
            empty += 1
    assert hits and empty
    print(f'PASS: 16000 homing-task comparisons across ten rounds, {hits} terrain-hit paths, '
          f'{empty} common paths; events, actors, players and counters match')
