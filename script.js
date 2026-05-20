let port, reader, writer;
let keepReading = false;
let isConnected = false;
let isReady = false;
let isSending = false;
let pendingFrame = false;
let pingInterval = null;

const GRID_SIZE = 16;
let grid = Array.from({ length: GRID_SIZE }, () => Array(GRID_SIZE).fill({ r: 0, g: 0, b: 0 }));

// UI Elements
const btnConnect = document.getElementById('btnConnect');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const canvas = document.getElementById('matrixCanvas');
const ctx = canvas.getContext('2d', { willReadFrequently: true });
const colorPicker = document.getElementById('colorPicker');
const logWindow = document.getElementById('logWindow');
const chkFlipX = document.getElementById('chkFlipX');
const chkFlipY = document.getElementById('chkFlipY');
const PIXEL_SIZE = canvas.width / GRID_SIZE;

// Tools
let currentTool = 'draw'; // 'draw', 'fill', 'erase'
const tools = {
    draw: document.getElementById('btnToolDraw'),
    fill: document.getElementById('btnToolFill'),
    erase: document.getElementById('btnToolErase')
};

let isDrawingMouse = false;

// i18n
const i18n = {
    en: {
        'title': 'Matrix Controller',
        'connect': 'Connect',
        'disconnect': 'Disconnect',
        'disconnected': 'Disconnected',
        'tools': 'Drawing Tools',
        'examples': 'Examples',
        'util': 'Utilities',
        'import': 'Import Image',
        'clear': 'Clear Matrix',
        'test': 'Test Pattern',
        'flipx': 'Flip X',
        'flipy': 'Flip Y',
        'logs': 'Terminal Logs',
    },
    fr: {
        'title': 'Contrôleur Matrice',
        'connect': 'Connecter',
        'disconnect': 'Déconnecter',
        'disconnected': 'Déconnecté',
        'tools': 'Outils de dessin',
        'examples': 'Exemples',
        'util': 'Utilitaires',
        'import': 'Importer Image',
        'clear': 'Tout effacer',
        'test': 'Motif Test',
        'flipx': 'Miroir X',
        'flipy': 'Miroir Y',
        'logs': 'Traces Terminal',
    }
};

let currentLang = 'en';

function setLang(lang) {
    currentLang = lang;
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (i18n[lang][key]) el.innerText = i18n[lang][key];
    });
    // Ensure button state is correctly translated if not "connect"
    if (isConnected) {
        document.querySelector('#btnConnect span').innerText = i18n[lang]['disconnect'];
    }
}

document.getElementById('langSelect').addEventListener('change', (e) => setLang(e.target.value));

document.getElementById('btnAbout').addEventListener('click', () => document.getElementById('aboutModal').classList.remove('hidden'));
document.getElementById('btnCloseModal').addEventListener('click', () => document.getElementById('aboutModal').classList.add('hidden'));

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    initExamples();
    drawGrid();
    setControlsDisabled(true);
});

// Examples
function loadImageToGrid(imgSource) {
    const img = new Image();
    img.crossOrigin = "Anonymous";
    img.onload = () => {
        const offscreen = document.createElement('canvas');
        offscreen.width = GRID_SIZE; offscreen.height = GRID_SIZE;
        const octx = offscreen.getContext('2d', { willReadFrequently: true });
        
        octx.fillStyle = '#000';
        octx.fillRect(0, 0, GRID_SIZE, GRID_SIZE);
        octx.drawImage(img, 0, 0, GRID_SIZE, GRID_SIZE);
        
        const imgData = octx.getImageData(0, 0, GRID_SIZE, GRID_SIZE).data;

        let i = 0;
        for (let y = 0; y < GRID_SIZE; y++) {
            for (let x = 0; x < GRID_SIZE; x++) {
                grid[y][x] = { r: imgData[i], g: imgData[i+1], b: imgData[i+2] };
                i += 4;
            }
        }
        drawGrid();
        requestFrameSend();
    };
    img.src = imgSource;
}

function initExamples() {
    document.querySelectorAll('.example-img').forEach(imgEl => {
        imgEl.addEventListener('click', (e) => {
            loadImageToGrid(e.target.src);
        });
    });
}

