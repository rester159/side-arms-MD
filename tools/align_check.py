"""Compare the port's BG against an arcade snapshot at the same scroll."""
import sys;sys.path.insert(0,'tools')
from run_rom import Runner
from PIL import Image
import numpy as np
snap,sx=sys.argv[1],int(sys.argv[2])
r=Runner();r.run(120)
r.write("scroll_x_fx",((sx<<8)-0x800).to_bytes(4,"big"));r.run(20)
port=np.array(Image.fromarray(r.frame))
arc=np.array(Image.open(snap).convert('RGB'))[:,32:352]
Image.fromarray(np.concatenate([arc,port],0)).resize((640,896),Image.NEAREST).save('reports/align.png')
best=None
for dy in range(-20,21):
    for dx in range(-8,9):
        a=arc[40:200,20:300].astype(int);p=np.roll(np.roll(port,dy,0),dx,1)[40:200,20:300].astype(int)
        e=np.abs(a-p).sum()
        if best is None or e<best[0]:best=(e,dx,dy)
print('best shift (err,dx,dy)',best)
