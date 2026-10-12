#!/usr/bin/env python3
"""Compare source death poses with current cartridge-rendered player artwork."""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
out = ROOT/'.local/bc-player-death-fix'; out.mkdir(exist_ok=True)
records = json.loads((ROOT/'res/generated/bc_player_death_shapes.json').read_text())
report = json.loads((ROOT/'.local/bc-player-death-render/result.json').read_text())
assert report['rom_sha256'] == hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest()
sheet = Image.new('RGB', (430, len(records)*210), '#182230')
draw = ImageDraw.Draw(sheet)
sections = []
for i, rec in enumerate(records):
    source = Image.new('RGB', (32, 32))
    for y, row in enumerate(rec['rows']):
        for x, pen in enumerate(row):
            pen = int(pen, 16)
            if pen: source.putpixel((x,y), tuple(v*36 for v in rec['colors'][pen]))
    current = Image.open(ROOT/f'.local/bc-player-death-render/death-{i}.png').crop((56,96,88,128))
    source.save(out/f'source-{i}.png'); current.save(out/f'current-{i}.png')
    for column, image in enumerate((source, current)):
        sheet.paste(image.resize((192,192), Image.Resampling.NEAREST), (column*220,i*210+18))
    label = 'Genesis flash reuse' if rec['geometry_source']=='matching_normal_explosion' else 'PCE shape import'
    draw.text((4,i*210+2), f'PCE {rec["source_pose"]:04X} | {label}', fill='white')
    sections.append(f'<section><h2>Phase {i+1}: {label}</h2><figure><img src="source-{i}.png" alt="PCE source"><figcaption>PCE BC</figcaption></figure><figure><img src="current-{i}.png" alt="Current cartridge"><figcaption>Current cartridge</figcaption></figure></section>')
sheet.save(out/'comparison.png')
(out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>BC player death sequence</title>
<style>body{font:18px system-ui;background:#182230;color:white;max-width:900px;margin:32px auto}img{width:192px;image-rendering:pixelated}figure{display:inline-block;margin:16px}section{border-top:1px solid #657}p{line-height:1.5}</style>
<h1>Corrected BC player death sequence</h1><p>The matching Genesis flash is reused. The other four phases use PCE geometry fitted to existing Genesis palette shades. Timing is unchanged; colors are approximations.</p>'''+''.join(sections)+f'<p>Verified ROM: {report["rom_sha256"]}</p>')
print(out/'index.html')
