#!/usr/bin/env python3
"""Compare state, post-flush VDP data and late-blank safety in two captured runs."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);a=p.parse_args()
x=json.loads(a.baseline.read_text());y=json.loads(a.candidate.read_text())
assert x.get('music_source','arcade')==y.get('music_source','arcade'), 'soundtrack mismatch'
for key in ('round','players','protected','charged_fire','simulation_updates'):assert x[key]==y[key],key
assert len(x['rows'])==len(y['rows'])
for old,new in zip(x['rows'],y['rows']):
    for key in ('tick','simulation_updates','simulation_sha256','workload'):assert old[key]==new[key],(old['tick'],key)
old={r['tick']:r for r in x['scheduler']['rows']};new={r['tick']:r for r in y['scheduler']['rows']}
assert len(old)==len(x['scheduler']['rows']) and len(new)==len(y['scheduler']['rows'])
assert old.keys()==new.keys()
for tick in old:assert old[tick]['video_sha256']==new[tick]['video_sha256'],('video',tick)
late=[r for r in new.values() if r['scene_start_vtimer'] is not None and r['vtimer']!=r['scene_start_vtimer'] and r['scanline']>=224 and r.get('video_end_vtimer',r['end_vtimer'])==r['vtimer']]
# New captures delimit video work before controller polling. Older captures
# retain the conservative whole-call boundary; never assume missing evidence.
for row in late:assert 224<=row.get('video_end_scanline',row['end_scanline'])<262,('late video work entered active display',row)
assert y['elapsed_video_frames']<=x['elapsed_video_frames'],('frame count regression',x['elapsed_video_frames'],y['elapsed_video_frames'])
print(json.dumps(dict(players=y['players'],updates=y['simulation_updates'],before_frames=x['elapsed_video_frames'],after_frames=y['elapsed_video_frames'],matching_state_frames=len(x['rows']),matching_video_frames=len(old),late_flushes=len(late),latest_flush_scanline=max((r.get('video_end_scanline',r['end_scanline']) for r in late),default=None),video_completion_boundary='before controller polling' if all('video_end_scanline' in r for r in late) else 'whole-call fallback',candidate_rom=y['rom_sha256']),indent=2))