// Logging (Compressed)
let lastLogText = '';
let lastLogElement = null;
let lastLogCount = 1;

function log(msg, type = 'sys') {
    if (msg === lastLogText && lastLogElement) {
        lastLogCount++;
        let badge = lastLogElement.querySelector('.badge-count');
        if (!badge) {
            badge = document.createElement('span');
            badge.className = 'badge-count';
            lastLogElement.appendChild(badge);
        }
        badge.innerText = `x${lastLogCount}`;
        return;
    }

    lastLogText = msg;
    lastLogCount = 1;

    const div = document.createElement('div');
    if (type) div.className = type;
    
    const txtNode = document.createElement('span');
    txtNode.innerText = msg;
    div.appendChild(txtNode);
    
    logWindow.appendChild(div);
    lastLogElement = div;

    if (logWindow.children.length > 200) logWindow.removeChild(logWindow.firstChild);
    logWindow.scrollTop = logWindow.scrollHeight;
}

document.getElementById('btnClearLog').addEventListener('click', () => {
    logWindow.innerHTML = '';
});

// Canvas Drawing
function drawGrid() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let y = 0; y < GRID_SIZE; y++) {
        for (let x = 0; x < GRID_SIZE; x++) {
            const color = grid[y][x];
            ctx.fillStyle = `rgb(${color.r}, ${color.g}, ${color.b})`;
            ctx.fillRect(x * PIXEL_SIZE, y * PIXEL_SIZE, PIXEL_SIZE, PIXEL_SIZE);
        }
    }
    
    // Grid overlay (Subtle)
    ctx.strokeStyle = '#27272a'; // var(--bg-elevated)
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i <= GRID_SIZE; i++) {
        ctx.moveTo(i * PIXEL_SIZE, 0); ctx.lineTo(i * PIXEL_SIZE, canvas.height);
        ctx.moveTo(0, i * PIXEL_SIZE); ctx.lineTo(canvas.width, i * PIXEL_SIZE);
    }
    ctx.stroke();
}

// Tool Selection
Object.keys(tools).forEach(toolName => {
    tools[toolName].addEventListener('click', () => {
        currentTool = toolName;
        Object.values(tools).forEach(t => t.classList.remove('active'));
        tools[toolName].classList.add('active');
    });
});

// Quick Colors
document.getElementById('quickColors').addEventListener('click', (e) => {
    if (e.target.classList.contains('c-swatch')) {
        colorPicker.value = e.target.getAttribute('data-c');
        if (currentTool === 'erase') {
            currentTool = 'draw';
            Object.values(tools).forEach(t => t.classList.remove('active'));
            tools.draw.classList.add('active');
        }
    }
});

// Interaction Logic
function hexToRgb(hex) {
    return {
        r: parseInt(hex.substring(1, 3), 16),
        g: parseInt(hex.substring(3, 5), 16),
        b: parseInt(hex.substring(5, 7), 16)
    };
}

function colorsMatch(c1, c2) {
    return c1.r === c2.r && c1.g === c2.g && c1.b === c2.b;
}

function floodFill(startX, startY, targetColor) {
    const startColor = grid[startY][startX];
    if (colorsMatch(startColor, targetColor)) return;

    const stack = [[startX, startY]];
    
    while(stack.length > 0) {
        const [x, y] = stack.pop();
        
        if (x >= 0 && x < GRID_SIZE && y >= 0 && y < GRID_SIZE) {
            if (colorsMatch(grid[y][x], startColor)) {
                grid[y][x] = { ...targetColor };
                stack.push([x + 1, y]);
                stack.push([x - 1, y]);
                stack.push([x, y + 1]);
                stack.push([x, y - 1]);
            }
        }
    }
}

let lastDrawPos = null;

function bresenhamDraw(x0, y0, x1, y1, drawColor) {
    const dx = Math.abs(x1 - x0);
    const dy = Math.abs(y1 - y0);
    const sx = (x0 < x1) ? 1 : -1;
    const sy = (y0 < y1) ? 1 : -1;
    let err = dx - dy;

    while(true) {
        if (x0 >= 0 && x0 < GRID_SIZE && y0 >= 0 && y0 < GRID_SIZE) {
            grid[y0][x0] = { ...drawColor };
        }

        if ((x0 === x1) && (y0 === y1)) break;
        const e2 = 2 * err;
        if (e2 > -dy) { err -= dy; x0 += sx; }
        if (e2 < dx) { err += dx; y0 += sy; }
    }
}

