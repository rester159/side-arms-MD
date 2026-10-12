"""Package this local candidate only after six current-ROM progression checks."""
from pathlib import Path
import argparse,hashlib,json,zipfile
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence',type=Path,required=True)
parser.add_argument('--output',type=Path)
parser.add_argument('--art-evidence',type=Path,help='Optional current-ROM art regression summary to include')
parser.add_argument('--sprite-evidence',type=Path,help='Optional current-ROM sprite geometry/rendering summary to include')
parser.add_argument('--performance-evidence',type=Path,help='Optional current-ROM matched-state performance comparison')
parser.add_argument('--audio-evidence',type=Path,help='Optional current-ROM instrument and delivery verification')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
evidence=args.evidence.resolve()
rom=(root/'out/release/rom.bin').read_bytes()
assert len(rom)==4194304, 'Expected finalized 4 MiB cartridge'
digest=hashlib.sha256(rom).hexdigest()
rows=[]
for players in (3,4):
 for mode in ('bc','normal','rush'):
  d=json.loads((evidence/f'{mode}-{players}p/result.json').read_text());assert d['rom_sha256']==digest and d['players']==players
  if mode=='bc':
   assert d['reason']=='final_clear' and d['ending']['home_returned']
   assert d['ending']['credit_updates']==5760 and d['ending']['gameplay_ticks_frozen']
   assert not any(d[k]for k in ('forced_boss_defeats','forced_player_deaths','seeded_health_or_weapons'))
   h=d['hucard_audio'];assert h['passed'] and h['complete_campaign'] and h['underruns']==0
   render=h['renderer_diagnostics'];assert render['maximum_unmapped']==0 and not any(render['counter_deltas'].values())
   row=dict(mode=mode,players=players,frames=d['frames'],ticks=d['ticks'],rounds=10,credit_updates=5760,home_returned=True,underruns=0,software_sprite_drops=0,unmapped_art=0,protection=True,assisted_boss_hits=False)
  else:
   assert d['passed'] and d['underruns']==0 and d['assisted_hit_tests']
   row=dict(mode=mode,players=players,underruns=0,protection=True,assisted_boss_hits=True)
   if mode=='normal':
    assert len(d['sections'])==10 and not d['injected_stage_warps'] and not d['injected_completion_events']
    row.update(video_frames=d['video_frames'],sections=10)
   else:
    assert len(d['encounters'])==12 and d['last_player_exit']
    row['encounters']=12
  rows.append(row)
