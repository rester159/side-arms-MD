#!/usr/bin/env python3
"""Set exact cartridge extent and standard big-endian Genesis checksum after padding."""
from pathlib import Path
import sys
p=Path(sys.argv[1]);b=bytearray(p.read_bytes());assert b[0x100:0x104]==b'SEGA' and len(b)%2==0
assert len(b)<=0x400000,'ROM exceeds the 4 MiB cartridge window; no bank mapper is installed'
# A "SEGA SSF" console name (SGDK's template with ENABLE_BANK_SWITCH=1) makes Genesis Plus GX /
# EverDrive / MegaSD remap $000000 on every SRAM_enable() ($A130F1 = bank 0 register there).
assert b[0x100:0x10f]==b'SEGA MEGA DRIVE',f'ROM header console name is {bytes(b[0x100:0x110])!r}: must be "SEGA MEGA DRIVE " (src/rom_header.c)'
b[0x1a4:0x1a8]=(len(b)-1).to_bytes(4,'big')
b[0x18e:0x190]=(sum(int.from_bytes(b[i:i+2],'big') for i in range(0x200,len(b),2))&65535).to_bytes(2,'big')
p.write_bytes(b)
