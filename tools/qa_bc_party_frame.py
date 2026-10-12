#!/usr/bin/env python3
"""Shared co-op frame clocks, independent input/weapons and latched respawn requests."""
import argparse
import ctypes as C
import subprocess
import tempfile
from pathlib import Path
from qa_bc_common import Player,Event as Contact
from qa_bc_factory import Actor
from qa_bc_player_flow import Control
from qa_bc_player_runtime import Event as PlayerEvent
from qa_bc_stage import Stage
from qa_bc_stage_runtime import Resources,Audio
from qa_bc_actor_step import StepData
from qa_bc_rules import Terrain
from qa_bc_enemies import Data
from qa_bc_weapons import Weapons
from qa_bc_beam import ROOT
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--legacy',action='store_true',help='Exercise the return-by-value compatibility wrapper')
args=parser.parse_args()
Sink=C.CFUNCTYPE(None,C.c_uint8,C.POINTER(Contact),C.c_void_p)
class Party(C.Structure):
    _fields_=[('players',C.POINTER(Player)*4),('count',C.c_uint8),('contact_policy',C.c_uint8),('contact',Sink),('context',C.c_void_p)]+[(n,C.c_uint8) for n in ('shot_bounds_valid','shot_min_x','shot_max_x','shot_min_y','shot_max_y','shot_half_x','shot_half_y','body_bounds_valid')]+[(n,C.c_uint16) for n in ('body_min_x','body_max_x','body_min_y','body_max_y')]
class Scale(C.Structure):
    _fields_=[('remainder',C.c_uint8*9)]
class Pending(C.Structure):
    _fields_=[('script',C.c_uint16),('size',C.c_uint8),('copies',C.c_uint8)]
class WaveQueue(C.Structure):
    _fields_=[('scale',Scale),('pending',Pending*8),('head',C.c_uint8),('count',C.c_uint8),
              ('delay',C.c_uint8),('originals',C.c_uint16),('extras',C.c_uint16),('blocked',C.c_uint16)]
class Group(C.Structure):
    _fields_=[('contacts',Party),('players',C.POINTER(Control)*4),('waiting',C.c_uint8),('waves',WaveQueue)]
class Cursor(C.Structure):
    _fields_=[('stage_events',C.c_uint16),('scrolling',C.c_uint8)]
class Result(C.Structure):
    _fields_=[('players',PlayerEvent*4),('handler',C.c_uint16),('stage_events',C.c_uint16),
              ('status',C.c_uint8),('next_slot',C.c_uint8),('checkpoints',C.c_uint8)]

