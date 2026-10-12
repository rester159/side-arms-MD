#!/usr/bin/env python3
"""Validate current-ROM HuCard playback, launch and listening-report provenance."""
from pathlib import Path
import json,hashlib,argparse
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence',type=Path,default=root/'.local/hucard-final-current')
parser.add_argument('--review',type=Path,default=root/'.local/hucard-audio-review')
args=parser.parse_args();out=args.evidence
sha=hashlib.sha256((root/'out/release/rom.bin').read_bytes()).hexdigest();matrix=json.loads((out/'gameplay-matrix.json').read_text());assert matrix['passed']and matrix['source_rom_sha256']==sha
assert len(matrix['results'])==12
assert {(r['mode'],r['players'],r['pal'])for r in matrix['results']}=={(m,p,t)for m in ('normal','bc','rush')for p in (3,4)for t in (False,True)}
pal_rom=bytearray((root/'out/release/rom.bin').read_bytes());pal_rom[0x1f0:0x200]=b'E'+b' '*15
pal_sha=hashlib.sha256(pal_rom).hexdigest()
for r in matrix['results']:
 assert r['passed']and r['underruns']==0 and r['saved_music']and r['version4_migration']
 assert r['rom_sha256']==(pal_sha if r['pal'] else sha), 'stale gameplay evidence'
tracks=[]
for standard in ('ntsc','pal'):
 r=json.loads((out/standard/'result.json').read_text());assert r['passed']and r['source_rom_sha256']==sha and r['underruns']==0;assert r['stop_silent']and r['arcade_resumed']and r['back_to_options'];assert r['published_packet_checks']==420
 assert r['core_sha256']=='20903bdbe7dde068ebc55eabb00a2bf45238a254f24fbe2285d12389520dbba0'
 assert r['tested_rom_sha256']==(pal_sha if standard=='pal' else sha);assert r['published_packet_slots']==[0,1,2,3];assert [t['song']for t in r['tracks']]==list(range(21))
 tracks.append(dict(standard=standard,tracks=len(r['tracks']),packet_checks=r['published_packet_checks'],min_rms=min(t['rms']for t in r['tracks']),max_peak=max(t['peak']for t in r['tracks'])))
t=json.loads((out/'bc-transition-4p.json').read_text());assert t['passed']and t['rom_sha256']==sha and not t['injected_music_requests'];review=json.loads((args.review/'manifest.json').read_text());assert review['genesis_rom_sha256']==sha and len(review['tracks'])==21
r=dict(passed=True,rom_sha256=sha,track_outputs=tracks,gameplay_launch_cases=12,players=[3,4],modes=['normal','bc','rush'],standards=['NTSC','PAL'],underruns=0,save_and_v4_migration=True,autonomous_bc_stage_boss_transition=True,music_wait_max_frames=t['max_wait_frames'],listening_review=str((args.review/'index.html').resolve()),subjective_timbre_verified=False,scope='Bounded native playback, menu/save/pause and transition checks; not full-campaign coverage, subjective sound approval or console validation.')
(out/'summary.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
