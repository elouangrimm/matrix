import machine
import neopixel
import sys
import select
import time
import micropython
import math
import gc

# CRITICAL: Disable Ctrl+C so binary data doesn't crash the script back to REPL
micropython.kbd_intr(-1)

PIN_NUM = 5
NUM_LEDS = 256
pin = machine.Pin(PIN_NUM, machine.Pin.OUT)
np = neopixel.NeoPixel(pin, NUM_LEDS)
boot_btn = machine.Pin(9, machine.Pin.IN, machine.Pin.PULL_UP) # C3 BOOT button is GPIO9

# Divides brightness to prevent USB power resets on the C3 (8 = 12.5% brightness)
BRIGHT_DIV = 8 

def xy_to_i(x, y):
    physical_row = 15 - y 
    if physical_row % 2 == 0:
        return (physical_row * 16) + x
    else:
        return (physical_row * 16) + (15 - x)

def clear():
    for i in range(NUM_LEDS):
        np[i] = (0, 0, 0)
    np.write()

def test_pattern():
    clear()
    np[xy_to_i(0, 0)]   = (255//BRIGHT_DIV, 0, 0)
    np[xy_to_i(15, 0)]  = (0, 255//BRIGHT_DIV, 0)
    np[xy_to_i(0, 15)]  = (0, 0, 255//BRIGHT_DIV)
    np[xy_to_i(15, 15)] = (255//BRIGHT_DIV, 255//BRIGHT_DIV, 255//BRIGHT_DIV)
    np.write()

# -- Animations --
def hsl_to_rgb(h, s, l):
    h = h / 360
    if s == 0:
        r = g = b = l
    else:
        def hue2rgb(p, q, t):
            if t < 0: t += 1
            if t > 1: t -= 1
            if t < 1/6: return p + (q - p) * 6 * t
            if t < 1/2: return q
            if t < 2/3: return p + (q - p) * (2/3 - t) * 6
            return p
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        r = hue2rgb(p, q, h + 1/3)
        g = hue2rgb(p, q, h)
        b = hue2rgb(p, q, h - 1/3)
    return (int(r * 255), int(g * 255), int(b * 255))

class Animator:
    def __init__(self):
        self.mode = None
        self.phase = 0
        self.last_update = time.ticks_ms()
        self.drops = [-1.0]*16
        self.speed = 1.0
        self.brightness = 1.0
    
    def set(self, mode, speed=1.0, brightness=1.0):
        self.mode = mode
        self.phase = 0
        self.drops = [-1.0]*16
        self.speed = speed
        self.brightness = brightness
        
    def step(self):
        if not self.mode:
            return
            
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_update) < 50:
            return
            
        self.last_update = now
        
        if self.mode == "rainbow":
            self.phase -= 0.5 * self.speed
            for y in range(16):
                for x in range(16):
                    hue = ((x + y) * 10 + self.phase * 10) % 360
                    if hue < 0: hue += 360
                    r,g,b = hsl_to_rgb(hue, 1, 0.5)
                    r = int(r * self.brightness)
                    g = int(g * self.brightness)
                    b = int(b * self.brightness)
                    np[xy_to_i(x,y)] = (r//BRIGHT_DIV, g//BRIGHT_DIV, b//BRIGHT_DIV)
            np.write()
            
        elif self.mode == "ripple":
            self.phase += 0.5 * self.speed
            cx = 8; cy = 8
            for y in range(16):
                for x in range(16):
                    dist = math.sqrt((x-cx)**2 + (y-cy)**2)
                    val = math.sin(dist - self.phase) * 127 + 128
                    val = int(val * self.brightness)
                    np[xy_to_i(x,y)] = (0, val//BRIGHT_DIV, val//BRIGHT_DIV)
            np.write()
            
        elif self.mode == "matrix":
            # Fade existing
            factor = 0.85 - (0.15 * self.speed)
            if factor < 0: factor = 0
            for y in range(16):
                for x in range(16):
                    idx = xy_to_i(x,y)
                    # rough approximation of fading Green by 85%
                    curr = np[idx][1] * BRIGHT_DIV
                    curr = int(curr * factor)
                    np[idx] = (0, curr//BRIGHT_DIV, 0)
            
            import random
            val = int(255 * self.brightness)
            for x in range(16):
                y = int(self.drops[x])
                if 0 <= y < 16:
                    np[xy_to_i(x,y)] = (0, val//BRIGHT_DIV, 0)
                self.drops[x] += self.speed
                if self.drops[x] > 16 and random.random() > 0.8:
                    self.drops[x] = random.randint(-16, -1)
            np.write()

anim = Animator()

# Save/Load
STATE_FILE = "state.bin"

def apply_frame(payload):
    idx = 6
    for y in range(16):
        for x in range(16):
            np[xy_to_i(x, y)] = (payload[idx]//BRIGHT_DIV, payload[idx+1]//BRIGHT_DIV, payload[idx+2]//BRIGHT_DIV)
            idx += 3
    np.write()

def load_state():
    try:
        with open(STATE_FILE, "rb") as f:
            data = f.read()
            if data.startswith(b"FRM1"):
                anim.set(None)
                apply_frame(data)
            elif data.startswith(b"SAVEANIM "):
                cmd_str = data.decode('utf-8').strip()
                parts = cmd_str.split(" ")
                name = parts[1]
                speed = float(parts[2]) if len(parts) > 2 else 1.0
                brightness = float(parts[3]) if len(parts) > 3 else 1.0
                anim.set(name, speed, brightness)
    except:
        pass # No save state or error

def save_state(data):
    try:
        with open(STATE_FILE, "wb") as f:
            f.write(data)
    except:
        pass

poll = select.poll()
poll.register(sys.stdin, select.POLLIN)

def read_exact(n, timeout_ms=1500):
    buf = bytearray(n)
    got = 0
    start = time.ticks_ms()
    while got < n:
        if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
            return None # Timed out!
        if poll.poll(1):
            c = sys.stdin.buffer.read(1)
            if c:
                buf[got] = c[0]
                got += 1
    return buf

def run():
    load_state()
    print("READY")
    line_buf = bytearray()
    
    save_next_frame = False
    is_on = True
    last_btn_state = 1
    
    while True:
        # Check BOOT button
        btn_state = boot_btn.value()
        if btn_state == 0 and last_btn_state == 1:
            # Button pressed (falling edge)
            is_on = not is_on
            if not is_on:
                clear()
                anim.set(None)
            else:
                load_state()
            time.sleep_ms(50) # debounce
        last_btn_state = btn_state

        if is_on:
            anim.step()

        if poll.poll(10):
            c_bytes = sys.stdin.buffer.read(1)
            if not c_bytes:
                continue
                
            c = c_bytes[0]
            if c == 10: # '\n' newline
                try:
                    cmd = line_buf.decode('utf-8').strip()
                except:
                    cmd = ""
                line_buf = bytearray()
                
                if cmd == "PING":
                    print("READY")
                elif cmd == "CLEAR":
                    anim.set(None)
                    save_next_frame = False
                    clear()
                    is_on = True
                    print("OK")
                elif cmd == "TEST":
                    anim.set(None)
                    save_next_frame = False
                    test_pattern()
                    is_on = True
                    print("OK")
                elif cmd == "SAVEFRAME":
                    save_next_frame = True
                    print("OK")
                elif cmd.startswith("SAVEANIM "):
                    parts = cmd.split(" ")
                    anim_name = parts[1]
                    speed = float(parts[2]) if len(parts) > 2 else 1.0
                    brightness = float(parts[3]) if len(parts) > 3 else 1.0
                    save_state(cmd.encode('utf-8'))
                    anim.set(anim_name, speed, brightness)
                    is_on = True
                    print("OK")
                elif cmd == "FRAME":
                    payload = read_exact(774, 1500)
                    
                    if payload is None:
                        print("ERR: Timeout")
                        continue
                        
                    if payload[0:4] == b'FRM1':
                        length = payload[4] | (payload[5] << 8)
                        if length == 768:
                            anim.set(None)
                            is_on = True
                            apply_frame(payload)
                            
                            if save_next_frame:
                                save_state(payload)
                                save_next_frame = False
                                
                            print("OK")
                        else:
                            print("ERR: Len")
                    else:
                        print("ERR: Magic")
            else:
                line_buf.append(c)
                # Auto-clear buffer if it gets full of garbage
                if len(line_buf) > 128:
                    line_buf = bytearray()

try:
    run()
except Exception as e:
    micropython.kbd_intr(3)
    raise e