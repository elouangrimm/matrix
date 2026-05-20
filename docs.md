Here is a comprehensive API and protocol specification. You can copy and paste this entire message to another AI (like ChatGPT, Claude, etc.) to have them build a fully customized, beautiful web dashboard. 

It covers exactly how the communication works, the exact byte structures needed, and the strict synchronization rules required to keep the ESP32-C3 stable.

***

# 16x16 LED Matrix WebSerial API Specification

## 1. Overview
This document outlines the WebSerial communication protocol for controlling a MicroPython-powered ESP32-C3 driving a 16x16 NeoPixel LED matrix. 

The protocol uses a **hybrid ASCII + Binary structure** over USB CDC. It employs a strict **Request-Response (Mutex) Handshake** to prevent USB buffer overflows, frame tearing, and device crashes.

## 2. Connection Parameters
*   **API:** WebSerial (`navigator.serial`)
*   **Baud Rate:** `115200`
*   **Hardware Flow Control:** None required, but **DTR and RTS must be asserted** upon opening the port (Native USB requirement for ESP32).
    ```javascript
    await port.open({ baudRate: 115200 });
    await port.setSignals({ dataTerminalReady: true, requestToSend: true });
    ```

## 3. Connection & Synchronization Flow
Because the ESP32 might be in an unknown state or have garbage bytes in its buffer when the browser connects, the frontend must establish a clean sync before sending any matrix data.

1.  **Open Port & Start Read Loop:** Start reading from the serial port immediately.
2.  **The PING Loop:** Send `\n\nPING\n` every 1000ms. 
    *   *Note: The preceding `\n\n` is intentional. It flushes any partial commands left in the ESP32's buffer.*
3.  **Wait for READY:** Once the ESP32 parses the PING, it will respond with `READY\n` (ASCII).
4.  **Unlock UI:** Stop the PING loop. The device is now ready to receive frames or commands.

## 4. Text Commands (ASCII)
All simple commands are ASCII text terminated by a newline (`\n`). 
Wait for the expected response before sending the next command.

| Command | Action | Expected Response |
| :--- | :--- | :--- |
| `PING\n` | Checks if device is alive | `READY\n` |
| `CLEAR\n` | Turns off all 256 LEDs | `OK\n` |
| `TEST\n` | Displays 4 colored corners | `OK\n` |

## 5. The FRAME Protocol (Binary Pixel Data)
To send drawing data, the system uses a hybrid packet. You must send an ASCII header followed *immediately* by a binary payload. 

**⚠️ CRITICAL RULE:** The ASCII command and the Binary Payload **MUST** be concatenated into a single `Uint8Array` and sent in a single `writer.write()` call. If sent separately, USB chunking delays may trigger the ESP32's 1500ms safety timeout.

### Frame Packet Structure (780 bytes total):
1.  **Text Trigger (6 bytes):** `FRAME\n` (ASCII)
2.  **Magic Header (4 bytes):** `FRM1` (ASCII / `[70, 82, 77, 49]`)
3.  **Payload Length (2 bytes):** `768` as a Little-Endian `uint16`. (`[0x00, 0x03]`)
4.  **Pixel Payload (768 bytes):** Sequential RGB values. 

### Payload Data Mapping (Row-Major, Top-Left Origin):
*   The array must contain exactly 768 bytes (256 pixels × 3 colors: R, G, B).
*   **Origin (0,0):** Top-Left of the image/canvas.
*   **Progression:** Left-to-Right, Top-to-Bottom. (Standard HTML Canvas / 2D Array mapping).
*   *Note to Frontend Dev: Do NOT implement zigzag/serpentine logic in JavaScript. The MicroPython firmware handles physical hardware abstraction automatically.*
*   **Format:** `[R0, G0, B0, R1, G1, B1, ... R255, G255, B255]`
*   **Values:** `0` to `255`. (The ESP32 firmware scales the brightness down automatically, so JS should send full 0-255 RGB values).

### Frame Responses
After sending a FRAME packet, the ESP32 will respond with one of the following (terminated by `\n`):
*   `OK` – Frame rendered successfully.
*   `ERR: Timeout` – ESP32 didn't receive all 774 binary bytes within 1.5s.
*   `ERR: Len` – The 2-byte length header did not equal 768.
*   `ERR: Magic` – The `FRM1` header was missing or corrupted.

## 6. Strict Handshaking & Mutex (Throttling)
The ESP32 does not have infinite memory. The frontend must implement a strict send-lock (Mutex).

1.  **State Boolean:** Maintain an `isSending` flag.
2.  **Send Lock:** When sending a `FRAME\n` packet, set `isSending = true`.
3.  **Prevent Overlap:** If the user draws on the canvas while `isSending == true`, **DO NOT** send another frame. Instead, set a flag `pendingFrame = true`.
4.  **Release Lock:** When the serial reader receives `OK\n` (or an `ERR...\n`), set `isSending = false`.
5.  **Process Queue:** If `pendingFrame == true` when the lock is released, immediately compile the *current* state of the canvas and send it, resetting `pendingFrame = false` and locking `isSending = true` again.

*This inherently limits the browser's FPS to exactly what the hardware can handle, preventing the "Device Lost" disconnects and buffer tearing.*

## 7. Graceful Disconnects
If the ESP32 is physically unplugged or crashes, WebSerial will throw a `NetworkError: The device has been lost` inside the read loop.
*   The JS read loop must be wrapped in a `try...catch`.
*   On error, safely call `reader.cancel()`, `reader.releaseLock()`, and reset the UI state to Disconnected so the user can click "Connect" again without refreshing the web page.