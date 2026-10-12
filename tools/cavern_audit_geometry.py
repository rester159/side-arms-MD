"""Read-only route masks for the two displayed Normal cavern palettes."""
import numpy as np
import zones


def region_masks(sections, grid, count):
    """Return canonical-metatile masks; exclude pixels outside authored traversal.

    Zone ownership follows the runtime's center test and retention across legs.
    The split is world x >=1536, y >=2048. This does not validate raster timing.
    """
    visible = np.zeros((4096, 4096), bool)
    active = None

    def contains(zone, x, y):
        zx, zy, width, height = zones.ZONES[zone]['rect']
        return zx <= x < zx + width and zy <= y < zy + height

    for section in sections:
        for leg in section['legs']:
            sx, sy = leg['start']
            ex, ey = leg['end']
            dx, dy = (ex > sx) - (ex < sx), (ey > sy) - (ey < sy)
            for step in range(max(abs(ex - sx), abs(ey - sy)) + 1):
                x, y = sx + dx * step + 96, sy + dy * step + 16
                cx, cy = (x + 160) // 32, (y + 112) // 32
                if active is None or not contains(active, cx, cy):
                    eligible = [z for z in range(len(zones.ZONES))
                                if z not in zones.RUNTIME_OMITTED_ZONES and contains(z, cx, cy)]
                    if eligible:
                        active = eligible[0]
                if active == 10:
                    visible[max(0, y):min(4096, y + 224),
                            max(0, x):min(4096, x + 320)] = True

    x, y, width, height = zones.ZONES[10]['rect']
    assert grid.shape == (height, width)
    result = []
    for region in (0, 1):
        view = visible.copy()
        if region:
            view[:2048] = False
            view[:, :1536] = False
        else:
            view[2048:, 1536:] = False
        masks = np.zeros((count, 32, 32), bool)
        for row in range(height):
            for col in range(width):
                cell = int(grid[row, col])
                meta = cell & 4095
                assert meta < count
                pixels = view[(y + row) * 32:(y + row + 1) * 32,
                              (x + col) * 32:(x + col + 1) * 32]
                if cell & 0x4000:
                    pixels = pixels[:, ::-1]
                if cell & 0x8000:
                    pixels = pixels[::-1]
                masks[meta] |= pixels
        result.append(masks)
    return result
