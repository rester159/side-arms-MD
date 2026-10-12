#!/usr/bin/env python3
"""Use an exact byte copy for SDK driver uploads, including pre-main startup.

GCC 16 LTO miscompiles the SDK C copy with a shifted destination. Keep the
installed SDK untouched and reject unexpected source instead of guessing.
"""
from pathlib import Path
import sys


def exact_upload(source):
    start = source.index('NO_INLINE void Z80_upload(')
    end = source.index('NO_INLINE void Z80_download(', start)
    block = source[start:end]
    old = 'while(len--) *dst++ = *src++;'
    if block.count(old) != 1:
        raise ValueError('Unrecognized SGDK Z80 upload; review local adaptation')
    new = '''if (len) {
        __asm__ volatile("1: move.b (%1)+,(%0)+\\n\\tsubq.w #1,%2\\n\\tbne.s 1b"
                         : "+a"(dst), "+a"(src), "+d"(len) : : "cc", "memory");
    }'''
    return source[:start] + block.replace(old, new) + source[end:]


if __name__ == '__main__':
    Path(sys.argv[2]).write_text(exact_upload(Path(sys.argv[1]).read_text()))
