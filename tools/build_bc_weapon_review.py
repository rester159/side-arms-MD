#!/usr/bin/env python3
"""Show imported player weapon shapes beside current cartridge captures."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'.local/bc-weapon-shapes-review';out.mkdir(exist_ok=True)
records=json.loads((ROOT/'res/generated/bc_player_projectile_shapes.json').read_text())
qa=json.loads((ROOT/'.local/bc-player-projectile-render/result.json').read_text())
assert qa['rom_sha256']==hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest()
sections=[]
sheet=Image.new('RGB',(600,((len(records)+1)//2)*166),'#182230');draw=ImageDraw.Draw(sheet)
for i,r in enumerate(sorted(records,key=lambda r:r['source_pose'])):
 pose=r['source_pose'];source=Image.new('RGB',(16,16))
 for y,row in enumerate(r['source_rows']):
  for x,pen in enumerate(row):
   pen=int(pen,16)
   if pen:source.putpixel((x,y),tuple(v*36 for v in r['source_colors'][pen]))
 current=Image.open(ROOT/f'.local/bc-player-projectile-render/projectile-{pose:03x}.png').crop((152,104,168,120))
 source.save(out/f'{pose:03x}-source.png');current.save(out/f'{pose:03x}-current.png')
 x=i%2*300;y=i//2*166
 for j,im in enumerate((source,current)):sheet.paste(im.resize((128,128),Image.Resampling.NEAREST),(x+j*144,y+24))
 draw.text((x+4,y+4),f'PCE {pose:03X} | current Genesis',fill='white')
 method = f'Recolored Genesis frame {r["normal_code"]:03X}; original shade regions retained.' if r['decision']=='recolor' else 'Original PCE shape imported.'
 if r['decision']=='keep':method=f'Existing Genesis frame {r["normal_code"]:03X}; artwork and colors unchanged.'
 if r.get('silhouette_difference_pixels'):method+=f' Retains {r["silhouette_difference_pixels"]} silhouette-pixel differences from PCE in the tapered segment.'
 if r.get('source_kind')=='loaded-bank':method+=' Source: loaded PCE graphics bank; pose not observed live in the reference captures.'
 sections.append(f'<section><h2>Projectile {pose:03X}</h2><p>{method}</p><figure><img src="{pose:03x}-source.png" alt="PCE source"><figcaption>PCE BC</figcaption></figure><figure><img src="{pose:03x}-current.png" alt="Current cartridge"><figcaption>Genesis conversion</figcaption></figure></section>')
sheet.save(out/'comparison.png')
(out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>BC weapon corrections</title><style>body{font:18px system-ui;background:#182230;color:white;max-width:900px;margin:32px auto}img{width:160px;image-rendering:pixelated}figure{display:inline-block}section{border-top:1px solid #678}</style><h1>BC weapon corrections</h1><p>Matching Genesis shapes are recolored; unmatched shapes are imported from PCE. Both use ordered shades within existing Genesis palettes. These are inferred corrections; exact PCE hues are not claimed.</p>'+''.join(sections)+f'<p>Verified ROM: {qa["rom_sha256"]}</p>')
print(out/'index.html')
