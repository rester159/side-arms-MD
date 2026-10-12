#!/usr/bin/env python3
"""Decode reachable HuCard score instructions, without running CPU code.
This is a development input for native Genesis compilation, not a runtime VM.
"""
import json
from pathlib import Path
from inspect_hucard_music import metadata,ROOT
OPS=[('tempo',1),('gate',1),('volume',1),('instrument',1),('toggle_triplet',0),
     ('toggle_tie',0),('dotted_next',0),('octave',1),('octave_high',0),('octave_low',0),
     ('global_transpose',1),('transpose',1),('detune',1),('vibrato',1),
     ('repeat0',3),('repeat1',3),('repeat2',3),('repeat3',3),
     ('break0',2),('break1',2),('break2',2),('break3',2),('jump',2),('end',0),
     ('toggle_noise',0),('pan',1)]

def decode(rom,entries):
    def read(addr):
        assert 0x4f57<=addr<0x7702,hex(addr)
        return rom[0x10000+addr-0x4000]
    todo=list(entries);result={};occupied={}
    while todo:
        pc=todo.pop()
        if not pc or pc in result:continue
        value=read(pc)
        if value>=0x1f:
            row=dict(address=pc,op='note' if value&31 else 'rest',pitch=value&31,length_code=value>>5,bytes=[value]);nexts=[pc+1]
        else:
            assert value<len(OPS),('unknown opcode',hex(pc),value)
            op,n=OPS[value];args=[read(pc+i+1) for i in range(n)]
            row=dict(address=pc,op=op,args=args,bytes=[value]+args)
            nexts=[] if op=='end' else [pc+1+n]
            if op.startswith(('repeat','break')) or op=='jump':
                target=args[-2]+256*args[-1];row['target']=target
                if op=='jump':nexts=[target]
                else:nexts.append(target)
        row['successors']=nexts;result[pc]=row
        for offset in range(len(row['bytes'])):
            assert pc+offset not in occupied,('overlapping score instructions',hex(pc+offset),hex(pc),hex(occupied[pc+offset]))
            occupied[pc+offset]=pc
        todo.extend(nexts)
    return [result[k] for k in sorted(result)]

def main():
    rom=(ROOT/'.local/pce-hucard/SideArms - Hyper Dyne (USA).pce').read_bytes()
    info=metadata(rom);info['instructions']=decode(rom,{p for t in info['music']for p in t['channels']if p})
    out=ROOT/'.local/pce-hucard/decoded-score.json';out.write_text(json.dumps(info,indent=2)+'\n')
    print(f'{len(info["instructions"])} reachable score instructions, {len(info["instruments"])} instruments -> {out}')
if __name__=='__main__':main()
