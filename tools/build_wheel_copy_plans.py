"""Compile parallel cell copies for the three-frame wheel shadow cache."""
def copy_moves(before, after):
    sources = {key: i for i, key in enumerate(before) if key is not None}
    for i, key in enumerate(before):
        if key is not None and key == after[i]:
            sources[key] = i
    pending = {i: sources[key] for i, key in enumerate(after)
               if key is not None and key != before[i]}
    moves = []
    scratch = len(before)
    while pending:
        used = set(pending.values())
        safe = next((dst for dst in pending if dst not in used), None)
        if safe is not None:
            moves.append((pending.pop(safe), safe))
        else:
            assert scratch not in used
            dst = next(iter(pending))
            moves.append((dst, scratch))
            pending = {d: scratch if s == dst else s for d, s in pending.items()}
    return moves


def emit_wheel_copy_plan(name, maps, cx, cy):
    assert len(maps) == 264
    maps = [e & 0xcfff for e in maps]
    frames = [maps[i*88:(i+1)*88] for i in range(3)]
    keys = set(maps)
    missing = [sorted(keys-set(frame)) for frame in frames]
    capacity = max(map(len, missing))
    states = [frame+other+[None]*(capacity-len(other)) for frame, other in zip(frames, missing)]
    lines = []
    def array(label, values):
        lines.append('static const u16 '+label+'[] = {'+','.join(map(str, values or [0]))+'};')
    def address(slot):
        if slot >= 88:
            return 0x8000+(slot-88)*32
        return (((cy+slot//11)&7)<<9)|(((cx+slot%11)&15)<<3)
    init = []
    for frame, values in enumerate(missing):
        label = f'{name}_copy_keys{frame}'
        array(label, values+[0xffff]*(capacity-len(values)))
        init.append(label)
    ops = []
    counts = []
    for old in range(3):
        for new in range(3):
            # The wheel advances forward. Other API transitions rebuild using
            # cell_words, retaining correctness without six ROM copy programs.
            if new != (old + 1) % 3:
                ops.append('NULL')
                counts.append(0)
                continue
            moves = copy_moves(states[old], states[new])
            # Verify dependency ordering before writing runtime instructions.
            memory = states[old]+[None]
            for src, dst in moves:
                memory[dst] = memory[src]
            assert all(key is None or memory[i] == key for i, key in enumerate(states[new]))
            label = f'{name}_copy_{old}{new}'
            array(label, [address(slot) for pair in moves for slot in pair])
            ops.append(label)
            counts.append(len(moves))
    metas = sorted({e & 0xfff for e in maps})
    assert all(meta < 1024 for meta in metas)
    array(name+'_copy_metas', metas)
    lines.append(f'static const BgCopyPlan {name}_copy = '+'{'+
        f'{capacity},{len(metas)},{name}_copy_metas,'+
        '{'+','.join(init)+'},{'+','.join(ops)+'},{'+','.join(map(str, counts))+'}};')
    return lines
