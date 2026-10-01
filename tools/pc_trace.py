"""Debug: sample the 68000 PC/SR in Genesis Plus GX (libretro core exports m68k_get_reg)."""
import sys,bisect,ctypes as C;sys.path.insert(0,'tools')
from run_rom import Runner
r=Runner();f=r.lib.m68k_get_reg;f.restype=C.c_uint;f.argtypes=[C.c_int]
syms=[]
for line in open(r.symbols and 'out/release/symbol.txt'):
    v=line.split()
    if len(v)>=3 and v[1] in 'tT':
        try:syms.append((int(v[0],16),v[2]))
        except:pass
syms.sort();addrs=[a for a,_ in syms]
def name(a):
    i=bisect.bisect_right(addrs,a)-1;return syms[i][1]+'+'+hex(a-addrs[i]) if i>=0 else '?'
a,b=int(sys.argv[1]),int(sys.argv[2])
r.run(a)
for t in range(a,b):
    r.run(1);pc=f(16)
    print(r.frames,'PC',hex(pc),name(pc),'SR',hex(f(17)),'vt',r.u32('vtimer'))
