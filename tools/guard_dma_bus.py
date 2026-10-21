#!/usr/bin/env python3
"""Require acknowledged Z80 ownership and atomic DMA commands in the local SDK copy."""
from pathlib import Path
import sys


def guard(source):
    for old,new in [('if (!busTaken) Z80_requestBus(FALSE);','if (!busTaken) Z80_requestBus(TRUE);'),
                    ('busTaken = Z80_getAndRequestBus(FALSE);','busTaken = Z80_getAndRequestBus(TRUE);')]:
        if source.count(old)!=1:
            raise ValueError('Unrecognized SGDK DMA bus ownership sequence')
        source=source.replace(old,new)
    # No interrupt may release a request that has not yet been acknowledged,
    # or insert a VDP register write between the command's two halves.
    old='#if (HALT_Z80_ON_DMA != 0)\n    bool busTaken = Z80_isBusTaken();'
    if source.count(old)!=1:
        raise ValueError('Unrecognized SGDK queued DMA critical section')
    source=source.replace(old,'    SYS_disableInts();\n'+old)
    start=source.index('void DMA_doDmaFast(')
    before,body=source[:start],source[start:]
    marker='    // first command word\n    *pw = *cmdbufp++;\n'
    if body.count(marker)!=1:raise ValueError('Unrecognized SGDK immediate DMA command')
    body=body.replace(marker,'    SYS_disableInts();\n')
    body=body.replace('    // trigger DMA (second word command wrote from memory to avoid possible failure on some MD)',
                      marker+'\n    // trigger DMA (second word command wrote from memory to avoid possible failure on some MD)',1)
    source=before+body
    old='    if (!busTaken) Z80_releaseBus();\n#endif  // HALT_Z80_ON_DMA'
    if source.count(old)!=2:raise ValueError('Unrecognized SGDK DMA bus release')
    # Balance the critical section even when the SDK disables Z80 halting.
    source=source.replace(old,old+'\n    SYS_enableInts();')
    return source

if __name__=='__main__':
    Path(sys.argv[2]).write_text(guard(Path(sys.argv[1]).read_text()))
