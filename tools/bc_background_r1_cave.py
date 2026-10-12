"""Compose R1 cave from shared quadrants of existing Genesis materials.

The authored source topology is shared by pattern, rather than substituting
whole 32px scenery blocks. No source-console pixels are used here.
"""
# (source pattern, source palette), in TL/TR/BL/BR order.
CELLS = {
 0x24: ((0x58,5),(0x58,5),(0x34,9),(0x51,4)),
 0x25: ((0x4a,4),(0x50,4),(0x50,4),(0x52,4)),
 0x26: ((0x52,4),(0x4b,4),(0x52,4),(0x53,4)),
 0x27: ((0x58,5),(0x58,5),(0x58,5),(0x3d,4)),
 0x28: ((0x58,5),(0x58,5),(0x3d,4),(0x3d,4)),
 0x29: ((0x5a,4),(0x5e,4),(0x39,9),(0x39,9)),
 0x2a: ((0x5e,4),(0x5e,4),(0x39,9),(0x39,9)),
 0x2b: ((0x4a,4),(0x43,4),(0x50,4),(0x4b,4)),
 0x2c: ((0x44,4),(0x44,4),(0x4c,4),(0x4c,4)),
 0x2d: ((0x4c,4),(0x4c,4),(0x56,4),(0x56,4)),
 0x2e: ((0x4c,4),(0x4c,4),(0x5b,4),(0x55,4)),
 0x2f: ((0x4c,4),(0x4c,4),(0x54,4),(0x55,4)),
 0x30: ((0x5c,12),(0x5d,12),(0x39,9),(0x39,9)),
 0x31: ((0x31,9),(0x59,12),(0x39,9),(0x39,9)),
 0x32: ((0x58,5),(0x58,5),(0x58,5),(0x4a,4)),
 0x33: ((0x4d,13),(0x4e,13),(0x39,9),(0x39,9)),
 0x34: ((0x58,5),(0x58,5),(0x3e,4),(0x58,5)),
 0x35: ((0x46,4),(0x47,4),(0x4c,4),(0x4f,4)),
 0x36: ((0x4c,4),(0x4f,4),(0x56,4),(0x57,4)),
 0x37: ((0x5c,12),(0x45,12),(0x39,9),(0x39,9)),
 0x38: ((0x5e,4),(0x5f,12),(0x39,9),(0x39,9)),
 0x3c: ((0x58,5),(0x4a,4),(0x51,4),(0x50,4)),
 0x3d: ((0x59,12),(0x5a,4),(0x39,9),(0x39,9)),
}

def compose(tiles, attrs, packed, templates):
    # Resolve donor pixels with their palette/priority, retaining shade ramps.
    def pixel(data, words, cell, x, y):
        k=y//8*4+x//8; word=words[cell*16+k]
        raw=data[cell*512+k*32+(y%8)*4+(x%8)//2]
        return ((raw&15) if x&1 else raw>>4, word&0xe000)
    def quadrant(cell,q):
        return [[pixel(packed,templates,cell,(q%2)*16+x,(q//2)*16+y)
                 for x in range(16)] for y in range(16)]
    def donor(meta,x0,y0,step=1):
        return [[pixel(tiles,attrs,meta,x0+x,y0+y//step)
                 for x in range(16)] for y in range(16)]
    # Retain existing authored edge silhouettes, then reuse each consistently.
    origins={0x4a:(0x32,3),0x51:(0x24,3),0x3d:(0x28,2),
             0x5a:(0x29,0),0x5e:(0x2a,0),0x59:(0x31,1),
             0x34:(0x24,2),0x39:(0x39,2),0x31:(0x39,0)}
    materials={p:quadrant(*loc) for p,loc in origins.items()}
    rock=donor(70,0,16)
    for p in (0x50,0x52,0x4b,0x53,0x43,0x44,0x4c,0x56):materials[p]=rock
    # One complete arch spans the lower half of 2E/2F and upper half of 30.
    for p,x,y in ((0x5b,0,16),(0x54,0,16),(0x55,16,16),
                  (0x5c,0,24),(0x5d,16,24),(0x45,16,24)):
        materials[p]=donor(74,x,y,2)
    materials[0x4d]=donor(77,0,16);materials[0x4e]=donor(77,16,16)
    # The far end is the reflected opening slope, using the same rock texture.
    for p,other in ((0x3e,0x3d),(0x46,0x43),(0x47,0x4a),
                    (0x4f,0x50),(0x57,0x51),(0x5f,0x5a)):
        materials[p]=[list(reversed(row)) for row in materials[other]]
    # Reference outer envelopes remove the stepped rectangular donor edges.
    # Only the silhouette is retained; all interior pixels are Genesis rock.
    import json
    from pathlib import Path
    contours=json.loads((Path(__file__).parent/'data/bc_background_r1_cave_contours.json').read_text())
    for key,rows in contours['patterns'].items():
        p=int(key)
        materials[p]=[[rock[y][x] if left<=x<=right else (0,0)
                       for x in range(16)] for y,(left,right) in enumerate(rows)]
    materials[0x58]=[[(0,0)]*16 for _ in range(16)]
    for cell,patterns in CELLS.items():
        canvas=[[materials[patterns[(y//16)*2+x//16][0]][y%16][x%16]
                 for x in range(32)] for y in range(32)]
        for ty in range(4):
            for tx in range(4):
                k=ty*4+tx; flags={canvas[ty*8+y][tx*8+x][1]
                    for y in range(8) for x in range(8) if canvas[ty*8+y][tx*8+x][0]}
                assert len(flags)<=1,(cell,k,flags)
                templates[cell*16+k]=(next(iter(flags))|k) if flags else 0
                for y in range(8):
                    for x in range(4):
                        row=canvas[ty*8+y];left=tx*8+x*2
                        packed[cell*512+k*32+y*4+x]=row[left][0]<<4|row[left+1][0]
