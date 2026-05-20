from machine import Pin
import neopixel
import time
import sys
import select

WIDTH = 16
HEIGHT = 16
NUM_LEDS = WIDTH * HEIGHT

MATRIX_PIN = 7
BRIGHTNESS = 0.12

np = neopixel.NeoPixel(Pin(MATRIX_PIN, Pin.OUT), NUM_LEDS)

poller = select.poll()
poller.register(sys.stdin, select.POLLIN)

frame = bytearray(NUM_LEDS * 3)

def clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v

def xy_to_index(xp, yp):
    yp = HEIGHT - 1 - yp
    return yp * WIDTH + xp

def apply_brightness(r, g, b):
    return (int(r * BRIGHTNESS), int(g * BRIGHTNESS), int(b * BRIGHTNESS))

def set_pixel(x, y, r, g, b):
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        i = xy_to_index(x, y)
        j = i * 3
        frame[j] = r
        frame[j + 1] = g
        frame[j + 2] = b

def fill(r, g, b):
    for i in range(NUM_LEDS):
        j = i * 3
        frame[j] = r
        frame[j + 1] = g
        frame[j + 2] = b

def clear():
    fill(0, 0, 0)

def show():
    for i in range(NUM_LEDS):
        j = i * 3
        r, g, b = apply_brightness(frame[j], frame[j + 1], frame[j + 2])
        np[i] = (r, g, b)
    np.write()

def send_line(s):
    sys.stdout.write(s + "\n")

def from_hex_char(c):
    o = ord(c)
    if 48 <= o <= 57:
        return o - 48
    if 65 <= o <= 70:
        return o - 55
    if 97 <= o <= 102:
        return o - 87
    return -1

def decode_hex_byte(s, p):
    a = from_hex_char(s[p])
    b = from_hex_char(s[p + 1])
    if a < 0 or b < 0:
        return -1
    return (a << 4) | b

def handle_framehex(hexdata):
    expected = NUM_LEDS * 3 * 2
    if len(hexdata) != expected:
        send_line("ERR FRAMEHEX length")
        return
    k = 0
    for i in range(NUM_LEDS * 3):
        v = decode_hex_byte(hexdata, k)
        if v < 0:
            send_line("ERR FRAMEHEX hex")
            return
        frame[i] = v
        k += 2
    show()
    send_line("OK FRAMEHEX")

def handle_command(line):
    parts = line.strip().split()
    if not parts:
        return
    cmd = parts[0].upper()

    try:
        if cmd == "PING":
            send_line("PONG")
            return

        if cmd == "CLEAR":
            clear()
            show()
            send_line("OK CLEAR")
            return

        if cmd == "SHOW":
            show()
            send_line("OK SHOW")
            return

        if cmd == "FILL":
            if len(parts) != 4:
                send_line("ERR FILL expects 3 ints")
                return
            r = clamp(int(parts[1]), 0, 255)
            g = clamp(int(parts[2]), 0, 255)
            b = clamp(int(parts[3]), 0, 255)
            fill(r, g, b)
            show()
            send_line("OK FILL")
            return

        if cmd == "PIX":
            if len(parts) != 6:
                send_line("ERR PIX expects x y r g b")
                return
            x = int(parts[1])
            y = int(parts[2])
            r = clamp(int(parts[3]), 0, 255)
            g = clamp(int(parts[4]), 0, 255)
            b = clamp(int(parts[5]), 0, 255)
            set_pixel(x, y, r, g, b)
            show()
            send_line("OK PIX")
            return

        if cmd == "FRAMEHEX":
            if len(parts) != 2:
                send_line("ERR FRAMEHEX expects 1 arg")
                return
            handle_framehex(parts[1])
            return

        send_line("ERR unknown command")
    except Exception as e:
        send_line("ERR " + str(e))

def drain_serial():
    events = poller.poll(0)
    for _fd, _evt in events:
        line = sys.stdin.readline()
        if line:
            handle_command(line)

clear()
set_pixel(0, 0, 255, 255, 255)
show()
send_line("READY WIDTH={} HEIGHT={}".format(WIDTH, HEIGHT))

while True:
    drain_serial()
    time.sleep_ms(5)
