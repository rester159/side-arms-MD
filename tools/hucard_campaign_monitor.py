"""Read-only BC music observation around every actual emulator video frame."""
import ctypes as C
import json
import numpy as np

TRACKS = dict(zip(range(0x21, 0x2a), (5,4,2,3,1,6,7,8,14)))
TRACKS.update({0x32:18,0x33:14,0x34:12,0x35:13,0x36:16,0x2a:10,0x2c:15,0xfe:15})

class CampaignMusicMonitor:
    def __init__(self, runner):
        self.r = runner
        self.zram = (C.c_uint8 * 8192).in_dll(runner.lib, 'zram')
        self.chunks = []
        self.rows = []
        self.requests = []
        self.last = None
        self.last_request = None
        self.window = 0
        # Read-only renderer diagnostics accompany the audio campaign. These
        # count software submission failures, not hardware scanline overflow.
        self.render_start = {name: runner.u32(name) for name in
                             ('spr_dbg_dropped', 'spr_dbg_remap')}
        self.render_last = dict(self.render_start)
        self.render_events = []
        self.maximum_unmapped = 0
        self.callback = C.CFUNCTYPE(C.c_size_t,C.POINTER(C.c_int16),C.c_size_t)(self.audio)
        runner.callbacks.append(self.callback)
        runner.lib.retro_set_audio_sample_batch(self.callback)
        previous_run = runner.run
        def run(frames, mask=0):
            for _ in range(frames):
                previous_run(1, mask)
                self.observe()
        runner.run = run

    def audio(self, data, count):
        if self.window < 120:
            self.chunks.append(np.ctypeslib.as_array(data,(count*2,)).copy())
        return count

    def observe(self):
        r = self.r
        assert not self.zram[0x1b0a], ('HuCard underrun', r.frames)
        request = (r.u16('dbg_bc_native_current_round'),
                   r.u16('dbg_bc_native_music_requests'),r.u16('dbg_bc_native_music_command'))
        self.maximum_unmapped = max(self.maximum_unmapped,
            r.u16('dbg_bc_native_actor_unmapped') + r.u16('dbg_bc_native_unmapped'))
        for name in self.render_last:
            value = r.u32(name)
            if value != self.render_last[name]:
                if len(self.render_events) < 64:
                    self.render_events.append(dict(counter=name, frame=r.frames,
                        round=request[0]+1, before=self.render_last[name], after=value))
                self.render_last[name] = value
        if request != self.last_request and request[1] and request[2] in TRACKS:
            assert r.u16('dbg_hucard_track') == TRACKS[request[2]], ('wrong track',request)
            self.requests.append(dict(round=request[0]+1,request=request[1],command=request[2],
                                      track=r.u16('dbg_hucard_track'),frame=r.frames))
        self.last_request = request
        key = (r.u16('dbg_hucard_starts'),r.u16('dbg_hucard_track'),r.read('hucard_active',1)[0])
        if key != self.last:
            self.last = key
            self.window = 0
            self.chunks.clear()
            self.rows.append(dict(starts=key[0],track=key[1],active=key[2],frame=r.frames,
                                  round=request[0]+1))
        self.window += 1
        if self.window == 120 and key[2]:
            samples = np.concatenate(self.chunks).astype(float)
            rms = float(np.sqrt(np.mean(samples**2)))
            assert rms > 5, ('silent campaign track',key,r.frames)
            self.rows[-1]['rms'] = rms
            self.chunks.clear()

    def finish(self, output, complete):
        audible = {row['track'] for row in self.rows if row.get('rms',0)>5}
        commands = {row['command'] for row in self.requests}
        if complete:
            assert not self.r.read('hucard_active',1)[0], 'BC playback survived session exit'
            expected = set(range(0x21,0x2a)) | {0x32,0x36,0x2a,0x2c,0xfe}
            assert expected <= commands, ('missing source music requests',expected-commands)
            assert {TRACKS[command] for command in expected} <= audible, ('missing audible tracks',audible)
            requested = {(row['round'],row['command']) for row in self.requests}
            stage_requests = {(number,0x20+number) for number in range(1,10)} | {(10,0x36)}
            assert stage_requests <= requested, ('missing round music',stage_requests-requested)
            stage_audio = {(row['round'],row['track']) for row in self.rows if row.get('rms',0)>5}
            assert {(number,TRACKS[command]) for number,command in stage_requests} <= stage_audio
        report = dict(passed=True,complete_campaign=bool(complete),underruns=0,
                      audible_tracks=sorted(audible),requests=self.requests,playbacks=self.rows)
        report['renderer_diagnostics'] = dict(
            scope='Software submission counters and unmapped art; not hardware scanline overflow',
            counter_deltas={name: (self.render_last[name]-start) & 0xffffffff
                            for name,start in self.render_start.items()},
            maximum_unmapped=self.maximum_unmapped, first_counter_changes=self.render_events)
        (output/'hucard-audio.json').write_text(json.dumps(report,indent=2)+'\n')
        return report
