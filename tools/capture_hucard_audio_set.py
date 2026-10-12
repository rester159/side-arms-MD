#!/usr/bin/env python3
"""Capture audible PCE references for every distinct HuCard music command."""
import concurrent.futures
import csv
import hashlib
import json
import subprocess
import sys
import wave
from inspect_hucard_music import ROOT,metadata

rom=ROOT/'.local/pce-hucard/SideArms - Hyper Dyne (USA).pce'
meta=metadata(rom.read_bytes())
tracks=[r for r in meta['music'] if 'alias_of' not in r]
def capture(track):
    command=track['command'];name=f'audition-{command:02x}-v1'
    folder=ROOT/'.local/pce-hucard'/name
    if not folder.exists():
        subprocess.run([sys.executable,str(ROOT/'tools/capture_pce_hucard.py'),name,
                        '--command',str(command),'--frames','900','--audio'],check=True)
    assert (folder/'complete.txt').read_text().strip()=='900'
    commands=list(csv.DictReader((folder/'commands.csv').open()))
    start=next(float(r['time']) for r in commands
               if r['fixture']=='1' and int(r['command'],16)==command)
    audio=folder/'source.wav'
    with wave.open(str(audio)) as wav:
        assert wav.getnchannels()==2 and wav.getsampwidth()==2
        rate=wav.getframerate();duration=wav.getnframes()/rate
        assert duration-start>12
    return dict(command=command,capture=str(folder.relative_to(ROOT)),
                command_time=start,sample_rate=rate,duration=duration,
                audio_sha256=hashlib.sha256(audio.read_bytes()).hexdigest())

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    results=list(pool.map(capture,tracks))
manifest=dict(source_sha256=meta['source_sha256'],captures=results,
              scope='Original emulated PSG audio; development fixture requests each music command')
(ROOT/'.local/pce-hucard/audio-captures.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(f'Complete: {len(results)} distinct original PSG recordings')
