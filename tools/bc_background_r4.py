"""Round-four Normal organic ledges and oval machinery, in original colors.

Source materials are zone 6. Components are rearranged for the PCE cell layout;
all resizes use nearest-neighbor sampling and all output colors must fit an
original Normal palette bank. No PCE artwork is consumed by this generator.
"""
from PIL import Image
import numpy as np

MAPPING = {0:0,1:15,2:28,3:15,4:37,5:43,6:47,7:51,8:47,9:50,10:50,
           11:27,12:37,13:37,14:27,15:56,16:30,17:31,18:32,19:33,
           20:31,21:32,24:56,45:58,60:61}

def render(raw, attrs, palette, entry):
    flip=entry&0xc000
    meta=entry&4095
    out=Image.new('RGB',(32,32))
    for k in range(16):
        word=int(attrs[meta*16+k])
        if not word:continue
        bank=word>>13&1
        for y in range(8):
            for x in range(8):
                byte=raw[(meta*16+k)*32+y*4+x//2]
                pen=byte&15 if x%2 else byte>>4
                c=int(palette[bank*16+pen]) if pen else 0
                rgb=((c>>1&7)*36,(c>>5&7)*36,(c>>9&7)*36)
                out.putpixel((k%4*8+x,k//4*8+y),rgb)
    if flip&0x4000:out=out.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if flip&0x8000:out=out.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return out


def materials(raw,attrs,pal):
    return arrange(lambda n: render(raw,attrs,pal,n))


def arrange(meta):
    def blank():return Image.new('RGB',(32,32))
    def joined(ms):
     a=Image.new('RGB',(len(ms)*32,32))
     for i,m in enumerate(ms):a.paste(meta(m),(i*32,0))
     return a
    def characters(image,xs,ys):
     result=Image.new('RGB',(len(xs)*8,len(ys)*8))
     for y,sy in enumerate(ys):
      for x,sx in enumerate(xs):result.paste(image.crop((sx*8,sy*8,sx*8+8,sy*8+8)),(x*8,y*8))
     return result
    small=np.array(meta(15));mask=(small[:,:,0]>small[:,:,1])&(small[:,:,0]>small[:,:,2]);small[~mask]=0;small=Image.fromarray(small)
    a=[blank()for _ in range(61)]
    a[3]=small;a[1].paste(small.crop((0,16,16,32)),(16,16));a[2].paste(joined([28,29]).resize((32,24),Image.Resampling.NEAREST),(0,8))
    for cell,m in {4:37,5:43,6:47,7:51,8:47|0x4000,9:50,10:50|0x4000,11:27,12:37|0x4000,13:37,14:27,15:56}.items():a[cell]=meta(m)
    # Attach the counterpart weapon barrel and machinery to the corresponding rock.
    a[13].paste(meta(16).crop((0,0,16,16)),(0,0));a[14].paste(characters(joined([11,12]),[1,3,4,6],range(4)).crop((0,16,32,32)),(0,16))
    # Normal's complete oval machine is 192x64. Select intact characters for the narrower PCE span.
    upper=joined([30,31,32,32|0x4000,31|0x4000,30|0x4000]);lower=joined([33,34,35,35|0x4000,34|0x4000,33|0x4000]);body=Image.new('RGB',(192,64));body.paste(upper);body.paste(lower,(0,32));body=characters(body,[0,1,3,4,6,8,10,11,12,13,15,17,19,20,22,23],[1,2,3,4,5,6]);top=body.crop((0,0,128,16));body=body.crop((0,16,128,48))
    for i in range(4):a[16+i]=body.crop((i*32,0,(i+1)*32,32))
    # PCE bottom stubs correspond to Normal's arch tips.
    a[20].paste(top.crop((32,0,64,16)),(0,16));a[21].paste(top.crop((64,0,96,16)),(0,16))
    # Defensive off-route cells keep machinery fill from this same source palette.
    for c,m in {24:56,45:58,60:61}.items():a[c]=meta(m)
    return a

def compose(raw,attrs,palette):
    images=materials(raw,attrs,palette)
    colors=[((int(c)>>1&7)*36,(int(c)>>5&7)*36,(int(c)>>9&7)*36) for c in palette]
    banks=[{rgb:next(i for i in range(1,16) if colors[b*16+i]==rgb)
            for rgb in colors[b*16+1:b*16+16]} for b in range(2)]
    packed=bytearray();templates=[]
    for cell in range(61):
        im=images[cell]
        for y in range(4):
            for x in range(4):
                rgb=list(im.crop((x*8,y*8,x*8+8,y*8+8)).getdata())
                used=set(rgb)-{(0,0,0)}
                if not used:
                    packed.extend(bytes(32));templates.append(0);continue
                available=[b for b in range(2) if used <= banks[b].keys()]
                assert available,(cell,x,y,'mixed palette-bank colors')
                bank=available[0]
                pens=[banks[bank][c] if c!=(0,0,0) else 0 for c in rgb]
                index=y*4+x
                word=bank*0x2000+index
                if not word:
                    # Template zero means inactive. Mirror the stored first
                    # character and undo it in hardware, preserving PAL0.
                    pens=[pens[py*8+7-px] for py in range(8) for px in range(8)]
                    word=0x0800
                packed.extend(pens[i]<<4|pens[i+1] for i in range(0,64,2))
                templates.append(word)
    return packed,templates,[i if i in MAPPING else 4095 for i in range(256)]
