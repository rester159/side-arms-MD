import sys;sys.path.insert(0,'tools')
import numpy as np
from PIL import Image
from arcade_source import *
s=Source();rom=s.region('maincpu')
lo=rom[0x14a37:0x14a37+0x400];hi=rom[0x14e37:0x14e37+0x400]
pal=np.array([palette_rgb(lo[i],hi[i]) for i in range(1024)],np.uint8)
tiles=decode_bgtiles(s.region('bgtiles'));np.save('reports/bgtiles.npy',tiles)
code,color,flags=bgmap_cells(s.region('bgmap'))
img=np.zeros((4096,4096,3),np.uint8)
for r in range(128):
  for c in range(128):
    t=tiles[code[r,c]]
    if flags[r,c]&1:t=t[:,::-1]
    if flags[r,c]&2:t=t[::-1,:]
    px=pal[color[r,c]*16+t];px[t==15]=(0,0,0)
    img[r*32:r*32+32,c*32:c*32+32]=px
Image.fromarray(img).save('reports/world.png')
Image.fromarray(img).resize((1024,1024)).save('reports/world_small.png')
print('unique tiles',len(set(code.flatten())),'colors',sorted(set(color.flatten())))