function interactCanvas(event) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    
    const x = Math.floor(((event.clientX - rect.left) * scaleX) / PIXEL_SIZE);
    const y = Math.floor(((event.clientY - rect.top) * scaleY) / PIXEL_SIZE);

    if (x >= 0 && x < GRID_SIZE && y >= 0 && y < GRID_SIZE) {
        // Middle click = Color Picker / Eyedropper
        if (event.button === 1 || event.buttons === 4) {
            const c = grid[y][x];
            colorPicker.value = "#" + (1 << 24 | c.r << 16 | c.g << 8 | c.b).toString(16).slice(1);
            currentTool = 'draw';
            Object.values(tools).forEach(t => t.classList.remove('active'));
            if (tools.draw) tools.draw.classList.add('active');
            return;
        }

        const isRightClick = event.buttons === 2 || event.button === 2;
        let drawColor = hexToRgb(colorPicker.value);
        if (currentTool === 'erase' || isRightClick) drawColor = {r:0, g:0, b:0};

        if (currentTool === 'fill' && !isRightClick) {
            if (event.type === 'mousedown') {
                floodFill(x, y, drawColor);
                drawGrid();
                requestFrameSend();
            }
        } else {
            // Bresenham interpolation to prevent dotted lines on fast drag
            if (event.type === 'mousedown') {
                grid[y][x] = drawColor;
                lastDrawPos = {x, y};
            } else if (event.type === 'mousemove' && lastDrawPos) {
                bresenhamDraw(lastDrawPos.x, lastDrawPos.y, x, y, drawColor);
                lastDrawPos = {x, y};
            }
            drawGrid();
            requestFrameSend();
        }
    } else {
        lastDrawPos = null; // Left grid bounds
    }
}

// Prevent context menu to allow right click to erase safely
canvas.addEventListener('contextmenu', e => e.preventDefault());
// Prevent middle mouse autoscroll
canvas.addEventListener('mousedown', e => { if (e.button === 1) e.preventDefault(); });

canvas.addEventListener('mousedown', (e) => { 
    isDrawingMouse = true; 
    interactCanvas(e); 
});

canvas.addEventListener('mousemove', (e) => {
    if (!isDrawingMouse || (currentTool === 'fill' && e.buttons !== 2)) {
        lastDrawPos = null;
        return;
    }
    interactCanvas(e);
});
window.addEventListener('mouseup', () => { isDrawingMouse = false; lastDrawPos = null; });
canvas.addEventListener('mouseleave', () => { isDrawingMouse = false; lastDrawPos = null; });

// Toggles triggers frame updates
if (chkFlipX) chkFlipX.addEventListener('change', () => requestFrameSend());
if (chkFlipY) chkFlipY.addEventListener('change', () => requestFrameSend());

// Import Image
document.getElementById('imageInput').addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    loadImageToGrid(URL.createObjectURL(file));
    e.target.value = '';
});

// Action Buttons
document.getElementById('btnClear').addEventListener('click', () => {
    grid = Array.from({ length: GRID_SIZE }, () => Array(GRID_SIZE).fill({ r: 0, g: 0, b: 0 }));
    drawGrid();
    sendTextCommand("CLEAR\n");
});

document.getElementById('btnTest').addEventListener('click', () => {
    sendTextCommand("TEST\n");
});

// UI states
function setControlsDisabled(disabled) {
    document.querySelectorAll('.action-btn, #chkFlipX, #chkFlipY').forEach(el => {
        if(el.tagName === 'LABEL') {
            el.style.pointerEvents = disabled ? 'none' : 'auto';
            el.style.opacity = disabled ? '0.5' : '1';
        } else {
            el.disabled = disabled;
        }
    });
}

function updateConnectionUI(state, text) {
    statusDot.className = 'dot ' + state;
    document.getElementById('statusText').innerText = text;
    
    if (state === 'disconnected') {
        btnConnect.innerHTML = `<i class="fa-solid fa-plug"></i> <span>${i18n[currentLang]['connect']}</span>`;
        btnConnect.classList.add('btn-primary');
        setControlsDisabled(true);
    } else {
        btnConnect.innerHTML = `<i class="fa-solid fa-plug"></i> <span>${i18n[currentLang]['disconnect']}</span>`;
        btnConnect.classList.remove('btn-primary');
    }
}

