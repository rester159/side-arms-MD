"""Complete BC boundaries for monolithic and shared frame ownership.

Shared measurements begin at bc_scene_update and finish at main's return from
 game_draw, including dispatch/profiling between update and draw. Input and final
video/VBlank work are outside this interval. The caller ignores draw returns
without a pending BC entry. The legacy scene return remains supported.
"""
import re
import subprocess
from pathlib import Path


def _verified_hoisted_paths(instructions, loads, rom):
    """Require the target initialization on every reachable indirect-call path."""
    registers = {register for _, register in loads}
    assert len(registers) == 1, ('different hoisted registers', loads)
    register = registers.pop()
    aliases = {'a6', 'fp'} if register in ('a6', 'fp') else {register}
    names = '|'.join(sorted(aliases))
    reference = re.compile(r'%(?:' + names + r')(?![a-z0-9])')
    call = re.compile(r'%(?:' + names + r')@')
    loaded = {at for at, _ in loads}
    index = {at: i for i, (at, _, _) in enumerate(instructions)}
    pending = [(instructions[0][0], False)]
    seen, returns = set(), set()
    while pending:
        at, initialized = pending.pop()
        if (at, initialized) in seen:
            continue
        seen.add((at, initialized))
        i = index[at]
        _, opcode, operands = instructions[i]
        if at in loaded:
            initialized = True
        elif opcode == 'jsr' and call.fullmatch(operands):
            assert initialized, ('indirect call can bypass target initialization', at)
            assert rom[at:at+2] == (0x4e90 + int('6' if register == 'fp' else register[1])).to_bytes(2, 'big')
            returns.add(at + 2)
        elif reference.search(operands) or (opcode.startswith('movem') and '@' in operands.split(',')[0]):
            # Conservatively invalidate even a read or an implicit MOVEM restore.
            initialized = False
        if opcode in ('rts', 'rte', 'rtr'):
            continue
        branch = ((opcode.startswith('b') and opcode not in ('bset', 'bclr', 'bchg', 'btst')
                   and not opcode.startswith('bsr')) or opcode.startswith('db') or opcode == 'jmp')
        if branch:
            destination = operands.split(',')[-1].strip()
            match = re.fullmatch(r'(?:0x)?([0-9a-f]+)(?:\s+<[^>]+>)?', destination)
            assert match, ('unsupported control transfer', at, opcode, operands)
            target = int(match[1], 16)
            assert target in index, ('branch leaves decoded main', at, target)
            pending.append((target, initialized))
            if opcode.startswith('bra') or opcode == 'jmp':
                continue
        if i + 1 < len(instructions):
            pending.append((instructions[i+1][0], initialized))
    assert returns, 'No reachable initialized indirect calls'
    return sorted(returns)


