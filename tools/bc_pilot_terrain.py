"""Read-only terrain helpers for the controller-driven campaign diagnostic."""
def solid(cells, attributes, x, y):
    x, y = int(x) & 65535, int(y) & 65535
    index = ((x >> 5) & 7) | (((x & 3840) | (y & 224)) >> 2) | ((y << 2) & 15360)
    part = ((x & 16) >> 3) | ((y & 16) >> 2)
    return attributes[cells[index] * 8 + part + 1] & 15


def stationary_step(x, y, vx, vy, camera_x, camera_y, terrain):
    """Match player terrain probes at a stationary camera; no crush prediction."""
    wx, wy = camera_x + x, camera_y + y
    if terrain(wx + (-8 if vx < 0 else 8), wy):
        vx = 0
    if terrain(wx, wy + (-8 if vy < 0 else 8)):
        vy = 0
    return max(16, min(240, x + vx)), max(32, min(200, y + vy))


def scrolling_step(x, y, vx, vy, camera_x, camera_y, scroll_x, scroll_y, terrain):
    """One production-order movement step in unsigned 8.8 player coordinates."""
    x, y = x & 65535, y & 65535
    scroll_x, scroll_y = scroll_x & 65535, scroll_y & 65535
    wx, wy = camera_x + (x >> 8), camera_y + (y >> 8)
    if terrain(wx + (-8 if vx < 0 else 8), wy):
        forward = vx >= 0
        vx = 0
        if forward and scroll_x:
            x = (x - scroll_x) & 65535
            if x < 16 * 256:
                return x, y, True
    wx = camera_x + (x >> 8)
    if terrain(wx, wy + (-8 if vy < 0 else 8)):
        forward = vy >= 0
        vy = 0
        if forward and scroll_y:
            y = (y - scroll_y) & 65535
            if y < 32 * 256:
                return x, y, True
    x, y = (x + vx * 256) & 65535, (y + vy * 256) & 65535
    x = (x & 255) | (max(16, min(240, x >> 8)) << 8)
    y = (y & 255) | (max(32, min(200, y >> 8)) << 8)
    return x, y, False
