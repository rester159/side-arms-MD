#!/usr/bin/env python3
"""Prove linked background pooling preserves every source cell and palette."""
import argparse,hashlib,json,struct
from pathlib import Path
from bc_background_equivalence import symbols,compare_round,block_bank,block_address
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
old=(a.baseline/'rom.bin').read_bytes();os=symbols(a.baseline/'symbol.txt')
new=(ROOT/'out/release/rom.bin').read_bytes();ns=symbols(ROOT/'out/release/symbol.txt')
rows=[compare_round(old,os,new,ns,n)for n in range(1,11)]
assert len({ns['bc_bg'+(str(n)if n>1 else '')+'_tiles']for n in range(1,11)})==1
assert len({ns['bc_bg'+(str(n)if n>1 else '')+'_templates']for n in range(1,11)})==1
normal=0
for path in (ROOT/'res/generated').glob('zone*.bin'):
    if path.stem not in ns or path.stem not in os:continue
    raw=path.read_bytes();x=os[path.stem];y=ns[path.stem]
    assert old[x:x+len(raw)]==new[y:y+len(raw)]==raw,path.name
    normal+=1
result=dict(passed=True,rom_sha256=hashlib.sha256(new).hexdigest(),rom_bytes=len(new),rounds=rows,source_cells=sum(r['cells']for r in rows),pixel_checks=sum(r['pixels']for r in rows),palette_words=320,normal_material_blobs_unchanged=normal,etext_before=os['_etext'],etext_after=ns['_etext'],rom_payload_bytes_saved=os['_etext']-ns['_etext'])
if 'bc_bg_sources' in ns:
    count=struct.unpack_from('>H',new,ns['bc_bg_draft']+8)[0]
    old_count=struct.unpack_from('>H',old,os['bc_bg_draft']+8)[0]
    if count==old_count:
        # Character order may change; compare_round above proves rendered identity.
        result['raw_source_order_unchanged']=block_bank(old,os,'bc_bg',count)==block_bank(new,ns,'bc_bg',count)
    ranges=[(ns[p.stem],ns[p.stem]+p.stat().st_size) for p in (ROOT/'res/generated').glob('zone*_tiles.bin') if p.stem in ns]
    reused=sum(any(lo<=block_address(new,ns,'bc_bg',m) and block_address(new,ns,'bc_bg',m)+512<=hi for lo,hi in ranges) for m in range(count))
    result.update(indexed_source_blocks=count,normal_source_blocks=reused,private_source_references=count-reused,private_source_blocks=len({block_address(new,ns,'bc_bg',m) for m in range(count) if not any(lo<=block_address(new,ns,'bc_bg',m)<hi for lo,hi in ranges)}))
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