def _hoisted_returns(rom_path, rom, main, end, target):
    """Accept a verified callee-saved LEA target,An / JSR (An) main loop.

    Decode instructions, not raw immediate words. Reject any additional use or
    write of the selected register, memory-to-register MOVEM after its load,
    an entry branch that skips the initialization. Multiple equivalent loads
    use a control-flow walk that checks every reachable call path. Calls
    preserve A2..A6 under the existing 68000 ABI. A0/A1 are never accepted.
    """
    assert rom_path is not None, 'Hoisted call needs matching ROM for disassembly'
    rom_path = Path(rom_path)
    assert rom_path.read_bytes() == rom, 'ROM changed before boundary disassembly'
    objdump = Path.home() / 'mars/m68k-elf/bin/m68k-elf-objdump'
    listing = subprocess.check_output([str(objdump), '-D', '-b', 'binary', '-m', 'm68k:68000',
        '--start-address='+hex(main), '--stop-address='+hex(end), str(rom_path)], text=True)
    instructions = []
    for line in listing.splitlines():
        match = re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{4}\s+)+)([a-z][a-z0-9.]*)\s*(.*)$', line)
        if match:
            instructions.append((int(match[1], 16), match[3], match[4].strip()))
    loads = []
    for at, opcode, operands in instructions:
        match = re.fullmatch(r'(?:0x)?([0-9a-f]+)(?:\s+<[^>]+>)?,%(a[2-6]|fp)', operands)
        if opcode == 'lea' and match and int(match[1], 16) == target:
            loads.append((at, match[2]))
    if len(loads) > 1:
        return _verified_hoisted_paths(instructions, loads, rom)
    assert len(loads) == 1, ('unknown hoisted scene/draw target load', loads)
    loaded, register = loads[0]
    aliases = {'a6', 'fp'} if register in ('a6', 'fp') else {register}
    names = '|'.join(sorted(aliases))
    reference = re.compile(r'%(?:'+names+r')(?![a-z0-9])')
    call = re.compile(r'%(?:'+names+r')@')
    returns = []
    for at, opcode, operands in instructions:
        if at == loaded:
            continue
        if at < loaded:
            # Normal entry must execute the LEA before reaching the loop.
            if opcode.startswith('b') and opcode not in ('bset', 'bclr', 'bchg', 'btst'):
                match = re.match(r'(?:0x)?([0-9a-f]+)(?:\s|$)', operands)
                assert not match or int(match[1], 16) <= loaded, 'Entry branch skips hoisted load'
            continue
        if opcode == 'jsr' and call.fullmatch(operands):
            assert rom[at:at+2] == (0x4e90+int('6' if register == 'fp' else register[1])).to_bytes(2, 'big')
            returns.append(at+2)
        else:
            assert not reference.search(operands), ('hoisted register has another use/write', at, opcode, operands)
            # A register range may restore the selected register implicitly.
            assert not (opcode.startswith('movem') and '@' in operands.split(',')[0]), 'MOVEM can restore hoisted register'
    return returns


def scene_boundary(symbols, by_name, rom, rom_path=None):
    fused = 'game_frame' in by_name
    shared = 'bc_scene_update' in by_name
    entry = by_name['game_frame' if fused else 'bc_scene_update' if shared else 'bc_scene_frame']
    # LTO may inline game_draw into main and bc_scene_draw into flow_draw.
    # The BC branch of game_draw returns immediately after flow_draw; its
    # matching main return is therefore the same completed-BC-work boundary.
    draw_name = 'game_draw' if 'game_draw' in by_name else 'flow_draw'
    target = by_name[draw_name] if shared and not fused else entry
    main = next(at for at, name in symbols if name == 'main' or name.startswith('main.'))
    end = min(at for at, name in symbols if at > main)
    call = b'\x4e\xb9' + target.to_bytes(4, 'big')
    returns = [at+6 for at in range(main, end-5, 2) if rom[at:at+6] == call]
    if not returns and fused:
        # A nearby engine frame can use PC-relative JSR or BSR.W after LTO. Only accept actual
        # disassembled calls, and independently verify the encoded target.
        objdump = Path.home() / 'mars/m68k-elf/bin/m68k-elf-objdump'
        listing = subprocess.check_output([str(objdump), '-D', '-b', 'binary', '-m', 'm68k:68000',
            '--start-address='+hex(main), '--stop-address='+hex(end), str(rom_path)], text=True)
        for line in listing.splitlines():
            match = re.match(r'^\s*([0-9a-f]+):\s+(6100|4eba)\s+([0-9a-f]{4})\s+(?:bsrw\s+|jsr\s+%pc@\()(?:0x)?([0-9a-f]+)', line)
            if match and int(match[4], 16) == target:
                at = int(match[1], 16)
                assert rom[at:at+2] == int(match[2], 16).to_bytes(2, 'big')
                assert at+2+int.from_bytes(rom[at+2:at+4], 'big', signed=True) == target
                returns.append(at+4)
    if not returns:
        returns = _hoisted_returns(rom_path, rom, main, end, target)
    assert 1 <= len(returns) <= 3, ('unknown main scene/draw call layout', returns)
    scope = ('Engine frame entry through its main return, including session dispatch and any catch-up updates/input inside the frame'
        if fused else 'BC update entry through shared '+draw_name+' return, including dispatcher overhead'
        if shared else 'Monolithic BC scene entry through its main return')
    return entry, returns, scope
