"""Pack exact BC characters into existing Normal or shared aligned DMA blocks.

Logical metatile IDs remain stable. Only source pointers and template character
indices change; the runtime still uploads a complete 512-byte block on a miss.
Mirrored characters share bytes using VDP flip flags; rendered pixels, palettes
and priority remain unchanged. No runtime conversion is added.
"""

from functools import lru_cache
import random


def flip_character(raw, flags):
    if flags & 0x0800:
        raw = bytes((raw[y*4+3-x]&15)<<4 | raw[y*4+3-x]>>4
                    for y in range(8) for x in range(4))
    if flags & 0x1000:
        raw = b''.join(raw[y*4:y*4+4] for y in range(7,-1,-1))
    return raw


@lru_cache(maxsize=None)
def canonical_character(raw):
    return min((flip_character(raw, flags), flags) for flags in (0,0x0800,0x1000,0x1800))


def group_characters(pending):
    """Choose the smallest deterministic offline packing of exact tile sets.

    Equal-sized logical blocks can yield different shared unions depending on
    their order. Try bounded, local-seed tie orders, retaining the original
    packing unless a candidate needs fewer DMA blocks. Runtime uploads and
    character bytes are unaffected; the zero-sentinel restriction is identical.
    """
    if not pending:
        return []
    characters = sorted({c for _, required, _ in pending for c in required})
    ids = {c:i for i,c in enumerate(characters)}
    rows = [(meta, sum(1<<ids[c] for c in required),
             sum(1<<ids[c] for c in forbidden))
            for meta,required,forbidden in pending]
    by_meta = {r[0]:r for r in rows}
    original = [by_meta[r[0]] for r in sorted(pending,
                key=lambda row:(-len(row[1]),sorted(row[1]),row[0]))]

    def arrange(order):
        groups = []
        for meta, required, forbidden in order:
            best = None
            for i,(chars,blocked,metas) in enumerate(groups):
                union = chars|required
                size = union.bit_count()
                if size<=16 and (size<16 or union & ~(blocked|forbidden)):
                    score = ((required & ~chars).bit_count(),i)
                    if best is None or score<best:
                        best=score
            if best is None:
                groups.append((required,forbidden,[meta]))
            else:
                i=best[1];chars,blocked,metas=groups[i]
                groups[i]=(chars|required,blocked|forbidden,metas+[meta])
        return groups

    best = arrange(original)
    for seed in range(128):
        rng = random.Random(seed)
        candidate = arrange(sorted(rows,key=lambda row:(-row[1].bit_count(),rng.random())))
        if len(candidate)<len(best):
            best=candidate
    return [dict(chars={c for i,c in enumerate(characters) if bits>>i&1},
                 forbidden={c for i,c in enumerate(characters) if blocked>>i&1},
                 metas=metas) for bits,blocked,metas in best]


def pack(tiles, attrs, normal_banks):
    # Move each character into a canonical orientation and compensate in its
    # template. This also exposes mirrored matches in existing Normal blocks.
    original_tiles = tiles
    tiles = bytearray()
    flips = []
    for offset in range(0, len(original_tiles), 32):
        raw, flags = canonical_character(bytes(original_tiles[offset:offset+32]))
        tiles.extend(raw)
        flips.append(flags)
    for i, word in enumerate(attrs):
        flags = flips[(i//16)*16+(word&0x7ff)] if word else 0
        value = word ^ flags if word else 0
        # Preserve an active index-zero PAL0 template if cancellation would
        # turn it into the inactive sentinel. Duplicate into another index.
        if word and not value:
            # Such templates use a flip as their only active bit. Retain the
            # original character orientation for this entire logical block.
            begin = i//16*512
            tiles[begin:begin+512] = original_tiles[begin:begin+512]
            for k in range(16): flips[i//16*16+k] = 0
    attrs = [word ^ flips[(i//16)*16+(word&0x7ff)] if word else 0 for i,word in enumerate(attrs)]
    tiles = bytes(tiles)
    donors = []
    for name, data in normal_banks:
        assert len(data) % 512 == 0
        for offset in range(0, len(data), 512):
            block = data[offset:offset+512]
            positions = {}
            for k in range(16):
                raw, flags = canonical_character(bytes(block[k*32:(k+1)*32]))
                positions.setdefault(raw, []).append((k, flags))
            donors.append((name, offset, positions))
    count = len(tiles)//512
    assert len(tiles) == count*512 and len(attrs) == count*16
    sources = [None]*count
    templates = list(attrs)
    pending = []
    reused = 0
    for meta in range(count):
        block = tiles[meta*512:(meta+1)*512]
        words = attrs[meta*16:(meta+1)*16]
        assert all((w & 0x7ff) < 16 for w in words)
        required = {block[(w&0x7ff)*32:(w&0x7ff)*32+32] for w in words if w}
        for name, offset, positions in donors:
            if not required <= positions.keys():
                continue
            mapped = []
            for word in words:
                if not word:
                    mapped.append(0)
                    continue
                raw = block[(word&0x7ff)*32:(word&0x7ff)*32+32]
                found = next(((k,flags) for k,flags in positions[raw] if ((word&0xf800)^flags)|k), None)
                if found is None:
                    break  # Index zero must not create the inactive sentinel.
                index, flags = found
                mapped.append(((word&0xf800)^flags)|index)
            if len(mapped) == 16:
                sources[meta] = (name, offset)
                templates[meta*16:(meta+1)*16] = mapped
                reused += 1
                break
        if sources[meta] is None:
            # An active low-priority PAL0 character may not occupy index zero:
            # the resulting zero template is the renderer's inactive sentinel.
            forbidden = {block[(w&0x7ff)*32:(w&0x7ff)*32+32]
                         for w in words if w and not (w&0xf800)}
            pending.append((meta, required, forbidden))
    groups = group_characters(pending)
    private = bytearray()
    offsets = {}

    def intern(block):
        block = bytes(block)
        if block not in offsets:
            offsets[block] = len(private)
            private.extend(block)
        return ('bc_bg_shared_tiles', offsets[block])

    for group in groups:
        chars = sorted(group['chars'])
        if len(chars) == 16:
            # Use all sixteen slots when one character can safely occupy zero.
            first = next(raw for raw in chars if raw not in group['forbidden'])
            chars.remove(first)
            chars.insert(0, first)
            start = 0
        else:
            start = 1
        block = bytes(start*32) + b''.join(chars) + bytes((16-start-len(chars))*32)
        source = intern(block)
        positions = {raw: k+start for k, raw in enumerate(chars)}
        for meta in group['metas']:
            sources[meta] = source
            for k in range(16):
                word = attrs[meta*16+k]
                if word:
                    at = meta*512+(word&0x7ff)*32
                    templates[meta*16+k] = (word&0xf800)|positions[tiles[at:at+32]]
                    assert templates[meta*16+k], 'Active character became the blank sentinel'
    assert all(source is not None for source in sources)
    return private, templates, sources, reused
