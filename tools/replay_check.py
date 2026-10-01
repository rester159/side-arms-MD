"""Replay an arcade trace frame (scroll + sprite RAM) in the port; save side-by-side."""
import sys;sys.path.insert(0,'tools')
from run_rom import Runner, ROOT
from PIL import Image
import numpy as np
trace,frame=sys.argv[1],int(sys.argv[2]);lag=int(sys.argv[3]) if len(sys.argv)>3 else 1
ev=(ROOT/f'reports/oracle/{trace}/events.txt').read_text().splitlines()
F={};S={}
cur=None
for l in ev:
    if l.startswith('F|'):cur=int(l.split('|')[1]);F[cur]=l
    elif l.startswith('S|'):S[cur]=bytes.fromhex(l[2:])
f=F[frame].split('|');sx=f[5][3:];sx=int(sx[0:2],16)|(int(sx[2:4],16)<<8&0xf00)
spr=S[frame-lag];rec=bytes(b for o in range(0,4096,32) for b in spr[o:o+4])
r=Runner();r.run(100)
r.write('dbg_replay',b'\x01');r.write('dbg_spr',rec);r.write('scroll_x_fx',(sx<<8).to_bytes(4,'big'));r.run(12)
port=np.array(r.frame)
arc=np.array(Image.open(ROOT/f'reports/oracle/{trace}/snap/f{frame:05d}.png').convert('RGB'))[:,32:352]
out=ROOT/f'reports/replay_{trace}_{frame}.png'
Image.fromarray(np.concatenate([arc,port],0)).resize((640,896),Image.NEAREST).save(out);print(out,'sx',sx,'uploads',r.u16('uploads') if 'uploads' in r.symbols else '')
