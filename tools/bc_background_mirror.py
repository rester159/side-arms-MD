"""Mirror a complete background block while keeping character palette banks."""

def mirrored(pixels, words, flip):
    if any(word & 0x1800 for word in words):
        return None  # Already uses character-level flips; retain exact storage.
    packed = bytearray()
    attrs = []
    for y in range(4):
        for x in range(4):
            sx = 3 - x if flip & 0x4000 else x
            sy = 3 - y if flip & 0x8000 else y
            source = sy * 4 + sx
            word = words[source]
            # Generated material blocks have one sequential tile per character.
            assert word == 0 or word & 0x1fff == source
            raw = pixels[source * 32:(source + 1) * 32]
            if flip & 0x4000:
                raw = bytes((raw[py * 4 + 3 - px] & 15) << 4 |
                            raw[py * 4 + 3 - px] >> 4
                            for py in range(8) for px in range(4))
            if flip & 0x8000:
                raw = b''.join(raw[py * 4:(py + 1) * 4] for py in range(7, -1, -1))
            packed.extend(raw)
            # An inactive character remains inactive even at a different index.
            target = (word & 0xe000) | y * 4 + x if word else 0
            if word and not target:
                return None  # Zero is the renderer's inactive-character sentinel.
            attrs.append(target)
    return bytes(packed), tuple(attrs)