with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'party.dylib'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
        *(str(ROOT/f'src/{n}.c') for n in ('bc_rules','bc_world','bc_stage','bc_runtime','bc_frame','bc_party','bc_wave','bc_wave_queue','bc_score','bc_player','bc_palette','bc_audio')),
        '-o',str(path)],check=True)
    lib=C.CDLL(str(path))
    lib.bc_party_bind.argtypes=[C.POINTER(Group),C.POINTER(C.POINTER(Control)),C.c_uint8,Sink,C.c_void_p]
    lib.bc_party_bind.restype=C.c_uint8
    lib.bc_runtime_party_frame.argtypes=[C.POINTER(Group),C.POINTER(Cursor),C.POINTER(Actor),C.POINTER(Stage),
        C.POINTER(Resources),C.POINTER(StepData),C.c_uint16,C.POINTER(C.c_uint8),C.POINTER(C.c_uint8),C.POINTER(C.c_uint8),C.c_void_p]
    lib.bc_runtime_party_frame.restype=Result
    lib.bc_runtime_party_frame_into.argtypes=[C.POINTER(Result)]+lib.bc_runtime_party_frame.argtypes
    lib.bc_runtime_party_frame_into.restype=None
    lib.bc_player_step.argtypes=[C.POINTER(Control),C.c_uint8,C.c_uint8,C.c_uint16,C.c_uint16,C.c_uint16,C.c_uint16,C.POINTER(Terrain),C.POINTER(Data),C.c_uint16]
    lib.bc_player_step.restype=PlayerEvent
    lib.bc_weapons_record_position.argtypes=[C.POINTER(Weapons),C.c_uint16,C.c_uint16]
    rom=(C.c_uint8*65536)();cells=(C.c_uint8*16384)()
    data=Data(rom,0);held=(C.c_uint8*4)(0x21,0x82,0x10,0x40);pressed=(C.c_uint8*4)(1,2,0,0)
    @Sink
    def sink(slot,event,ctx):pass
    def fixture(n):
        ps=(Control*4)();group=Group()
        for i,p in enumerate(ps):
            p.world.state=0x80;p.world.x=(64+i*32)<<8;p.world.y=112<<8;p.speed=2
        ptrs=(C.POINTER(Control)*4)(*(C.pointer(p) for p in ps))
        assert lib.bc_party_bind(C.byref(group),ptrs,n,sink,None)
        stage=Stage();stage.stopped=1;stage.boss_active=16;stage.shot_limit=16
        ad=StepData();ad.data=data;ad.terrain=Terrain(cells,rom)
        sd=Resources();sd.data=data
        return ps,group,stage,ad,sd,Cursor(),(Actor*32)(),C.c_uint8()
    def frame(g,stage,ad,sd,cursor,pool,count):
        if args.legacy:
            return lib.bc_runtime_party_frame(C.byref(g),C.byref(cursor),pool,C.byref(stage),C.byref(sd),
                C.byref(ad),0x1000,held,pressed,C.byref(count),None)
        result=Result();C.memset(C.byref(result),0xa5,C.sizeof(result))
        lib.bc_runtime_party_frame_into(C.byref(result),C.byref(g),C.byref(cursor),pool,C.byref(stage),C.byref(sd),
            C.byref(ad),0x1000,held,pressed,C.byref(count),None)
        return result
    for n in (1,2,3,4):
        ps,g,stage,ad,sd,cursor,pool,count=fixture(n)
        expected=[Control.from_buffer_copy(bytes(p)) for p in ps]
        for i,p in enumerate(expected[:n]):
            lib.bc_player_step(C.byref(p),held[i],pressed[i],0,0,0,0,C.byref(ad.terrain),C.byref(data),0x1000)
            lib.bc_weapons_record_position(C.byref(p.world.weapons),p.world.x>>8,p.world.y>>8)
        result=frame(g,stage,ad,sd,cursor,pool,count)
        assert result.status==0 and result.next_slot==32
        assert all(bytes(v)==bytes(C.sizeof(PlayerEvent)) for v in result.players[n:])
        assert stage.boss_active==15 and ad.boss_active==15
        assert [bytes(p) for p in ps]==[bytes(p) for p in expected]
        # Move the world once, regardless of how many controllers are bound.
        stage.stopped=0;stage.dx=85;stage.script=0x3000;rom[0x3000]=255
        assert frame(g,stage,ad,sd,cursor,pool,count).status==0
        assert stage.x==85
        if n==4:
            assert ps[0].world.x>64<<8 and ps[1].world.x<96<<8
            assert ps[2].world.y<112<<8 and ps[3].world.y>112<<8
            assert ps[0].world.weapons.shots[0].body.state and ps[1].world.weapons.shots[0].body.state
    ps,g,stage,ad,sd,cursor,pool,count=fixture(4)
    a=pool[0];a.routine=0x9eb1;a.body.state=0x80;a.body.timer=200;a.body.flags=3
    a.body.x=a.body.y=100<<8;a.body.vx=256
    ps[1].world.state=0;ps[1].death_clock=160
    result=frame(g,stage,ad,sd,cursor,pool,count)
    assert result.checkpoints==2 and g.waiting==2 and result.status==0
    assert a.body.x==101<<8 and a.body.timer==199
    assert frame(g,stage,ad,sd,cursor,pool,count).checkpoints==0 and ps[1].death_clock==161
    for i in (0,2,3):ps[i].world.state=0;ps[i].death_clock=160
    before=bytes(a);result=frame(g,stage,ad,sd,cursor,pool,count)
    assert result.status==1 and result.checkpoints==13 and g.waiting==15 and bytes(a)==before
    assert bytes(result.players[1])==bytes(C.sizeof(PlayerEvent))
    # A stage audio wait must not consume any of the four inputs, scroll,
    # tick boss timers or partially update player weapons.
    ps,g,stage,ad,sd,cursor,pool,count=fixture(4)
    stage.stopped=0;stage.dx=85;stage.script=0x3000
    rom[0x3000:0x3004]=(0,0x50,0x8c,255)
    audio=Audio();sd.audio=C.pointer(audio)
    before=bytes(ps)
    for _ in range(3):
        result=frame(g,stage,ad,sd,cursor,pool,count)
        assert result.status==4 and audio.state==1 and bytes(ps)==before
        assert bytes(result.players)==bytes(C.sizeof(result.players))
        assert stage.x==0 and stage.boss_active==16 and stage.script==0x3000
    audio.state=2
    result=frame(g,stage,ad,sd,cursor,pool,count)
    assert result.status==0 and result.stage_events==1 and stage.x==85
    assert stage.script==0x3003 and stage.boss_active==15 and audio.state==0
    # Peeking a pending-wave boundary must consume a script page marker once.
    ps,g,stage,ad,sd,cursor,pool,count=fixture(4)
    stage.stopped=0;stage.dx=85;stage.x=255<<8;stage.script=0x3100
    rom[0x3100:0x3105]=(255,254,255,255,255)
    g.waves.count=1;g.waves.delay=20
    result=frame(g,stage,ad,sd,cursor,pool,count)
    assert result.status==0 and stage.script==0x3102 and stage.x==(255<<8)+85
    assert g.waves.delay==19
    # Twelve original waves at one camera coordinate exceed the bounded queue.
    # The camera waits, but actors/player clocks continue and every source
    # record is executed once. A following stop event waits for all copies.
    rom[0xabb1:0xabb1+19]=(128,200,34,0,20,8,8,0,0,0,0,0,0,0,0x50,0xb1,0x9e,0xb1,0x9e)
    for i in range(12):rom[0x3000+i*3:0x3003+i*3]=(0,0x34,0xaa)
    rom[0x3024:0x3028]=(0,0x17,0x8c,255)
    ps,g,stage,ad,sd,cursor,pool,count=fixture(4)
    stage.stopped=0;stage.dx=85;stage.script=0x3000
    result=frame(g,stage,ad,sd,cursor,pool,count)
    assert result.status==0 and result.stage_events==8 and g.waves.count==8
    assert stage.x==0 and stage.script==0x3018 and cursor.scrolling==1
    assert pool[0].body.timer==198,'birth and actor update both required'
    for _ in range(180):
        for actor in pool:actor.body.state=0
        result=frame(g,stage,ad,sd,cursor,pool,count)
        assert result.status==0
        if stage.stopped:break
    else:raise AssertionError('queued stage boundary never drained')
    assert (g.waves.originals,g.waves.extras,g.waves.count)==(12,15,0)
    assert stage.script==0x3027
    # Failed source births must keep their script pointer and earn no copies.
    ps,g,stage,ad,sd,cursor,pool,count=fixture(3)
    stage.stopped=0;stage.dx=85;stage.script=0x3000
    for actor in pool:
        actor.body.state=128;actor.body.flags=35;actor.body.timer=200;actor.routine=0x9eb1
    result=frame(g,stage,ad,sd,cursor,pool,count)
    assert result.status==0 and not result.stage_events
    assert stage.script==0x3000 and stage.x==0 and not g.waves.originals
    assert pool[0].body.timer==199,'pool pressure must not freeze existing actors'
    for actor in pool:actor.body.state=0
    assert frame(g,stage,ad,sd,cursor,pool,count).status==0
    assert g.waves.originals==12 and stage.script==0x3024
    # Invalid counts and event-budget exits must clear every player output.
    for n in (0,5):
        ps,g,stage,ad,sd,cursor,pool,count=fixture(4)
        g.contacts.count=n
        result=frame(g,stage,ad,sd,cursor,pool,count)
        assert result.status==5 and bytes(result.players)==bytes(C.sizeof(result.players))
    ps,g,stage,ad,sd,cursor,pool,count=fixture(4)
    cursor.stage_events=256
    result=frame(g,stage,ad,sd,cursor,pool,count)
    assert result.status==5 and bytes(result.players)==bytes(C.sizeof(result.players))
    # Invalid binding must not partially overwrite a live group or its players.
    before=bytes(g);ptrs=(C.POINTER(Control)*4)(*(C.pointer(ps[0]) for _ in range(4)))
    assert not lib.bc_party_bind(C.byref(g),ptrs,4,sink,None) and bytes(g)==before
print('PASS: 1/2/3/4 independent input/weapon/trail updates, one camera/boss/enemy clock, latched individual/all-player checkpoints, audio waits, queued wave counts/overflow/boundaries, allocation retries, invalid binding')
