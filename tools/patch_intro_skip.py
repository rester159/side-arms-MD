#!/usr/bin/env python3
"""Apply boot-skip hooks after fetching the private logo wrappers."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'src/intro'
for name in ('intros.c','sega_splash.c','capcom_splash.c'):
 p=root/name
 s=p.read_text()
 if 'bool intro_skip_poll(void);' not in s:
  s=s.replace('#include <genesis.h>','#include <genesis.h>\nbool intro_skip_poll(void);\nvoid intro_skip_release(void);',1)
 if name=='intros.c':
  s=s.replace('    capcom_splash();        /* CAPCOM logo + FM jingle */','    if (!intro_skip_poll()) capcom_splash();\n    intro_skip_release();')
 elif name=='sega_splash.c':
  s=s.replace('        if (shinobi_palroll_step())','        if (intro_skip_poll()) break;\n        if (shinobi_palroll_step())') if 'if (intro_skip_poll()) break;' not in s else s
 else:
  s=s.replace('        PAL_setColors(0, capcom_logo_cram, 16, CPU);','        if (intro_skip_poll()) break;\n        PAL_setColors(0, capcom_logo_cram, 16, CPU);') if 'if (intro_skip_poll()) break;' not in s else s
 p.write_text(s)