core_hash=hashlib.sha256((root/'.local/test-core/genesis_plus_gx_libretro.dylib').read_bytes()).hexdigest()
assert core_hash=='20903bdbe7dde068ebc55eabb00a2bf45238a254f24fbe2285d12389520dbba0'
summary=dict(passed=True,rom_sha256=digest,core_sha256=core_hash,results=rows,scope='Protected continuous 3P/4P progression and HuCard music. BC uses controller aiming; Normal/Rush use assisted hit paths. Not unassisted combat, full-speed or physical-console certification.')
(evidence/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
notes='''Side Arms MD expansion — local test build (2026-10-09)

Contains Normal, Before Christ and Boss Rush with 1–4-player Home sessions,
the PC Engine HuCard music option, original BC bosses/attacks and the latest
shade-preserving artwork corrections, including exact Round 7 source colors,
restored Normal machinery/scenery and opening-city shades, source-exact Earth/flash colors,
recovered burning-frame highlights and the HuCard packet-copy optimization.
The duplicate unused Earth world bank is omitted; the intro scene art remains
intact.
Stage-four scenery also restores 40 source-color distinctions without new
source-color pair merges. That palette fit has a small color-accuracy cost:
mean squared RGB3 channel error rises from 0.1470 to 0.1566. Its protected
3P/4P controls match the preceding build's state, rendering workload and timing.
Stage-nine scenery restores another 40 source-color distinctions with no new
source-pair merges, while improving color accuracy and restoring 549 exact
source-color pixels. Its protected 3P/4P state, rendering and timing also match.
Stage-three cave art recovers another 74 exact source highlight pixels using
existing palettes, with no merged Standard/Vivid shades or changed BC art.
Normal sprite shade recovery restores 6,014 stored pixels across 296 pattern
blocks (300 lookup keys), using existing spare palette pens and no added pattern
storage. Existing Standard/Vivid distinctions and protected BC patterns remain
intact. Native 3P/4P gallery CRAM matches the archived colors in Vivid mode;
Normal and BC bounded gameplay/timing comparisons match the preceding build.
These are stored-pattern counts, not a claim that all sprite shading is finished.
Selective Normal background repacking restores another 3,869 stored pixels
to exact source colors across five palette zones. Home cutout variants keep
every displayed pixel; geometry, transparency, star colors and existing
Standard/Vivid shade distinctions are preserved. That shading-only revision preserved runtime code, audio, BC artwork and
Vivid lookup data. Later performance revisions are covered separately by the
current-ROM acceptance and performance evidence.
BC idle spike turrets now use narrower sprite pieces where spare hardware
sprite entries and cache space are available. Original sprites remain intact
when resources are full. In the measured four-player Round 7 route, sprite-width
over-limit line observations fall by 31%, with identical ideal sprite artwork;
mean scene processing cost rises 2.3%. The crowded reference snapshot recovers
201 of 643 missing sprite-plane pixels. Hardware sprite crowding is reduced,
not eliminated; these counts are before background/window composition.
The first BC surfacer pose also omits its fully transparent outer rows,
using one 32x16 sprite with identical pixels and half the pattern upload bytes.
Against the preceding turret-strip build, the measured four-player Round 7
route reduces entry-over-limit line observations from 60 to 13 and width-over-
limit observations from 27,735 to 25,081. Mean scene CPU cost rises about 0.5%;
all 4,000 compared simulation states and ideal sprite images remain identical.
A reviewed BC pod pose now also omits its fully transparent final tile row,
using one 32x24 sprite. Crop selection is cached with the animation pose.
Against the preceding surfacer-crop build, the measured Round 7 route reduces
entry-over-limit line observations from 13 to 9 and width-over-limit observations
from 25,081 to 24,313. Mean scene CPU cost rises about 0.18%; all 4,000 compared
simulation states and ideal sprite images remain identical. The Round 8 control
keeps its 1,013-frame count. Crowding is still present.
The HuCard ending instrument now uses a fitted FM patch, reducing measured
harmonic-magnitude error by 72.2% while preserving source loudness within
0.227 dB at the tested levels. Long ending playback and 3P/4P ending flow pass
with zero underruns; listening and harmonic-phase fidelity remain unverified.

Start: choose HOME, then a mode and 1/2/3/4 players.
Music: HOME > OPTIONS > MUSIC > PC ENGINE. Saved in SRAM.
Default controls: A fire left, B fire right, C next weapon, Start pause/start.
Menus: B back. A+B+C+Start returns to the boot screen.
Controller options and remapping are in HOME > OPTIONS > CONTROLS.

Team Player port 1: adapter A/B/C/D are P1/P2/P3/P4.
Team Player port 2: ordinary port-1 pad is P1; adapter A/B/C are P2/P3/P4.
EA 4-Way Play: four pads in order. Connect the adapter before boot.

Current-ROM checks: all six protected 3P/4P progression runs pass for Normal,
BC and Boss Rush, with zero HuCard underruns. BC includes the ending and Home
return without forced boss defeats. Normal/Rush use assisted hit paths.
Full results and test scope are in acceptance.json.

Known limits: heavy 3P/4P scenes slow down; full-speed acceptance is unfinished.
Validation is emulator-only, as requested; physical-console certification is not claimed.
HuCard timbre polish and
remaining visual review are still open. Normal retains its existing star/cave
parallax; broader tiled-background parallax is not included. Experimental
Round 8 mask prototypes are excluded. The Earth palette switches add a small
intro-only delay (one Standard / ten Vivid frames in the recorded fixture);
gameplay frame counts were unchanged in the bounded regression samples.
This is not the final release.
'''
name=f'Side-Arms-MD-expansion-{digest[:8]}.bin';files={name:rom,'README.txt':notes.encode(),'acceptance.json':(json.dumps(summary,indent=2)+'\n').encode()}
if args.art_evidence:
 art=json.loads(args.art_evidence.read_text())
 assert art['passed'] and art['rom_sha256']==digest, 'Art evidence must identify this cartridge'
 files['art-checks.json']=(json.dumps(art,indent=2)+'\n').encode()
 files['README.txt']+=b'\nCurrent-ROM pixel/shading regression scope is recorded in art-checks.json.\n'
if args.audio_evidence:
 audio=json.loads(args.audio_evidence.read_text())
 assert audio['passed'] and audio['rom_sha256']==digest, 'Audio evidence must identify this cartridge'
 files['audio-checks.json']=(json.dumps(audio,indent=2)+'\n').encode()
 files['README.txt']+=b'\nInstrument 2 uses a fitted FM feedback patch; measured harmonic error is reduced\nby about 79%, with loudness within 0.44 dB at the tested levels. Production\nchip-register delivery and NTSC/PAL output checks pass. Phase and subjective\ntimbre fidelity are not claimed. See audio-checks.json for scope and evidence.\n'
if args.sprite_evidence:
 sprite=json.loads(args.sprite_evidence.read_text())
 assert sprite['passed'] and sprite['rom_sha256']==digest, 'Sprite evidence must identify this cartridge'
 files['sprite-checks.json']=(json.dumps(sprite,indent=2)+'\n').encode()
 files['README.txt']+=b'\nCurrent-ROM sprite geometry and bounded rendering checks are in sprite-checks.json.\n'
if args.performance_evidence:
 performance=json.loads(args.performance_evidence.read_text())
 assert performance['passed'] and performance['rom_sha256']==digest, 'Performance evidence must identify this cartridge'
 files['performance-checks.json']=(json.dumps(performance,indent=2)+'\n').encode()
 if performance.get('bc') and performance.get('normal'):
  lines=['\nCurrent candidate versus the retained comparison build:']
  for row in performance['bc']:
   lines.append(f"BC R{row['round']} {row['players']}P: mean scene CPU reduction {row['reduction_percent']:.3f}%; video frames {row['before_frames']} -> {row['after_frames']} for the same measured updates.")
  for row in performance['normal']:
   lines.append(f"Normal section {row['section']} 4P: mean update CPU reduction {row['reduction_percent']:.3f}%; video frames {row['before_frames']} -> {row['after_frames']}.")
  lines.append('Negative reductions are regressions. Results cover the recorded routes only; crowded scenes still slow down.')
  files['README.txt']+=('\n'.join(lines)+'\n').encode()

 files['README.txt']+=b'\nMatched-state performance comparisons for this ROM are in performance-checks.json.\nThese bounded routes do not establish full-speed campaign performance.\n'
files['SHA256SUMS']=(''.join(hashlib.sha256(v).hexdigest()+'  '+k+'\n'for k,v in sorted(files.items()))).encode()
out=root/'.local/candidates';out.mkdir(exist_ok=True);target=args.output or out/f'Side-Arms-MD-expansion-{digest[:8]}-test.zip'
target.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9)as z:
 for name,data in sorted(files.items()):
  info=zipfile.ZipInfo(name,date_time=(2026,10,9,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16;z.writestr(info,data)
with zipfile.ZipFile(target)as z:
 assert z.testzip()is None
 for name,data in files.items():assert z.read(name)==data
(evidence/'package.json').write_text(json.dumps(dict(path=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),rom_sha256=digest,final_release=False),indent=2)+'\n')
print(target)
