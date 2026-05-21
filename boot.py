import machine
import neopixel
import sys
import select
import time
import micropython

# CRITICAL: Disable Ctrl+C so binary data doesn't crash the script back to REPL
micropython.kbd_intr(-1)

PIN_NUM = 5
NUM_LEDS = 256
pin = machine.Pin(PIN_NUM, machine.Pin.OUT)
np = neopixel.NeoPixel(pin, NUM_LEDS)

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

poll = select.poll()
poll.register(sys.stdin, select.POLLIN)

def read_exact(n, timeout_ms=1500):
    buf = bytearray(n)
    got = 0
    start = time.ticks_ms()
    while got < n:
        if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
            return None # Timed out!
        if poll.poll(10):
            # FIX: Read exactly 1 byte at a time. 
            # Asking for more causes ESP32-C3 Native USB to permanently lock up!
            c = sys.stdin.buffer.read(1)
            if c:
                buf[got] = c[0]
                got += 1
    return buf

def run():
    print("READY")
    line_buf = bytearray()
    
    while True:
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
                    clear()
                    print("OK")
                elif cmd == "TEST":
                    test_pattern()
                    print("OK")
                elif cmd == "FRAME":
                    payload = read_exact(774, 1500)
                    
                    if payload is None:
                        print("ERR: Timeout")
                        continue
                        
                    if payload[0:4] == b'FRM1':
                        length = payload[4] | (payload[5] << 8)
                        if length == 768:
                            idx = 6
                            for y in range(16):
                                for x in range(16):
                                    np[xy_to_i(x, y)] = (payload[idx]//BRIGHT_DIV, payload[idx+1]//BRIGHT_DIV, payload[idx+2]//BRIGHT_DIV)
                                    idx += 3
                            np.write()
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