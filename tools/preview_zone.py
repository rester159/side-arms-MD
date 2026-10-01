"""Render a converted zone from res/generated data (what the Genesis shows)."""
import sys,struct
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];G=ROOT/'res/generated'
sys.path.insert(0,str(ROOT/'tools'));import zones
zi=int(sys.argv[1]) if len(sys.argv)>1 else 0
x0,y0,w,h=zones.ZONES[zi]['rect']
tiles=np.frombuffer((G/f'zone{zi}_tiles.bin').read_bytes(),np.uint8)
attr=(G/f'zone{zi}_attr.bin').read_bytes()
m=struct.unpack(f'>{w*h}H',(G/f'zone{zi}_map.bin').read_bytes())
pw=struct.unpack('>32H',(G/f'zone{zi}_pal.bin').read_bytes())
def rgb(wd):
    r=(wd>>1)&7;g=(wd>>5)&7;b=(wd>>9)&7;return (r*36,g*36,b*36)
pal=np.array([rgb(x) for x in pw],np.uint8)
def tile(i):
    t=tiles[i*32:i*32+32];px=np.zeros((8,8),np.uint8)
    for y in range(8):
        for x in range(4):
            v=t[y*4+x];px[y,2*x]=v>>4;px[y,2*x+1]=v&15
    return px
img=np.zeros((h*32,w*32,3),np.uint8)
for r in range(h):
    for c in range(w):
        e=m[r*w+c];mt=e&0xfff;hf=e>>14&1;vf=e>>15&1
        for sy in range(4):
            for sx in range(4):
                i=mt*16+sy*4+sx;px=tile(i);p=attr[i]&1
                if hf:px=px[:,::-1]
                if vf:px=px[::-1,:]
                dx=(3-sx) if hf else sx;dy=(3-sy) if vf else sy
                col=pal[p*16+px];col[px==0]=0
                img[r*32+dy*8:r*32+dy*8+8,c*32+dx*8:c*32+dx*8+8]=col
Image.fromarray(img).save(ROOT/f'reports/zone{zi}_md.png')
arc=Image.open(ROOT/'reports/world.png').crop((x0*32,y0*32,(x0+w)*32,(y0+h)*32))
both=Image.new('RGB',(1600,h*32*2*1600//(w*32)+4))
a=arc.resize((1600,h*32*1600//(w*32)));b=Image.fromarray(img).resize(a.size)
both.paste(a,(0,0));both.paste(b,(0,a.height+4));both.save(ROOT/f'reports/zone{zi}_compare.png')
