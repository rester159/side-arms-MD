"""Read logical BC arrays, resolving aliases and indexed Normal block sources."""
import re
from pathlib import Path


def literal_arrays(text):
    return {name:[int(v,0) for v in re.findall(r'0x[0-9a-fA-F]+|\b\d+\b',body)]
            for name,body in re.findall(r'const (?:u8|u16)\s+(\w+)\[\d+\](?:\s+__attribute__\(\(aligned\(\d+\)\)\))?\s*=\s*\{(.*?)\};',text,re.S)}


def arrays(path):
    path=Path(path);text=path.read_text();result=literal_arrays(text)
    external=re.findall(r'extern const (?:u8|u16) (\w+)\[(\d+)\];',text)
    if external:
        pool=(path.parent/'bc_background_pool.c').read_text()
        values=literal_arrays(pool)
        aliases=dict(re.findall(r'extern const (?:u8|u16) (\w+)\[\d+\] __attribute__\(\(alias\("(\w+)"\)',pool))
        for name,count in external:
            value=values[aliases[name]]
            assert len(value)==int(count),(name,len(value),count)
            if name.endswith('_tiles') and 'bc_bg_sources[' in pool:
                body=re.search(r'bc_bg_sources\[\d+\]\s*=\s*\{(.*?)\};',pool,re.S).group(1)
                expanded=[]
                for source,offset in re.findall(r'(\w+)\s*\+\s*(\d+)',body):
                    offset=int(offset)
                    data=values[source] if source in values else (Path(__file__).resolve().parents[1]/'res/generated'/f'{source}.bin').read_bytes()
                    block=data[offset:offset+512]
                    assert len(block)==512,(source,offset)
                    expanded.extend(block)
                value=expanded
            result[name]=value
    return result
