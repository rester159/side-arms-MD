"""Source-exact colors for R4's valid Normal organic/machinery composition."""
import json
import struct
import numpy as np
from PIL import Image
from arcade_source import ROOT, Source, decode_bgtiles, bgmap_cells, palette_rgb
from quantize import to_md, md_word
from bc_background_r4 import arrange, compose as fitted_compose, MAPPING
from bc_background_r6 import reuse_pen_order
import zones

PRIMARY = {c:m for c,m in MAPPING.items() if c not in (24,45,60)}


def source_images():
    src=Source();main=src.region('maincpu');bg=decode_bgtiles(src.region('bgtiles'))
    codes,cols,_=bgmap_cells(src.region('bgmap'));x,y,w,h=zones.ZONES[6]['rect']
    metas=sorted({(int(codes[r,c]),int(cols[r,c]))for r in range(y,y+h)for c in range(x,x+w)})
    palette=np.array([to_md(tuple(v//17 for v in palette_rgb(main[0x14a37+i],main[0x14e37+i])))for i in range(1024)],np.uint8)
    def original(entry):
        cd,col=metas[entry&4095];pens=bg[cd].astype(np.int32)
        pixels=palette[col*16+pens]*36;pixels[pens==15]=0
        im=Image.fromarray(pixels)
        if entry&0x4000:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if entry&0x8000:im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        return im
    return arrange(original)


def compose():
    gen=ROOT/'res/generated';images=source_images()
    recipe=json.loads((ROOT/'tools/data/bc_background_r4_shading.json').read_text())
    banks=[[tuple(c)for c in bank]for bank in recipe['palette_banks_rgb3']]
    assert all(len(b)<=15 for b in banks)
    raw=(gen/'zone6_tiles.bin').read_bytes();attrs=np.fromfile(gen/'zone6_attr.bin','>u2');pal=np.fromfile(gen/'zone6_pal.bin','>u2')
    previous,words,_=fitted_compose(raw,attrs,pal)
    counts=[np.zeros((15,16),dtype=np.int64)for b in banks];pending=[]
    for c in range(61):
        pixels=np.array(images[c])//36
        for k in range(16):
            rgb=pixels[k//4*8:k//4*8+8,k%4*8:k%4*8+8]
            required=set(map(tuple,rgb.reshape(-1,3)))-{(0,0,0)} if c in PRIMARY else set()
            if not required:
                pending.append(None);continue
            choices=[b for b,colors in enumerate(banks)if required<=set(colors)]
            assert choices,(c,k,required)
            bank=choices[0]
            data=np.frombuffer(previous[(c*16+k)*32:(c*16+k+1)*32],np.uint8).reshape(8,4)
            pens=np.stack((data>>4,data&15),-1).reshape(8,8)
            if words[c*16+k]&0x0800:pens=pens[:,::-1]
            if words[c*16+k]&0x1000:pens=pens[::-1,:]
            for i,color in enumerate(banks[bank]):
                counts[bank][i]+=np.bincount(pens[np.all(rgb==color,axis=2)],minlength=16)
            pending.append((rgb,bank))
    orders=[reuse_pen_order(c)for c in counts];palette=[0]*32
    for b,colors in enumerate(banks):
        for i,color in enumerate(colors):palette[b*16+orders[b][i]]=md_word(color)
    packed=bytearray();templates=[]
    for n,record in enumerate(pending):
        px=np.zeros((8,8),np.uint8);word=0
        if record:
            rgb,bank=record
            for i,color in enumerate(banks[bank]):px[np.all(rgb==color,axis=2)]=orders[bank][i]
            word=bank*0x2000+n%16
            if not word:px=px[:,::-1];word=0x0800
        packed.extend(((px[:,::2]<<4)|px[:,1::2]).tobytes());templates.append(word)
    (gen/'bc_r4_material_pal.bin').write_bytes(struct.pack('>32H',*palette))
    return packed,templates,palette,[i if i in PRIMARY else 4095 for i in range(256)]
