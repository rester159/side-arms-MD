#!/usr/bin/env python3
"""Inspect actual Genesis rendering of the authored BC scenery draft.
Checks ROM-to-VRAM uploads and full round-one camera coverage. No gameplay or
performance claim: scenery geometry and aesthetics still need visual review.
"""
import argparse
import hashlib
import json
import struct
from run_rom import ROOT, Runner
from bc_background_equivalence import block_address

p=argparse.ArgumentParser(description=__doc__)
p.add_argument("--round",type=int,choices=(1,2,3,4,5,6,7,8,9,10),default=1)
a=p.parse_args()
second=a.round==2
prefix="bc_bg10" if a.round==10 else "bc_bg9" if a.round==9 else "bc_bg8" if a.round==8 else "bc_bg7" if a.round==7 else "bc_bg6" if a.round==6 else "bc_bg5" if a.round==5 else "bc_bg4" if a.round==4 else "bc_bg3" if a.round==3 else "bc_bg2" if second else "bc_bg"
r = Runner()
r.run(2600)
rom = (ROOT / 'out/release/rom.bin').read_bytes()
code_address = r.symbols[f'bc_round{a.round}_code']
cells = rom[code_address+0xc000:code_address+0x10000]
patterns = r.symbols[prefix+'_tiles']
assert patterns % 512 == 0, 'Each fast-DMA block must stay inside a 128 KiB ROM bank'
remap=struct.unpack_from('>256H',rom,r.symbols[prefix+'_remap'])
count=struct.unpack_from('>H',rom,r.symbols[prefix+'_draft']+8)[0]
assert all((v&4095)<count for v in remap if v!=4095)
attrs = struct.unpack_from('>'+str(count*16)+'H', rom, r.symbols[prefix+'_templates'])
r.write('dbg_bc_cells', struct.pack('>I', code_address+0xc000))
r.write('dbg_bc_background', struct.pack('>H',a.round+1))
if 1<=a.round<=9:r.write('dbg_bc_boss_preview',struct.pack('>H',a.round))
r.write('dbg_bc_robot_preview', b'\0\1')
out = ROOT / (f'.local/bc-background-draft{a.round}' if a.round>1 else '.local/bc-background-draft')
out.mkdir(parents=True, exist_ok=True)
boss_blocks={bank['round']:bank['block_count'] for bank in json.loads((ROOT/'res/generated/bc_boss_geometry.json').read_text())['banks']}
checks = 0
seen = set()
captures = []
# Stay inside the first round's 256-pixel-high strip. Camera spans the entire
# 320px view, including the extra margins around the original 256px play area.
cameras=list(range(480,2305,32)) if a.round==4 else list(range(0,1793,32)) if a.round==3 else list(range(480,2305,32)) if second else list(range(512,3777,32))
if a.round>=5:
    cameras=[]
    for cap in (('round10-protected',) if a.round==10 else ('round9-opening','round9-first-defeat','round9-second-defeat','round9-third-defeat','round9-fourth-defeat','round9-fifth-defeat-short','round9-sixth-opening','round9-sixth-defeat','round9-seventh','round9-eighth','round9-final') if a.round==9 else ('round8-opening','round8-boss-opening') if a.round==8 else ('round7-route',) if a.round==7 else ('round6-route3',) if a.round==6 else ('round5-opening','round5-later','round5-ending')):
        for path in sorted((ROOT/'.local/pce-reference'/cap).glob('f*-ram.bin')):
            # Captures include boot frames before the stage camera is installed.
            if int(path.name[1:7])<2160:continue
            ram=path.read_bytes()
            if ram[0x94]!=128 or ram[0x4b]!=a.round-1:continue
            camera=(ram[0x2e]*256+ram[0x2f]-32,ram[0x31]*256+ram[0x32])
            if camera not in cameras:cameras.append(camera)