// -------------------------------------------------------------
// WEBSERIAL API & LOGIC FROM `docs.md`
// -------------------------------------------------------------

async function writeRaw(uint8Array) {
    if (!port || !port.writable) return;
    writer = port.writable.getWriter();
    try { await writer.write(uint8Array); }
    catch (err) { log(`Write err: ${err.message}`, 'err'); }
    finally { writer.releaseLock(); }
}

async function sendTextCommand(cmd) {
    if (!isConnected) return;
    const encoder = new TextEncoder();
    await writeRaw(encoder.encode(cmd));
    if(cmd.trim()) log(`${cmd.trim()}`, 'tx');
}

function requestFrameSend() {
    if (!isConnected || !isReady) return;
    if (isSending) {
        pendingFrame = true;
        return;
    }
    sendCurrentFrame();
}

async function sendCurrentFrame() {
    isSending = true; pendingFrame = false;

    const textHeader = new TextEncoder().encode("FRAME\n");
    const binSize = 4 + 2 + 768; // Magic(4) + Len(2) + Pixels(768)
    const binBuffer = new ArrayBuffer(binSize);
    const view = new DataView(binBuffer);
    const u8 = new Uint8Array(binBuffer);

    u8[0] = 70; u8[1] = 82; u8[2] = 77; u8[3] = 49; // FRM1
    view.setUint16(4, 768, true); // Little-Endian 768

    let offset = 6;
    const flipX = chkFlipX ? chkFlipX.checked : false;
    const flipY = chkFlipY ? chkFlipY.checked : false;

    for (let y = 0; y < GRID_SIZE; y++) {
        for (let x = 0; x < GRID_SIZE; x++) {
            let mapX = flipX ? (GRID_SIZE - 1 - x) : x;
            let mapY = flipY ? (GRID_SIZE - 1 - y) : y;
            let color = grid[mapY][mapX];
            u8[offset++] = color.r;
            u8[offset++] = color.g;
            u8[offset++] = color.b;
        }
    }

    const combined = new Uint8Array(textHeader.length + u8.length);
    combined.set(textHeader, 0);
    combined.set(u8, textHeader.length);

    await writeRaw(combined);
}

async function readLoop() {
    let lineBuffer = "";
    while (port.readable && keepReading) {
        const decoder = new TextDecoderStream();
        const readableStreamClosed = port.readable.pipeTo(decoder.writable);
        reader = decoder.readable.getReader();

        try {
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                lineBuffer += value;
                let lines = lineBuffer.split('\n');
                lineBuffer = lines.pop(); // keep incomplete line

                for (let line of lines) {
                    line = line.trim();
                    if (!line) continue;
                    log(`${line}`, 'rx');

                    if (line === "READY") {
                        if (!isReady) {
                            isReady = true;
                            if (pingInterval) clearInterval(pingInterval);
                            updateConnectionUI('ready', 'Lock Acquired');
                            setControlsDisabled(false);
                            requestFrameSend(); // Send initial state empty (or if UI was drawn before)
                        }
                    }
                    else if (line === "OK" || line.startsWith("ERR")) {
                        isSending = false;
                        if (pendingFrame) sendCurrentFrame();
                    }
                }
            }
        } catch (error) {
            log(`Lost: ${error.message}`, 'err');
            break;
        } finally {
            reader.releaseLock();
            decoder.writable.abort().catch(()=>{});
        }
    }
    await disconnect();
}

async function connect() {
    if (!navigator.serial) {
        alert("WebSerial is not supported in this browser. Use Chrome or Edge.");
        return;
    }
    
    try {
        port = await navigator.serial.requestPort();
        await port.open({ baudRate: 115200 });
        await port.setSignals({ dataTerminalReady: true, requestToSend: true });

        keepReading = true;
        isConnected = true;
        isReady = false;

        updateConnectionUI('syncing', 'Syncing...');
        
        log("Port opened. Pinging ESP32...");
        readLoop();

        pingInterval = setInterval(() => {
            if (isConnected && !isReady) {
                sendTextCommand("\n\nPING\n");
            }
        }, 1000);

    } catch (err) {
        log(`Connect Error: ${err.message}`, 'err');
        updateConnectionUI('disconnected', 'Disconnected');
    }
}

