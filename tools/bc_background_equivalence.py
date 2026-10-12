"""Compare linked BC scenery by resolved materials, independent of bank IDs."""
import struct


def symbols(path):
    result={}
    for line in path.read_text().splitlines():
        v=line.split()
        if len(v)>=3:result[v[2]]=int(v[0],16)
    return result


def block_address(rom, symbols, prefix, meta):
    if 'bc_bg_sources' in symbols:
        return struct.unpack_from('>I',rom,symbols['bc_bg_sources']+meta*4)[0]
    return symbols[prefix+'_tiles']+meta*512


def block_bank(rom, symbols, prefix, count):
    return b''.join(rom[block_address(rom,symbols,prefix,m):block_address(rom,symbols,prefix,m)+512] for m in range(count))


def rendered_cell(rom, symbols, prefix, entry):
    """Decode effective pens/attributes, independently of physical bank layout."""
    result=[]
    meta=entry&4095
    base=block_address(rom,symbols,prefix,meta)
    for y in range(32):
        for x in range(32):
            sx=31-x if entry&0x4000 else x
            sy=31-y if entry&0x8000 else y
            k=sy//8*4+sx//8
            word=struct.unpack_from('>H',rom,symbols[prefix+'_templates']+meta*32+k*2)[0]
            if not word:
                result.append(None)
                continue
            px=7-sx%8 if word&0x0800 else sx%8
            py=7-sy%8 if word&0x1000 else sy%8
            at=base+(word&0x7ff)*32+py*4+px//2
            byte=rom[at]
            pen=byte&15 if px%2 else byte>>4
            result.append((pen,word&0xe000))
    return result


def compare_round(before,old_symbols,after,new_symbols,number):
    prefix='bc_bg'+(str(number)if number>1 else '')
    old=struct.unpack_from('>256H',before,old_symbols[prefix+'_remap'])
    new=struct.unpack_from('>256H',after,new_symbols[prefix+'_remap'])
    seen=0
    for cell,(a,b) in enumerate(zip(old,new)):
        assert (a==4095)==(b==4095),(number,cell,'mapped status')
        if a==4095:continue
        assert rendered_cell(before,old_symbols,prefix,a)==rendered_cell(after,new_symbols,prefix,b),(number,cell,'rendered pixels/attributes')
        seen+=1
    x=old_symbols[prefix+'_palette'];y=new_symbols[prefix+'_palette']
    assert before[x:x+64]==after[y:y+64],(number,'palette')
    name=f'bc_round{number}_code';x=old_symbols[name];y=new_symbols[name]
    assert before[x:x+65536]==after[y:y+65536],(number,'source code/collision')
    # Runtime Zone layout: 5 words, then tile/template/map/palette pointers.
    at=new_symbols[prefix+'_draft'];metas=struct.unpack_from('>H',after,at+8)[0]
    tiles,attrs,unused,palette=struct.unpack_from('>4I',after,at+10)
    assert (tiles,attrs,unused,palette)==(new_symbols[prefix+'_tiles'],new_symbols[prefix+'_templates'],0,new_symbols[prefix+'_palette'])
    assert metas<1024 and all((e&4095)<metas for e in new if e!=4095)
    for m in range(metas):
        address=block_address(after,new_symbols,prefix,m)
        assert address%512==0 and address+512<=len(after)
        assert address//131072==(address+511)//131072
    return dict(round=number,cells=seen,pixels=seen*1024,shared_bank_blocks=metas,referenced_blocks=len({e&4095 for e in new if e!=4095}))