if a.round==7:
    # Route captures begin after scrolling starts. Include the initial extra
    # 32-pixel Genesis margin from the actual checkpoint header as well.
    header = rom[code_address+0x6218:code_address+0x6220]
    start = (header[0]*256-32, header[1]*256)
    cameras = list(dict.fromkeys([(start[0]+dx,start[1]) for dx in (0,16,32)] + cameras))
if a.round==9:
    cameras=sorted(set(cameras)|{(x,2048) for x in range(480,2785,32)})
for x in cameras:
    if a.round>=5: x,y=x
    else:y=min(512,max(256,x+32-864)) if second else 0
    if a.round==3: y,x=x,0
    if a.round==4:y=768
    r.write('dbg_bc_camera', struct.pack('>2H', x, y));r.run(12)
    expected_columns = [max(16,c) if a.round in (4,7) else c for c in range(128)]
    assert struct.unpack('>128H', r.read('stage_column_offsets',256)) == tuple((c&7)|((c>>3)<<6) for c in expected_columns)
    assert r.read('slot_refs',56).count(255)==(0 if a.round==10 else boss_blocks[a.round])
    slots = r.read('cell_slot', 128)
    metas = struct.unpack('>56H', r.read('slot_meta', 112))
    shadow = struct.unpack('>2048H', r.read('shadow', 4096))
    for cy in range(y//32,(y+223)//32+1):
        for cx in range(x//32,(x+319)//32+1):
            map_cx = max(16, cx) if a.round in (4,7) else cx
            cell = cells[(map_cx & 7) | ((cy&7) << 3) | ((map_cx >> 3) << 6) | ((cy >> 3) << 10)]
            entry=remap[cell];meta=entry&4095
            assert meta < count
            slot = slots[(cy%8)*16 + cx%16]
            assert slot < 56, ('missing cell/cache exhausted', x, cx, cy, cell)
            assert metas[slot] == meta
            seen.add(cell)
            for ty in range(4):
                for tx in range(4):
                    k = ty*4 + tx
                    sx=3-tx if entry&0x4000 else tx
                    sy=3-ty if entry&0x8000 else ty
                    template = attrs[meta*16+sy*4+sx]
                    expected = (template + 160 + slot*16) ^ ((entry&0xc000)>>3) if template else 0
                    pos = ((cy*4+ty)%32)*64+(cx%16)*4+tx
                    assert shadow[pos] == expected
                    address = 0xe000 + pos*2
                    assert (r.vram[address^1]<<8)|r.vram[(address+1)^1] == expected
                    address = (160+slot*16+k)*32
                    source = block_address(rom,r.symbols,prefix,meta)+k*32
                    assert bytes(r.vram[(address+i)^1] for i in range(32)) == rom[source:source+32], (x,y,cx,cy,cell,slot,k,hex(address))
                    checks += 1
    if a.round>=5 or (y if a.round==3 else x) in (0,480,512,1024,1280,1792,2304,2560,3328,3776):
        path = out / f'camera-{x}-{y}.png'
        r.capture(path)
        captures.append(str(path))
r.write('dbg_bc_robot_preview', b'\0\0')
r.write('dbg_bc_background', b'\0\0')
r.run(120)
assert r.u32('flow_state') == 0
result = dict(rom_sha256=hashlib.sha256(rom).hexdigest(),round=a.round,cameras=len(cameras), verified_subtiles=checks, visible_cells=sorted(seen), unique_art_blocks=len({v&4095 for v in remap if v!=4095}), bank_blocks=count, captures=captures,
              artwork=f'Normal Genesis zone {21 if a.round==10 else 16 if a.round==8 else 19 if a.round==9 else 10 if a.round==5 else 13 if a.round==6 else 14 if a.round==7 else 6 if a.round==4 else 3 if a.round==3 else 1 if a.round>1 else 0}', draft=True, gameplay_enabled=False,
              source_collision_changed=False, performance_verified=False, returned_to_menu=True)
(out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
