import time
import sys
from machine import Pin
import neopixel

W = 16
H = 16
N = W * H
DATA_PIN = 5

np = neopixel.NeoPixel(Pin(DATA_PIN, Pin.OUT), N)

BRIGHTNESS = 32  # 0..255

def _scale(r, g, b):
    br = BRIGHTNESS
    return (r * br // 255, g * br // 255, b * br // 255)

def xy_to_i(x, y):
    """
    Editor coordinates: (0,0)=top-left, x->right, y->down.

    Panel wiring observed: first LED bottom-left, serpentine rows, horizontal scan.
    """
    # Convert top-left origin to bottom-left origin
    yy = (H - 1) - y
    xx = x

    if (yy & 1) == 0:
        return yy * W + xx
    return yy * W + (W - 1 - xx)

def clear():
    for i in range(N):
        np[i] = (0, 0, 0)
    np.write()

def test_corners():
    clear()
    np[xy_to_i(0, 0)] = _scale(255, 0, 0)           # top-left red
    np[xy_to_i(W-1, 0)] = _scale(0, 255, 0)         # top-right green
    np[xy_to_i(0, H-1)] = _scale(0, 0, 255)         # bottom-left blue
    np[xy_to_i(W-1, H-1)] = _scale(255, 255, 255)   # bottom-right white
    np.write()

def show_frame(buf):
    if len(buf) != W * H * 3:
        return False

    i = 0
    for y in range(H):
        for x in range(W):
            r = buf[i]
            g = buf[i + 1]
            b = buf[i + 2]
            np[xy_to_i(x, y)] = _scale(r, g, b)
            i += 3

    np.write()
    return True

def read_line():
    # ASCII line reader, LF-terminated
    line = bytearray()
    while True:
        c = sys.stdin.buffer.read(1)
        if not c:
            time.sleep_ms(1)
            continue
        if c == b"\n":
            return bytes(line)
        if c != b"\r":
            line += c

def read_exact(n):
    buf = bytearray(n)
    mv = memoryview(buf)
    got = 0
    while got < n:
        chunk = sys.stdin.buffer.read(n - got)
        if not chunk:
            time.sleep_ms(1)
            continue
        mv[got:got + len(chunk)] = chunk
        got += len(chunk)
    return buf

def main():
    clear()
    test_corners()
    sys.stdout.write("READY\n")

    # Protocol:
    #   ASCII: FRAME\n
    #   then exactly 768 bytes (RGBRGB... row-major y=0..15 x=0..15)
    #   then ASCII: \n (optional; we ignore one byte if present)
    #
    # Other commands: PING, CLEAR, TEST
    while True:
        cmd = read_line().strip().upper()

        if cmd == b"PING":
            sys.stdout.write("PONG\n")
            continue

        if cmd == b"CLEAR":
            clear()
            sys.stdout.write("OK\n")
            continue

        if cmd == b"TEST":
            test_corners()
            sys.stdout.write("OK\n")
            continue

        if cmd == b"FRAME":
            frame = read_exact(W * H * 3)
            show_frame(frame)
            # swallow one trailing byte if sender adds '\n'
            sys.stdin.buffer.read(1)
            sys.stdout.write("OK\n")
            continue

        sys.stdout.write("ERR\n")

main()