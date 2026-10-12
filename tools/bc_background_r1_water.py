"""Join the R1 rock field to the surrounding sea instead of donor cyan sky."""
def compose(packed, templates, palette):
    def color(word,pen):return palette[((word>>13)&1)*16+pen] if pen else 0
    def rgb(c):return (c&14,(c>>4)&14,(c>>8)&14)
    def read(cell,x,y):
        k=y//8*4+x//8;word=templates[cell*16+k]
        raw=packed[cell*512+k*32+(y%8)*4+(x%8)//2]
        return color(word,(raw&15) if x&1 else raw>>4)
    # Rock-bearing cells start on 32px boundaries, matching the sea's phase.
    # Use the unchanged sea bank; retained rock pixels select its closest
    # existing grey/olive shade. No palette slots or geometry are changed.
    for cell in (0x13,0x14,0x15):
        sea=[[read(2 if cell==0x15 else 1,x,y) for x in range(32)]for y in range(32)]
        image=[[read(cell,x,y) for x in range(32)]for y in range(32)]
        for ty in range(4):
            for tx in range(4):
                k=ty*4+tx;pixels=[image[ty*8+y][tx*8+x]for y in range(8)for x in range(8)]
                water=[bool(c and not (c&14) and (c&0xe00)) for c in pixels]
                if not any(water):continue
                pens=[]
                for i,c in enumerate(pixels):
                    if water[i]:c=sea[ty*8+i//8][tx*8+i%8]
                    if not c:pens.append(0);continue
                    a=rgb(c)
                    pens.append(min(range(1,16),key=lambda p:sum((x-y)**2 for x,y in zip(a,rgb(palette[p])))))
                templates[cell*16+k]=0x8000|k
                packed[cell*512+k*32:cell*512+(k+1)*32]=bytes((pens[i]<<4)|pens[i+1]for i in range(0,64,2))
