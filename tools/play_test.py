"""Drive the port with a simple input script and capture screenshots."""
import sys;sys.path.insert(0,'tools')
from run_rom import Runner, PAD, ROOT
from PIL import Image
import numpy as np
r=Runner();out=ROOT/'reports/port';out.mkdir(parents=True,exist_ok=True)
shots=[]
r.run(120); shots.append(np.array(r.frame))
for k in range(6):
    for i in range(20):
        r.run(2,PAD['RIGHT']|PAD['UP']|(PAD['A'] if i%2 else PAD['B']));r.run(2,PAD['DOWN'])
    shots.append(np.array(r.frame))
print('frames',r.frames,'loops',r.u32('frame_counter'),'line',r.u16('prof_line'))
grid=np.concatenate([np.concatenate(shots[i:i+2],1) for i in range(0,6,2)],0)
Image.fromarray(grid).save(ROOT/'reports/play_test.png')
