#!/usr/bin/env python3
"""Compare native gameplay tasks while carrying player/weapons across tasks.
--full-frame also carries stage/enemies within each captured life segment.
Score/RNG and scheduler inputs still come from the source at task boundaries;
palette animation and checkpoint loading are outside this comparison.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import ROOT,Beam,decode
from qa_bc_factory import Actor,actor
from qa_bc_enemies import Data,Enemy
from qa_bc_player_flow import state,Control
from qa_bc_player_runtime import Event as PlayerEvent
from qa_bc_stage import Stage,state as stage_state
from qa_bc_rules import Terrain
from qa_bc_boss_effects import Sequence
from qa_bc_actor_step import StepData
from qa_bc_score import Score,decode as score_state


from qa_bc_actor_loop import RuntimeEvents
from qa_bc_stage_runtime import Resources, Palette, Audio, palette_state


class PlayResult(C.Structure):
    _fields_=[("player_event",PlayerEvent),("status",C.c_uint8),("next_slot",C.c_uint8)]

class FrameResult(C.Structure):
    _fields_=[('play',PlayResult),('handler',C.c_uint16),('stage_events',C.c_uint16),('status',C.c_uint8)]

class FrameCursor(C.Structure):
    _fields_=[('stage_events',C.c_uint16),('scrolling',C.c_uint8)]

def verify(capture,code,full_frame=False):
    raw=(capture/'play-task.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    stage_entries={}
    if full_frame:
        stage_raw=(capture/'stage-state.bin').read_bytes()
        assert len(stage_raw)%(stride*2)==0
        pending=None
        for off in range(0,len(stage_raw),stride*2):
            f,_,phase=struct.unpack_from('<IBB',stage_raw,off)
            if phase==6 and pending is None:pending=stage_raw[off+6:off+stride]
            if phase==4:
                stage_entries.setdefault(f,[]).append(pending or stage_raw[off+6:off+stride])
                pending=None
    program=code.read_bytes();signature=bytes.fromhex('bdcc2df0273a9dcc2dd02c');assert program.count(signature)==1
    shift=program.index(signature)+0x4000-0x9204
    custom={a+shift for a in (0x9204,0x9399,0x923e,0x9413,0x953a,0x998a,0x9ca8,0x9d22)}
    rom=(C.c_uint8*len(program)).from_buffer_copy(program)
    cells=(C.c_uint8*16384).from_buffer_copy(program[0xc000:])
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'runtime.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        *(str(ROOT/f'src/{name}.c') for name in ('bc_rules','bc_world','bc_stage','bc_runtime','bc_frame','bc_score','bc_player','bc_palette','bc_audio')),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));lib.bc_runtime_play.argtypes=[C.POINTER(Control),C.POINTER(Actor),
            C.POINTER(Stage),C.POINTER(StepData),C.c_uint16,C.c_uint8,C.c_uint8,
            C.POINTER(C.c_uint8),C.POINTER(RuntimeEvents)]
        lib.bc_runtime_play.restype=PlayResult
        lib.bc_runtime_frame.argtypes=[C.POINTER(FrameCursor),C.POINTER(Control),C.POINTER(Actor),C.POINTER(Stage),
            C.POINTER(Resources),C.POINTER(StepData),C.c_uint16,C.c_uint8,C.c_uint8,
            C.POINTER(C.c_uint8),C.POINTER(RuntimeEvents)]
        lib.bc_runtime_frame.restype=FrameResult
        combined_events=scroll_frames=audio_waits=0
        loops=checkpoints=segments=launches=scheduler_requests=0;p=None;pool=None;stage=None
        defeat=Sequence()
        def compare(r,f,task):
            expected=state(r)
            for field,_ in Control._fields_[1:]:
                assert getattr(p,field)==getattr(expected,field),(f,task,field,getattr(p,field),getattr(expected,field))
            for field in ('x','y','state','invulnerability'):
                assert getattr(p.world,field)==getattr(expected.world,field),(f,task,field,getattr(p.world,field),getattr(expected.world,field))
            assert bytes(p.world.inventory)==bytes(expected.world.inventory),(f,task,'inventory')
            w=p.world.weapons
            assert bytes(w.charge)==bytes(expected.world.weapons.charge),(f,task,'charge',bytes(w.charge),bytes(expected.world.weapons.charge))
            assert w.returning==r[0x5a] and bytes(w.option_shots)==r[0x5b:0x5d],(f,task,'weapon counters')
            assert bytes(w.trail)==r[0xb4:0xc4],(f,task,'trail')
            for i,s in enumerate(w.shots):
                want=decode(r,i);want.facing=(r[0xac] if s.kind==3 else r[0xdae+i])==0x52
                want.accelerating=r[0xcdc+i]*256+r[0xcfa+i] in custom
                fields=[name for name,_ in Beam._fields_] if s.body.state else ('state','x','y','delay')
                for field in fields:
                    assert getattr(s.body,field)==getattr(want,field),(f,task,i,field,getattr(s.body,field),getattr(want,field))
                if s.body.state and s.kind in (2,4):assert s.launch_wait==r[0xc28+i]
                if s.body.state and s.kind==4:assert s.tier==r[0xdea+i]
        for off in range(0,len(raw),stride*2):
            f,_,phase=struct.unpack_from('<IBB',raw,off);f2,end_slot,end=struct.unpack_from('<IBB',raw,off+stride)
            assert phase==0 and end in (1,2) and f2>=f
            r=raw[off+6:off+stride];after=raw[off+stride+6:off+stride*2]
            if full_frame:
                if stage_entries.get(f):r=stage_entries[f].pop(0);scroll_frames+=1
                else:assert r[0x48],(f,'missing scroll-task entry')
            assert not r[0x49],'Global debug invulnerability is outside native rules'
            expected_pool=(Actor*32)(*(actor(r,j,program) for j in range(32)))
            if not full_frame or p is None:
                pool=expected_pool
                stage=stage_state(r)
            else:
                for j in range(32):
                    for field,_ in Enemy._fields_:
                        assert getattr(pool[j].body,field)==getattr(expected_pool[j].body,field),(f,'carried actor',j,field)
                    for field,_ in Actor._fields_[1:]:
                        assert getattr(pool[j],field)==getattr(expected_pool[j],field),(f,'carried actor',j,field)
                for field,_ in Stage._fields_:
                    assert getattr(stage,field)==getattr(stage_state(r),field),(f,'carried stage',field)
            if p is None:
                assert not any(r[0xa48:0xa66]),'Initialize only at empty-pool checkpoint entry'
                p=state(r);segments+=1
            compare(r,f,'entry')
            count=C.c_uint8(r[0x59])
            def base(address):return int.from_bytes(r[address-0x2000:address-0x2000+2],'big')
            bullet_ref=int.from_bytes(program[0x4aaf+shift:0x4ab1+shift],'little')
            attrs=int.from_bytes(r[0x44:0x46],'little')-0x4000
            terrain=Terrain(cells,C.cast(C.byref(rom,attrs),C.POINTER(C.c_uint8)))
            seed=C.c_uint16(int.from_bytes(r[0x6c:0x6e],'little'))
            data=StepData(Data(rom,0x4000),base(bullet_ref),base(0x367c),base(0x367e),shift,r[0x4b],
                          terrain,int.from_bytes(r[0x2e:0x30],'big'),int.from_bytes(r[0x31:0x33],'big'),
                          base(0x367a),C.pointer(seed),base(0x3684),r[0x5e],base(0x36c8),base(0x3682),r[0x12])
            score=score_state(r);event_context=RuntimeEvents(C.pointer(score),r[0x51],0,None,None,C.cast(C.pointer(defeat),C.c_void_p))
            if full_frame:
                def template_base(address):
                    ref=int.from_bytes(program[address-0x4000+11:address-0x4000+13],'little')
                    return base(ref)
                palette=palette_state(r);audio=Audio()
                resources=Resources(Data(rom,0x4000),*(template_base(t) for t in (0xaca6,0xae54,0xb213,0xb31d)),
                    shift,r[0x4b],template_base(0xb0a5),template_base(0x8908+shift),C.pointer(score),r[0x51],
                    template_base(0xabb1),template_base(0xb4b0),C.pointer(palette),C.pointer(audio))
                cursor=FrameCursor()
                def run_frame():
                    return lib.bc_runtime_frame(C.byref(cursor),C.byref(p),pool,C.byref(stage),C.byref(resources),
                        C.byref(data),0x9c07+shift,r[0x228],r[0x22d],C.byref(count),C.byref(event_context))
                frame_result=run_frame()
                while frame_result.status==4:
                    combined_events+=frame_result.stage_events
                    assert audio.state==1
                    waiting=(bytes(stage),bytes(pool),bytes(p),bytes(score),seed.value,count.value)
                    retry=run_frame()
                    assert retry.status==4 and retry.stage_events==0
                    assert waiting==(bytes(stage),bytes(pool),bytes(p),bytes(score),seed.value,count.value)
                    lib.bc_audio_acknowledge(C.byref(audio));audio_waits+=1
                    frame_result=run_frame()
                assert frame_result.status<3,(f,'main frame stopped',frame_result.status,hex(frame_result.handler))
                combined_events+=frame_result.stage_events
                result=frame_result.play
                assert data.camera_x==stage.x>>8 and data.camera_y==stage.y>>8
                assert C.cast(data.terrain.attributes,C.c_void_p).value==C.addressof(rom)+stage.terrain_attributes-0x4000
                if not result.status:assert data.boss_active==stage.boss_active
                for field,_ in Stage._fields_:
                    assert getattr(stage,field)==getattr(stage_state(after),field),(f,'stage',field)
                assert palette.effect==after[0x5f],(f,'palette effect request')
            else:
                result=lib.bc_runtime_play(C.byref(p),pool,C.byref(stage),C.byref(data),0x9c07+shift,
                                          r[0x228],r[0x22d],C.byref(count),C.byref(event_context))
            assert result.status!=2,(f,'unsupported actor',result.next_slot,hex(pool[result.next_slot].routine))
            assert result.status==(1 if end==2 else 0),(f,'checkpoint status')
            compare(after,f,'exit')
            assert stage.boss_active==after[0x5e],(f,'boss countdown')
            if r[0xe08]==64 and r[0x1268]*256+r[0x1288]==0xb497:
                assert defeat.remaining==50 and defeat.wait==3
                assert defeat.center_y==int.from_bytes(after[0x60:0x62],'big')
                scheduler_requests+=1
            for j in range(32):
                want=actor(after,j,program)
                for field,_ in Enemy._fields_:
                    assert getattr(pool[j].body,field)==getattr(want.body,field),(f,j,'body',field,getattr(pool[j].body,field),getattr(want.body,field))
                for field,_ in Actor._fields_[1:]:
                    assert getattr(pool[j],field)==getattr(want,field),(f,j,field)
            assert count.value==after[0x59],(f,'count')
            assert seed.value==int.from_bytes(after[0x6c:0x6e],'little'),(f,'random seed')
            assert bytes(score)==bytes(score_state(after)),(f,'score queue/state')
            loops+=1;launches+=result.player_event.weapon.shots
            if result.status==1:p=None;checkpoints+=1
        if full_frame:
            # Contract regression: a stop followed by an audio wait must finish
            # this scroll task once on acknowledgement, then stay stopped.
            script=0x7f00
            rom[script-0x4000:script-0x4000+8]=bytes((0,0x17,0x8c,0,0x50,0x8c,255,255))
            held_stage=Stage();held_stage.script=script;held_stage.dx=85
            held_stage.terrain_attributes=stage.terrain_attributes
            held_player=Control();held_pool=(Actor*32)();held_count=C.c_uint8()
            cursor=FrameCursor();audio=Audio();resources.audio=C.pointer(audio)
            def resume():
                return lib.bc_runtime_frame(C.byref(cursor),C.byref(held_player),held_pool,C.byref(held_stage),
                    C.byref(resources),C.byref(data),0x9c07+shift,0,0,C.byref(held_count),None)
            stopped=resume()
            assert stopped.status==4 and stopped.stage_events==1 and held_stage.stopped==1
            assert held_stage.x==0 and held_stage.script==script+3 and cursor.scrolling==1
            snapshot=(bytes(held_stage),bytes(held_player),bytes(held_pool),bytes(cursor))
            assert resume().status==4
            assert snapshot==(bytes(held_stage),bytes(held_player),bytes(held_pool),bytes(cursor))
            lib.bc_audio_acknowledge(C.byref(audio))
            assert resume().status==0 and held_stage.x==85 and not cursor.scrolling
            assert resume().status==0 and held_stage.x==85
        return dict(module='native stage/scroll/player/enemy task' if full_frame else 'combined native player/weapons/enemy gameplay task',tasks=loops,
                    combined_stage_events=combined_events,scroll_frames=scroll_frames,test_audio_acknowledgements=audio_waits,
                    stage_and_actor_state_carried=full_frame,stop_audio_resume_verified=full_frame,
                    main_shots=launches,checkpoint_requests=checkpoints,boss_scheduler_requests=scheduler_requests,
                    source_initialized_life_segments=segments,unsupported_tasks=0,whole_game_verified=False)



if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);p.add_argument('--full-frame',action='store_true');a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code,a.full_frame),indent=2))
