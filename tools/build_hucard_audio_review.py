#!/usr/bin/env python3
"""Build a local source/current-ROM listening comparison with recorded provenance."""
import hashlib
import argparse
import html
import json
import re
import wave
from pathlib import Path
import numpy as np
from inspect_hucard_music import ROOT,metadata

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--capture',type=Path,default=ROOT/'.local/pce-hucard/audition-genesis-v1')
parser.add_argument('--output',type=Path,default=ROOT/'.local/hucard-audio-review')
args=parser.parse_args()
out=args.output;out.mkdir(parents=True,exist_ok=True)
source=json.loads((ROOT/'.local/pce-hucard/audio-captures.json').read_text())
capture=args.capture
current=json.loads((capture/'result.json').read_text())
rom_sha=hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest()
assert current['passed'] and current['source_rom_sha256']==rom_sha
meta=metadata((ROOT/'.local/pce-hucard/SideArms - Hyper Dyne (USA).pce').read_bytes())
assert source['source_sha256']==meta['source_sha256']
refs={r['command']:r for r in source['captures']}
names=re.findall(r'"([^"]+)"',(ROOT/'src/flow_menu.c').read_text().split('HUCARD_NAMES[21] = {')[1].split('};')[0])
assert len(names)==len(current['tracks'])==21

def read_audio(path):
    with wave.open(str(path)) as wav:
        assert wav.getnchannels()==2 and wav.getsampwidth()==2
        return wav.getframerate(),np.frombuffer(wav.readframes(wav.getnframes()),'<i2').reshape(-1,2)

def export(stem,rate,samples):
    peak=int(np.max(np.abs(samples.astype(np.int32))))
    rms=float(np.sqrt(np.mean(samples.astype(float)**2)))
    assert peak>0 and rms>0
    gain=min(32767*10**(-20/20)/rms,32767*10**(-1/20)/peak)
    files={}
    for suffix,values in [('original',samples),('matched',np.rint(samples.astype(float)*gain).astype('<i2'))]:
        filename=f'{stem}-{suffix}.wav'
        with wave.open(str(out/filename),'wb') as wav:
            wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(rate)
            wav.writeframes(values.astype('<i2').tobytes())
        files[suffix]=filename
    return dict(**files,sample_rate=rate,seconds=len(samples)/rate,rms=rms,peak=peak,
                matched_gain_db=float(20*np.log10(gain)))

rows=[];sections=[]
for track in current['tracks']:
    command=track['song'];definition=meta['music'][command]
    reference=refs[definition.get('alias_of',command)]
    path=ROOT/reference['capture']/'source.wav'
    assert hashlib.sha256(path.read_bytes()).hexdigest()==reference['audio_sha256']
    rate,pcm=read_audio(path)
    # The cartridge capture begins six video frames after pressing Play.
    # This aligns requests approximately, not individual synthesis phases.
    start=round((reference['command_time']+6/current['fps'])*rate)
    gen_rate,gen=read_audio(capture/track['audio_file'])
    frames=round(len(gen)/gen_rate*rate);assert start+frames<=len(pcm)
    pce=export(f'{command:02x}-pce',rate,pcm[start:start+frames])
    genesis=export(f'{command:02x}-genesis',gen_rate,gen)
    rows.append(dict(command=command,name=names[command],reference_command=reference['command'],pce=pce,genesis=genesis))
    cells=[]
    for side,label,data in [('pce','Original PCE HuCard',pce),('genesis','Current Genesis ROM',genesis)]:
        cells.append(f'<div><h3>{label}</h3><audio controls preload="none" data-side="{side}" data-original="{data["original"]}" data-matched="{data["matched"]}" src="{data["matched"]}"></audio><button data-side="{side}">Switch to {label}</button></div>')
    sections.append(f'<section><h2>{html.escape(names[command])}</h2><div class="pair">'+''.join(cells)+'</div></section>')

page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HuCard soundtrack comparison</title>
<style>body{font:18px system-ui;background:#17212d;color:#edf4fa;max-width:1000px;margin:32px auto;padding:16px}p{line-height:1.5}.pair{display:flex;gap:32px;flex-wrap:wrap}section{border-top:1px solid #526477;margin-top:28px}h3{font-size:17px}audio{display:block;width:320px;max-width:100%}button{font:inherit;margin:12px 0;padding:8px 12px;cursor:pointer}a{color:#a9d9ff}.controls{position:sticky;top:0;background:#17212d;padding:12px 0;border-bottom:1px solid #526477}</style>
<h1>HuCard soundtrack comparison</h1><p>Original PCE PSG audio beside the current Genesis FM conversion. All 21 menu selections are included; selections 08, 13 and 14 share the Stage 2 source score. Clips cover approximately the first ten seconds after playback begins. Short jingles may finish before the clip ends.</p>
<p>Use either player's controls, or switch sides at the current playback position. Starts are approximately aligned by playback requests, not by waveform phase. Level matching changes only a constant gain; no compression or EQ is applied. This page supports listening review and does not claim identical instrument sound.</p>
<div class="controls"><label><input id="matched" type="checkbox" checked> Level-match clips for comparison</label></div>'''+''.join(sections)+f'<p>Genesis ROM: <code>{rom_sha}</code><br>PCE HuCard: <code>{source["source_sha256"]}</code></p><p>PCE recordings use the original emulated sound driver with requested music commands. Genesis recordings come from the actual cartridge Sound Test.</p><p><a href="manifest.json">Capture details</a> · <a href="../bc-asset-review/index.html">Artwork review</a></p>'+'''
<script>
const clips=[...document.querySelectorAll('audio')];
for(const clip of clips)clip.addEventListener('play',()=>{clip.closest('section').dataset.active=clip.dataset.side;clips.forEach(other=>{if(other!==clip)other.pause()})});
document.querySelector('#matched').addEventListener('change',event=>{
  for(const clip of clips){const time=clip.currentTime,playing=!clip.paused;clip.pause();clip.src=clip.dataset[event.target.checked?'matched':'original'];clip.addEventListener('loadedmetadata',()=>{clip.currentTime=Math.min(time,clip.duration);if(playing)clip.play().catch(()=>{})},{once:true});clip.load()}
});
for(const button of document.querySelectorAll('button'))button.addEventListener('click',()=>{
  const pair=[...button.closest('section').querySelectorAll('audio')],target=pair.find(a=>a.dataset.side===button.dataset.side),other=pair.find(a=>a!==target);
  const active=pair.find(a=>a.dataset.side===button.closest('section').dataset.active);
  const time=active?active.currentTime:0;other.pause();
  const start=()=>{target.currentTime=Math.min(time,Math.max(0,target.duration-.01));target.play().catch(()=>{})};
  if(target.readyState>=1)start();else{target.addEventListener('loadedmetadata',start,{once:true});target.load()}
});
</script></html>'''
(out/'index.html').write_text(page)
(out/'manifest.json').write_text(json.dumps(dict(source_rom_sha256=source['source_sha256'],genesis_rom_sha256=rom_sha,
  source_fixture='Original HuCard driver; injected music command',genesis_fixture='Sound Test controller input',
  alignment='Approximate playback requests; not sample/phase alignment',level_matching='Constant gain to -20 dBFS RMS, limited to -1 dBFS peak',tracks=rows),indent=2)+'\n')
print(out/'index.html')
