import time
from machine import Pin
import neopixel

W = 16
H = 16
N = W * H
DATA_PIN = 5

np = neopixel.NeoPixel(Pin(DATA_PIN, Pin.OUT), N)

cfg = {
    "serp": 1,      # 1 serpentine, 0 progressive
    "rot": 0,       # 0..3
    "flipx": 0,     # 0/1
    "flipy": 0,     # 0/1
    "b": 32,        # brightness 0..255
    "pat": 3,       # current pattern
}

_state = {
    "step": 0,
    "phase": 0,
    "last_phase_ms": 0,
    "running": False,
}

def _clamp8(x):
    return 0 if x < 0 else (255 if x > 255 else x)

def _scale(rgb):
    br = cfg["b"]
    r, g, b = rgb
    return (r * br // 255, g * br // 255, b * br // 255)

def _clear():
    for i in range(N):
        np[i] = (0, 0, 0)

def _transform_xy(x, y):
    if cfg["flipx"]:
        x = (W - 1) - x
    if cfg["flipy"]:
        y = (H - 1) - y

    rot = cfg["rot"] & 3
    if rot == 0:
        return x, y
    if rot == 1:   # 90
        return (W - 1) - y, x
    if rot == 2:   # 180
        return (W - 1) - x, (H - 1) - y
    return y, (H - 1) - x  # 270

def _xy_to_i(x, y):
    x, y = _transform_xy(x, y)

    if not cfg["serp"]:
        return y * W + x

    if (y & 1) == 0:
        return y * W + x
    return y * W + (W - 1 - x)

def _show():
    np.write()

# ---------- Patterns ----------
def _pat_moving_index():
    _clear()
    i = _state["step"]
    np[i] = _scale((255, 255, 255))
    _state["step"] = (i + 1) % N
    _show()
    time.sleep_ms(40)

def _pat_xy_grid():
    for y in range(H):
        for x in range(W):
            r = x * 255 // (W - 1)
            g = y * 255 // (H - 1)
            b = ((x ^ y) * 16) & 0xFF
            np[_xy_to_i(x, y)] = _scale((r, g, b))
    _show()
    time.sleep_ms(150)

def _pat_corner_markers():
    _clear()
    np[_xy_to_i(0, 0)] = _scale((255, 0, 0))                 # TL red
    np[_xy_to_i(W - 1, 0)] = _scale((0, 255, 0))             # TR green
    np[_xy_to_i(0, H - 1)] = _scale((0, 0, 255))             # BL blue
    np[_xy_to_i(W - 1, H - 1)] = _scale((255, 255, 255))     # BR white

    if W > 2 and H > 2:
        np[_xy_to_i(1, 0)] = _scale((255, 0, 0))
        np[_xy_to_i(0, 1)] = _scale((255, 0, 0))

    _show()
    time.sleep_ms(150)

def _pat_solid_rgb_cycle():
    now = time.ticks_ms()
    if time.ticks_diff(now, _state["last_phase_ms"]) > 800:
        _state["phase"] = (_state["phase"] + 1) % 4
        _state["last_phase_ms"] = now

    ph = _state["phase"]
    if ph == 0:
        c = (255, 0, 0)
    elif ph == 1:
        c = (0, 255, 0)
    elif ph == 2:
        c = (0, 0, 255)
    else:
        c = (255, 255, 255)

    c = _scale(c)
    for i in range(N):
        np[i] = c
    _show()
    time.sleep_ms(50)

def _pat_checkerboard():
    for y in range(H):
        for x in range(W):
            if ((x + y) & 1) == 0:
                np[_xy_to_i(x, y)] = _scale((255, 255, 255))
            else:
                np[_xy_to_i(x, y)] = (0, 0, 0)
    _show()
    time.sleep_ms(150)

_patterns = {
    1: _pat_moving_index,
    2: _pat_xy_grid,
    3: _pat_corner_markers,
    4: _pat_solid_rgb_cycle,
    5: _pat_checkerboard,
}

# ---------- Public controls (type these in Thonny REPL) ----------
def help():
    print("Controls (call from REPL):")
    print("  p(n)       pattern 1..5")
    print("  serp(v)    0 progressive, 1 serpentine")
    print("  rot(v)     0..3 (0,90,180,270)")
    print("  flipx(v)   0/1")
    print("  flipy(v)   0/1")
    print("  b(v)       brightness 0..255")
    print("  render()   draw current pattern once (static)")
    print("  run()      start animation loop (Ctrl+C to stop)")
    print("Patterns:")
    print("  1 moving index, 2 XY grid, 3 corners, 4 solid RGB cycle, 5 checkerboard")

def p(n):
    cfg["pat"] = max(1, min(5, int(n)))
    print("pat =", cfg["pat"])

def serp(v):
    cfg["serp"] = 1 if int(v) else 0
    print("serp =", cfg["serp"])

def rot(v):
    cfg["rot"] = int(v) & 3
    print("rot =", cfg["rot"])

def flipx(v):
    cfg["flipx"] = 1 if int(v) else 0
    print("flipx =", cfg["flipx"])

def flipy(v):
    cfg["flipy"] = 1 if int(v) else 0
    print("flipy =", cfg["flipy"])

def b(v):
    cfg["b"] = _clamp8(int(v))
    print("brightness =", cfg["b"])

def render():
    _patterns[cfg["pat"]]()

def run():
    print("Running. Ctrl+C to stop.")
    while True:
        _patterns[cfg["pat"]]()

# boot hint
help()
render()