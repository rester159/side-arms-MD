"""Build-time Vivid conversion, preserving existing material shade distinctions.

The runtime remains a 512-word lookup. Saturation/brightness boosts are retained
unless they merge or reverse an ordered shade pair; affected colors fall back
to their Standard values. Rechecking matters: a fallback can expose a new pair.
This cannot recover shades already lost during artwork quantization.
"""
import colorsys


def rgb(word):
    return word >> 1 & 7, word >> 5 & 7, word >> 9 & 7


def word(color):
    r, g, b = color
    return r << 1 | g << 5 | b << 9


def index(value):
    r, g, b = rgb(value)
    return r | g << 3 | b << 6


def light(value):
    r, g, b = rgb(value)
    return 299*r + 587*g + 114*b


def base_lut():
    result = []
    for i in range(512):
        color = i & 7, i >> 3 & 7, i >> 6 & 7
        h, saturation, value = colorsys.rgb_to_hsv(*(v/7 for v in color))
        if saturation > .05:
            saturation = min(1., saturation*1.4)
        value = min(1., value*1.15)
        boosted = colorsys.hsv_to_rgb(h, saturation, value)
        quantized = [max(old, round(new*7)) if saturation <= .05 else round(new*7)
                     for old, new in zip(color, boosted)]
        if max(quantized) < max(color):
            quantized = color
        result.append(word(quantized))
    return result


def guard(lut, edges):
    """edges are (darker CRAM word, lighter CRAM word, minimum luma gap)."""
    result = list(lut)
    edges = sorted(set(edges))
    for a, b, gap in edges:
        assert 0 < gap <= light(b)-light(a), (a, b, gap)
    for _ in range(513):
        bad = [(a, b) for a, b, gap in edges
               if light(result[index(b)])-light(result[index(a)]) < gap]
        if not bad:
            return result
        for a, b in bad:
            result[index(a)] = a
            result[index(b)] = b
    raise AssertionError('Vivid shade fallback failed to converge')
