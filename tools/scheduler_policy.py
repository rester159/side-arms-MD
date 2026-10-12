"""Decode only verified native scheduler entry ABIs; unknown builds stay unknown."""


def entry_policy(rom, address, wait_address):
    code = rom[address:address + 32]
    # GCC's constant ON_VBLANK_START clone has no incoming argument. It
    # pushes TRUE for VDP_waitVBlank(forceNext), then calls that function.
    if (code[:10] == bytes.fromhex('518f 2f02 4878 0001 4eb9') and
            int.from_bytes(code[10:14], 'big') == wait_address):
        return 'constant', 2
    # Generic entry reserves eight bytes, saves D2 and reads its 32-bit
    # argument from the original SP+4 (now SP+16), comparing it with 2.
    if code[:12] == bytes.fromhex('518f 2f02 242f 0010 7202 b282'):
        return 'stack', None
    return 'unknown', None


def process_policy(entry, stack_value):
    source, constant = entry
    value = constant if source == 'constant' else stack_value if source == 'stack' else None
    return value if value in (0, 1, 2) else None
