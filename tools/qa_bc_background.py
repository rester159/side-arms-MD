#!/usr/bin/env python3
"""Exercise BC block-map addressing through the Genesis background renderer.
Uses existing ROM bytes as a deterministic synthetic map, not finished BC art.
Checks actual cached metatiles, flips, nametable DMA and 4096-pixel wrapping.
"""
import json
import struct
import numpy as np
from run_rom import ROOT, Runner

r=Runner();r.run(2600)
rom=(ROOT/'out/release/rom.bin').read_bytes()
cells_address=r.symbols['zone0_tiles']
cells=rom[cells_address:cells_address+16384]
templates=struct.unpack_from('>1488H',rom,r.symbols['zone0_attr'])
# Eight resident art cells, all four flip combinations, and explicit blanks.
remap=[(4+i%8)|((i%4)<<14) if i!=221 else 0xfff for i in range(256)]
r.write('dbg_bc_cells',struct.pack('>I',cells_address))
r.write('dbg_bc_remap',struct.pack('>256H',*remap))
r.write('dbg_bc_background',b'\0\1')
r.write('dbg_bc_robot_preview',b'\0\1')
out=ROOT/'.local/bc-background-render';out.mkdir(parents=True,exist_ok=True)
checks=0;results=[]
for x,y in [(0,0),(1,1),(31,31),(32,32),(255,255),(256,256),(4080,4080),(4095,4095),(-32,-32),(512,736)]:
    r.write('dbg_bc_camera',struct.pack('>2H',x&65535,y&65535));r.run(24)
    shadow=struct.unpack('>2048H',r.read('shadow',4096))
    slots=r.read('cell_slot',128)
    metas=struct.unpack('>56H',r.read('slot_meta',112))
    for cy in range(y//32,(y+223)//32+1):
        for cx in range(x//32,(x+319)//32+1):
            wx,wy=cx%128,cy%128
            index=((wy//8)*16+wx//8)*64+(wy%8)*8+wx%8
            entry=remap[cells[index]];meta=entry&4095
            slot=slots[(cy%8)*16+cx%16]
            if meta==4095:assert slot==255
            else:
                assert slot<56,(x,y,cx,cy,meta,slot,r.u16("dbg_bc_background"),r.u16("dbg_bc_robot_preview"))
                assert metas[slot]==meta,(x,y,cx,cy,meta,slot,metas[slot])
            for ty in range(4):
                for tx in range(4):
                    expected=0
                    if meta!=4095:
                        sx=3-tx if entry&0x4000 else tx
                        sy=3-ty if entry&0x8000 else ty
                        t=templates[meta*16+sy*4+sx]
                        if t:expected=t+(160+slot*16)|((entry>>3)&0x1800)
                    pos=((cy%8)*4+ty)*64+(cx%16)*4+tx
                    assert shadow[pos]==expected,(x,y,cx,cy,tx,ty,hex(shadow[pos]),hex(expected))
                    address=0xe000+pos*2
                    actual=(r.vram[address^1]<<8)|r.vram[(address+1)^1]
                    assert actual==expected,('DMA',x,y,pos,actual,expected)
                    checks+=1
    assert np.any(r.frame),('empty rendered screen',x,y)
    path=out/('camera-%d-%d.png'%(x,y));r.capture(path)
    results.append(dict(camera=[x,y],path=str(path)))
r.write('dbg_bc_background',b'\0\0');r.write('dbg_bc_robot_preview',b'\0\0');r.run(120)
assert r.u32('flow_state')==0
result=dict(cameras=results,verified_tiles=checks,returned_to_menu=True,synthetic_map=True,playable_bc=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