async function disconnect() {
    keepReading = false;
    isConnected = false;
    isReady = false;
    isSending = false;
    pendingFrame = false;
    
    if (pingInterval) clearInterval(pingInterval);

    if (reader) await reader.cancel().catch(()=>{});
    if (port) await port.close().catch(()=>{});

    updateConnectionUI('disconnected', 'Disconnected');
    log("Disconnected.", 'sys');
}

btnConnect.addEventListener('click', () => {
    if (!isConnected) {
        connect();
    } else {
        disconnect();
    }
});
// -------------------------------------------------------------
// GAME OF LIFE (Konami Code)
// -------------------------------------------------------------
const konamiSequence = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a'];
let konamiIndex = 0;
let golInterval = null;
let golPlaying = false;

document.addEventListener('keydown', (e) => {
    if (e.key === konamiSequence[konamiIndex] || e.key.toLowerCase() === konamiSequence[konamiIndex]) {
        konamiIndex++;
        if (konamiIndex === konamiSequence.length) {
            konamiIndex = 0;
            activateConway();
        }
    } else {
        konamiIndex = 0;
    }
});

function activateConway() {
    log("Konami Code Accepted: Game of Life Unlocked", "rx");
    document.getElementById('golControls').classList.remove('hidden');
    colorPicker.value = '#f59e0b'; // yellow (alive)
    currentTool = 'draw';
    Object.values(tools).forEach(t => t.classList.remove('active'));
    tools.draw.classList.add('active');
}

const btnGolPlay = document.getElementById('btnGolPlay');
const golSpeed = document.getElementById('golSpeed');

function stepGameOfLife() {
    const nextGrid = Array.from({ length: GRID_SIZE }, () => Array(GRID_SIZE).fill({ r: 0, g: 0, b: 0 }));
    let changes = false;

    for (let y = 0; y < GRID_SIZE; y++) {
        for (let x = 0; x < GRID_SIZE; x++) {
            let aliveNeighbors = 0;
            for (let dy = -1; dy <= 1; dy++) {
                for (let dx = -1; dx <= 1; dx++) {
                    if (dx === 0 && dy === 0) continue;
                    const nx = x + dx, ny = y + dy;
                    if (nx >= 0 && nx < GRID_SIZE && ny >= 0 && ny < GRID_SIZE) {
                        const c = grid[ny][nx];
                        if (c.r > 0 || c.g > 0 || c.b > 0) aliveNeighbors++;
                    }
                }
            }

            const c = grid[y][x];
            const isAlive = c.r > 0 || c.g > 0 || c.b > 0;
            
            if (isAlive && (aliveNeighbors === 2 || aliveNeighbors === 3)) {
                nextGrid[y][x] = { ...c };
            } else if (!isAlive && aliveNeighbors === 3) {
                nextGrid[y][x] = { r: 245, g: 158, b: 11 }; // Yellow
                changes = true;
            } else if (isAlive) {
                changes = true; // Died
            }
        }
    }

    if (changes) {
        grid = nextGrid;
        drawGrid();
        requestFrameSend();
    }
}

function getGolInterval() {
    // 1 -> 1040ms, 100 -> 50ms
    return Math.max(20, 1050 - (parseInt(golSpeed.value) * 10));
}

if (btnGolPlay) {
    btnGolPlay.addEventListener('click', () => {
        golPlaying = !golPlaying;
        if (golPlaying) {
            btnGolPlay.innerHTML = '<i class="fa-solid fa-pause"></i> Pause';
            golInterval = setInterval(stepGameOfLife, getGolInterval());
        } else {
            btnGolPlay.innerHTML = '<i class="fa-solid fa-play"></i> Play/Pause';
            clearInterval(golInterval);
        }
    });

    golSpeed.addEventListener('input', () => {
        if (golPlaying) {
            clearInterval(golInterval);
            golInterval = setInterval(stepGameOfLife, getGolInterval());
        }
    });
}
