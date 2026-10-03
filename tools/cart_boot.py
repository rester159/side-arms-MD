#!/usr/bin/env python3
"""Adapt SGDK's reset entry for launch from flash-cart menus.

Controller registers are not a reliable indication that this cartridge has run
before. Always perform TMSS and the full RAM/data initialization, including reset.
Keep the rest of the installed SGDK startup (vectors/interrupts) unchanged.
"""
from pathlib import Path
import re
import sys


def cartridge_boot(source):
    pattern = (r"        tst\.l   0xa10008\n"
               r"        bne\.s   SkipInit\n\n"
               r"        tst\.w   0xa1000c\n"
               r"        bne\.s   SkipInit\n")
    result, count = re.subn(pattern,
        "* Flash-cart launch / reset: always initialize this game's RAM and TMSS.\n", source)
    if count != 1:
        raise ValueError("Unrecognized SGDK boot entry: review the flash-cart adaptation")
    return result


if __name__ == '__main__':
    Path(sys.argv[2]).write_text(cartridge_boot(Path(sys.argv[1]).read_text()))
