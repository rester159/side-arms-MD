#!/usr/bin/env python3
"""Check generated carrier levels against the original wavetable's AC power."""
import json,math
from pathlib import Path
from build_hucard_fm import patches
from inspect_hucard_music import ROOT,metadata
rom=(ROOT/'.local/pce-hucard/SideArms - Hyper Dyne (USA).pce').read_bytes()
rows,report=patches(rom);sources=metadata(rom)['instruments'];errors=[]
assert len(rows)==len(sources)==32
for row,source in zip(rows,sources):
    if report[source['id']-1]['algorithm'] != 7:
        continue  # Nonlinear patches use actual chip output in qa_hucard_fm_timbre.py.
    multipliers,levels=row[:4],row[4:]
    assert len(set(multipliers))==4 and all(1<=m<=15 for m in multipliers)
    assert all(0<=v<=127 for v in levels)
    samples=source['wave'];mean=sum(samples)/len(samples)
    source_power=sum((v-mean)**2 for v in samples)/len(samples)
    # Undo common headroom to compare source and represented carrier power.
    output_power=sum((16*10**((16-tl)*.75/20))**2/2 for tl in levels)
    error=10*math.log10(output_power/source_power)
    assert abs(error)<=.375001,(source['id'],error)
    errors.append(dict(instrument=source['id'],error_db=error))
result=dict(passed=True,instruments=len(errors),nonlinear_instruments_checked_separately=[r['instrument'] for r in report if r['algorithm'] != 7],max_level_error_db=max(abs(r['error_db'])for r in errors),mix_headroom_db=12,levels=errors)
(ROOT/'.local/pce-hucard/fm-level-qa.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
