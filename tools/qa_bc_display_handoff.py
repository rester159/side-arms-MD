#!/usr/bin/env python3
"""Verify BC scenes suspend the title HUD and restore it on menu return."""
import ctypes as C
import json
import numpy as np
from run_rom import Runner,ROOT
r=Runner();r.run(2600)
# Isolate stale window/H-interrupt pixels from the intentionally visible scenery.
r.write('dbg_bc_native_background_off',b'\0\1')
reg=(C.c_uint8*32).in_dll(r.lib,'reg')
assert reg[0]&16, 'regular HUD H-interrupt should be enabled'
results=[]
for flag in ('dbg_bc_native','dbg_bc_robot_preview','dbg_bc_native'):
    r.write(flag,b'\0\1');r.run(90)
    assert not reg[0]&16, (flag,'stale HUD H-interrupt')
    for _ in range(30):
        r.run(1)
        assert reg[17]==0 and reg[18]==(1 if flag=='dbg_bc_native' else 0), (flag,'incorrect scene window register')
        assert not np.any(r.frame[200:224]),(flag,'title footer leaked')
    r.write(flag,b'\0\0');r.run(120)
    assert r.u32('flow_state')==0 and reg[0]&16
    assert np.any(r.frame[200:224]),'menu footer should be visible again'
    results.append(dict(scene=flag,window_owned_by_scene=True,footer_cleared=True,menu_restored=True))
print(json.dumps(results,indent=2))
(ROOT/'.local/pce-reference/display-handoff.json').write_text(json.dumps(results,indent=2)+'\n')
