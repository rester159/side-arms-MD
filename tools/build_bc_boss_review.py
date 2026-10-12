#!/usr/bin/env python3
"""Refresh the original-PCE boss body comparison from verified source captures."""
import hashlib,json
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'.local/bc-composite-review';out.mkdir(exist_ok=True)
source=json.loads((ROOT/'tools/data/bc_composite_source_shapes.json').read_text())['bosses']
qa=json.loads((ROOT/'.local/bc-all-original-bosses/bodies.json').read_text())
rom_sha=hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest()
for report in (qa,
 json.loads((ROOT/'.local/bc-original-boss-shots/result.json').read_text()),
 json.loads((ROOT/'.local/bc-serpent-render/result.json').read_text())):
 assert report['passed'] and report['rom_sha256']==rom_sha, 'Re-run boss body, shot and serpent checks against the current ROM before refreshing this review.'
assert len(qa['bosses'])==9 and qa['composite_attack_poses_verified']==4
sections=[]
for b in source:
 n=b['round'];p=ROOT/'.local/pce-reference'/b['capture']/'snap'/f'f{b["capture_frame"]:06d}.png'
 Image.open(p).convert('RGB').resize((264,224),Image.Resampling.NEAREST).save(out/f'round-{n}-pce.png')
 Image.open(ROOT/f'.local/bc-all-original-bosses/boss-{n}-source-round-{n}.png').save(out/f'round-{n}-current.png')
 sections.append(f'''<section id="round-{n}"><h2>Boss {n}: original PCE body imported</h2><div class="grid"><figure><img width="264" height="224" src="round-{n}-pce.png" alt="PCE source boss {n}"><figcaption>Original PCE capture</figcaption></figure><figure><img width="320" height="224" src="round-{n}-current.png" alt="Imported boss {n} in Genesis"><figcaption>Genesis renderer, captured actor positions</figcaption></figure></div></section>''')
attacks=json.loads((ROOT/'tools/data/bc_boss_attack_shapes.json').read_text())['attacks']
for a in attacks:
 p=a['pose'];n=a['round'];frame=p['frame'];original=Image.new('RGB',(320,224))
 for piece in p['pieces']:
  for y,row in enumerate(piece['rows']):
   for x,pen in enumerate(row):
    pen=int(pen,16)
    if pen:original.putpixel((184+piece['x']+x,112+piece['y']+y),tuple(v*36 for v in p['colors'][pen]))
 stem=f'attack-{n}-{frame:04x}'
 original.crop((128,88,240,136)).save(out/f'{stem}-pce.png')
 Image.open(ROOT/f'.local/bc-all-original-bosses/{stem}.png').crop((128,88,240,136)).save(out/f'{stem}-genesis.png')
 sections.append(f'<section><h2>Boss {n} attack {frame:04X}: imported</h2><div class="grid"><figure><img width="336" height="144" src="{stem}-pce.png" alt="Original PCE attack pattern"><figcaption>Extracted original PCE pattern</figcaption></figure><figure><img width="336" height="144" src="{stem}-genesis.png" alt="Imported attack in Genesis"><figcaption>Genesis renderer</figcaption></figure></div></section>')
shots=json.loads((ROOT/'res/generated/bc_boss_shots.json').read_text())
for shot in shots:
 original=Image.new('RGB',(16,16))
 for y,row in enumerate(shot['rows']):
  for x,pen in enumerate(row):
   pen=int(pen,16)
   if pen:original.putpixel((x,y),tuple(v*36 for v in shot['colors'][pen]))
 stem=shot['id'];original.save(out/f'{stem}-pce.png')
 Image.open(ROOT/f'.local/bc-original-boss-shots/{stem}.png').crop((152,104,168,120)).save(out/f'{stem}-genesis.png')
 sections.append(f'<section><h2>Boss {shot["round"]} shot {shot["frame"]:02X}: imported</h2><div class="grid"><figure><img width="128" height="128" src="{stem}-pce.png" alt="Original PCE shot"><figcaption>PCE pattern</figcaption></figure><figure><img width="128" height="128" src="{stem}-genesis.png" alt="Original shot in Genesis"><figcaption>Genesis renderer</figcaption></figure></div></section>')
serpent=json.loads((ROOT/'res/generated/bc_serpent_shapes.json').read_text())
for shape in serpent:
 original=Image.new('RGB',(32,32))
 for y,row in enumerate(shape['rows']):
  for x,pen in enumerate(row):
   pen=int(pen,16)
   if pen:original.putpixel((x,y),tuple(v*36 for v in shape['colors'][pen]))
 stem=shape['id'];original.save(out/f'{stem}-pce.png')
 Image.open(ROOT/f'.local/bc-serpent-render/{stem}.png').crop((144,96,176,128)).save(out/f'{stem}-genesis.png')
 part={0x36d0:'head',0x36d2:'body',0x36d4:'tail'}[shape['family']]
 sections.append(f'<section><h2>Final serpent {part}: pose {shape["frame"]:02X}, palette {shape["source_palette"]}</h2><div class="grid"><figure><img width="192" height="192" src="{stem}-pce.png" alt="Original PCE serpent"><figcaption>PCE pattern</figcaption></figure><figure><img width="192" height="192" src="{stem}-genesis.png" alt="Imported serpent in Genesis"><figcaption>Genesis renderer</figcaption></figure></div></section>')
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Original PCE bosses in BC</title><style>body{font:18px system-ui;background:#182230;color:#eee;max-width:1100px;margin:32px auto;padding:16px}p{line-height:1.6}.grid{display:flex;gap:24px;flex-wrap:wrap}figure{margin:0}img{image-rendering:pixelated}section{border-top:1px solid #546170;margin-top:32px;padding-top:12px}a{color:#9df}.notice{background:#34303d;padding:16px}</style><h1>Original PCE bosses, attacks and final serpent</h1><p class="notice">The Genesis boss substitutions have been replaced with the original PCE body geometry. The composite laser and beam poses are imported too. The dedicated round-one radial and round-six rain shots are imported. The eleven shared-projectile variants use original PCE geometry during boss fights, including the final serpent encounter. The serpent’s head, body and tail use twenty original PCE poses, including both head palettes. Captured attack shapes and encounter transitions are verified; this does not claim the full expansion runs at the target frame rate.</p><p>Every source body pixel, opaque outline and articulated part position is retained. Colors are fitted to the shared Genesis sprite palettes with distinct ordered shade levels; some hues differ from PCE. Screenshots on the right use the captured actor positions in a blank preview scene, without source backgrounds, attacks or HUD. Some parts are clipped at the original scene edge.</p>'''+''.join(sections)+f'''<p>Verified ROM: <code>{qa['rom_sha256']}</code></p><p><a href="../bc-asset-review/index.html">Sprite and background review</a></p></html>'''
(out/'index.html').write_text(page)
print('Original PCE comparison: nine composite bosses, four composite attacks, fifteen projectile variants and twenty final-serpent poses')
