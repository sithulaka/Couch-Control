/**
 * Couch Control - WebSocket Client
 * Real-time bidirectional remote desktop control
 */

(function () {
    'use strict';

    // ===== DOM Elements =====
    const canvas = document.getElementById('screen');
    const ctx = canvas.getContext('2d');
    const loading = document.getElementById('loading');
    const loadingText = document.getElementById('loading-text');
    const clickIndicator = document.getElementById('click-indicator');
    const keyboardPanel = document.getElementById('keyboard-panel');
    const textInput = document.getElementById('text-input');
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    const container = document.getElementById('container');

    // ===== State =====
    let ws = null;
    let connected = false;
    let reconnectTimeout = null;

    // Modes
    // isZoomLocked = true  -> Mouse Mode (Desktop Interaction Enabled, Pan/Zoom Disabled)
    // isZoomLocked = false -> View Mode  (Desktop Interaction Disabled, Pan/Zoom Enabled)
    let isZoomLocked = true;
    let isDragMode = false;

    // Zoom/Pan
    let zoomLevel = 1.0;
    let panX = 0;
    let panY = 0;
    let pinchStartDist = 0;
    let panStart = { x: 0, y: 0 };

    // Touch/mouse state
    let touchState = {
        startTime: 0,
        startX: 0,
        startY: 0,
        isDragging: false,
        clientX: 0,
        clientY: 0
    };
    let longPressTimer = null;
    let lastTapTime = 0;

    // ===== WebSocket Connection =====

    function connect() {
        const wsPort = parseInt(location.port || 80) + 1;
        const wsUrl = `ws://${location.hostname}:${wsPort}`;

        console.log('Connecting to', wsUrl);
        loadingText.textContent = 'Connecting...';
        loading.classList.remove('hidden');

        try {
            ws = new WebSocket(wsUrl);
            ws.binaryType = 'arraybuffer';
        } catch (e) {
            console.error('WebSocket creation failed:', e);
            scheduleReconnect();
            return;
        }

        ws.onopen = () => {
            console.log('WebSocket connected');
            connected = true;
            loading.classList.add('hidden');
            statusDot.classList.add('connected');
            statusText.textContent = 'Connected';
            if (reconnectTimeout) {
                clearTimeout(reconnectTimeout);
                reconnectTimeout = null;
            }
        };

        ws.onmessage = (event) => {
            if (event.data instanceof ArrayBuffer) {
                renderFrame(event.data);
            }
        };

        ws.onclose = () => {
            connected = false;
            statusDot.classList.remove('connected');
            statusText.textContent = 'Disconnected';
            scheduleReconnect();
        };

        ws.onerror = (error) => {
            ws.close();
        };
    }

    function scheduleReconnect() {
        loading.classList.remove('hidden');
        loadingText.textContent = 'Reconnecting...';
        if (reconnectTimeout) clearTimeout(reconnectTimeout);
        reconnectTimeout = setTimeout(connect, 2000);
    }

    function send(data) {
        if (connected && ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(data));
        }
    }

    // ===== Frame Rendering & Zoom =====

    function renderFrame(arrayBuffer) {
        const blob = new Blob([arrayBuffer], { type: 'image/jpeg' });
        const url = URL.createObjectURL(blob);
        const img = new Image();

        img.onload = () => {
            if (canvas.width !== img.width || canvas.height !== img.height) {
                canvas.width = img.width;
                canvas.height = img.height;
            }
            ctx.drawImage(img, 0, 0);
            URL.revokeObjectURL(url);
        };

        img.onerror = () => URL.revokeObjectURL(url);
        img.src = url;
    }

    function updateTransform() {
        // Clamp zoom
        zoomLevel = Math.max(1.0, Math.min(5.0, zoomLevel));
        canvas.style.transform = `translate(${panX}px, ${panY}px) scale(${zoomLevel})`;
    }

    // ===== Input Handling =====

    function getCoords(event) {
        const rect = canvas.getBoundingClientRect();
        let clientX, clientY;

        if (event.touches && event.touches.length > 0) {
            clientX = event.touches[0].clientX;
            clientY = event.touches[0].clientY;
        } else if (event.changedTouches && event.changedTouches.length > 0) {
            clientX = event.changedTouches[0].clientX;
            clientY = event.changedTouches[0].clientY;
        } else {
            clientX = event.clientX;
            clientY = event.clientY;
        }

        // Note: getBoundingClientRect includes scale transforms, so this 0-1 logic works
        // even when zoomed!
        return {
            x: Math.max(0, Math.min(1, (clientX - rect.left) / rect.width)),
            y: Math.max(0, Math.min(1, (clientY - rect.top) / rect.height)),
            clientX,
            clientY
        };
    }

    function getDistance(e) {
        if (e.touches.length < 2) return 0;
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        return Math.sqrt(dx * dx + dy * dy);
    }

    function getMidpoint(e) {
        if (e.touches.length < 2) return { x: 0, y: 0 };
        return {
            x: (e.touches[0].clientX + e.touches[1].clientX) / 2,
            y: (e.touches[0].clientY + e.touches[1].clientY) / 2
        };
    }

    function showClickIndicator(x, y, color = null) {
        clickIndicator.style.left = x + 'px';
        clickIndicator.style.top = y + 'px';
        if (color) clickIndicator.style.borderColor = color;
        else clickIndicator.style.borderColor = 'rgba(255, 255, 255, 0.8)';

        clickIndicator.classList.remove('active');
        void clickIndicator.offsetWidth;
        clickIndicator.classList.add('active');
    }

    function handlePointerDown(event) {
        if (event.target.closest('#control-bar') || event.target.closest('#keyboard-panel')) return;
        event.preventDefault();

        // Check Mode Logic
        if (!isZoomLocked) {
            // VIEW MODE (Unlocked): Pan/Zoom Logic
            // 1 Finger = Pan Start
            // 2 Finger = Pinch Start
            if (event.touches && event.touches.length === 2) {
                pinchStartDist = getDistance(event);
                const mid = getMidpoint(event);
                panStart = { x: mid.x - panX, y: mid.y - panY };
            } else {
                // 1 Finger Pan
                const coords = event.touches ? event.touches[0] : event;
                panStart = { x: coords.clientX - panX, y: coords.clientY - panY };
            }
            return; // No Desktop Interaction
        }

        // MOUSE MODE (Locked): Desktop Interaction

        const coords = getCoords(event);
        touchState = {
            startTime: Date.now(),
            startX: coords.x,
            startY: coords.y,
            lastX: coords.x,
            lastY: coords.y,
            isDragging: false,
            clientX: coords.clientX,
            clientY: coords.clientY
        };

        if (isDragMode) {
            // Drag Mode: Immediate Mouse Down + Move
            send({ type: 'move', x: coords.x, y: coords.y });
            send({ type: 'mousedown', button: 1 });
            touchState.isDragging = true;
        } else {
            // Normal Mode: Jump and Wait
            send({ type: 'move', x: coords.x, y: coords.y });

            // Long Press for Right Click
            longPressTimer = setTimeout(() => {
                send({ type: 'click', x: coords.x, y: coords.y, button: 3 });
                showClickIndicator(coords.clientX, coords.clientY, '#e94560');
                longPressTimer = null;
                touchState.startTime = 0;
            }, 500);
        }
    }

    function handlePointerMove(event) {
        if (event.target.closest('#control-bar') || event.target.closest('#keyboard-panel')) return;
        event.preventDefault();

        if (!isZoomLocked) {
            // VIEW MODE: Pan/Zoom
            if (event.touches && event.touches.length === 2) {
                // 2 Finger Zoom
                const dist = getDistance(event);
                if (pinchStartDist > 0) {
                    const delta = dist - pinchStartDist;
                    zoomLevel += delta * 0.005;
                    pinchStartDist = dist;
                }
                // And Pan (midpoint)
                const mid = getMidpoint(event);
                panX = mid.x - panStart.x;
                panY = mid.y - panStart.y;
            } else {
                // 1 Finger Pan
                const coords = event.touches ? event.touches[0] : event;
                panX = coords.clientX - panStart.x;
                panY = coords.clientY - panStart.y;
            }
            updateTransform();
            return;
        }

        // MOUSE MODE
        if (!touchState.startTime) return;

        const coords = getCoords(event);
        const dx = Math.abs(coords.x - touchState.startX);
        const dy = Math.abs(coords.y - touchState.startY);

        if (!touchState.isDragging && (dx > 0.005 || dy > 0.005)) {
            if (longPressTimer) {
                clearTimeout(longPressTimer);
                longPressTimer = null;
            }
            if (!isDragMode) touchState.isDragging = true;
        }

        if (touchState.isDragging || isDragMode) {
            send({ type: 'move', x: coords.x, y: coords.y });
        }
    }

    function handlePointerUp(event) {
        if (event.target.closest('#control-bar') || event.target.closest('#keyboard-panel')) return;
        event.preventDefault();

        if (!isZoomLocked) return; // View Mode has no End action usually (just stop panning)

        // Mouse Mode Actions
        if (longPressTimer) clearTimeout(longPressTimer);

        if (isDragMode) {
            send({ type: 'mouseup', button: 1 });
            touchState.startTime = 0;
            return;
        }

        const duration = Date.now() - touchState.startTime;

        if (!touchState.isDragging && longPressTimer !== null && duration < 500) {
            const now = Date.now();
            if (now - lastTapTime < 300) {
                send({ type: 'dblclick', x: touchState.startX, y: touchState.startY });
                lastTapTime = 0;
            } else {
                send({ type: 'click', x: touchState.startX, y: touchState.startY, button: 1 });
                lastTapTime = now;
            }
            showClickIndicator(touchState.clientX, touchState.clientY);
        }

        touchState.startTime = 0;
        touchState.isDragging = false;
        longPressTimer = null;
    }

    // ===== Event Listeners =====

    container.addEventListener('touchstart', handlePointerDown, { passive: false });
    container.addEventListener('touchmove', handlePointerMove, { passive: false });
    container.addEventListener('touchend', handlePointerUp, { passive: false });
    container.addEventListener('touchcancel', handlePointerUp, { passive: false });

    container.addEventListener('mousedown', handlePointerDown);
    container.addEventListener('mousemove', handlePointerMove);
    container.addEventListener('mouseup', handlePointerUp);
    container.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        const coords = getCoords(e);
        send({ type: 'click', x: coords.x, y: coords.y, button: 3 });
    });
    container.addEventListener('wheel', (e) => {
        e.preventDefault();
        const direction = e.deltaY > 0 ? 'down' : 'up';
        send({ type: 'scroll', direction, amount: 3 });
    }, { passive: false });

    // ===== UI Controls =====

    // Toggle Drag Mode
    document.getElementById('btn-drag').addEventListener('click', function () {
        isDragMode = !isDragMode;
        this.classList.toggle('active', isDragMode);
    });

    // Mode Toggle (Zoom/Control)
    const btnMode = document.getElementById('btn-mode');
    const modeIcon = document.getElementById('mode-icon');
    const modeLabel = btnMode.querySelector('.btn-label');

    function updateModeUI() {
        if (isZoomLocked) {
            // Mouse Mode -> Show "Zoom" icon (indicating ability to switch to Zoom)
            modeIcon.textContent = '🔍';
            modeLabel.textContent = 'Zoom';
            btnMode.classList.remove('active');
        } else {
            // View Mode -> Show "Lock" icon
            modeIcon.textContent = '🔒';
            modeLabel.textContent = 'Lock';
            btnMode.classList.add('active');
        }
    }

    // Initialize UI
    updateModeUI();

    btnMode.addEventListener('click', function () {
        isZoomLocked = !isZoomLocked;
        updateModeUI();
    });

    // Reset Button
    document.getElementById('btn-reset').addEventListener('click', () => {
        zoomLevel = 1.0;
        panX = 0;
        panY = 0;
        updateTransform();
        // Optionally lock zoom on reset?
        // isZoomLocked = true; updateModeUI();
    });

    // Keyboard & Other Controls
    document.getElementById('btn-keyboard').addEventListener('click', () => {
        keyboardPanel.classList.toggle('visible');
        if (keyboardPanel.classList.contains('visible')) textInput.focus();
    });

    document.getElementById('btn-send').addEventListener('click', () => {
        if (textInput.value) {
            send({ type: 'type', text: textInput.value });
            textInput.value = '';
            textInput.focus();
        }
    });

    textInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            if (textInput.value) {
                send({ type: 'type', text: textInput.value });
                textInput.value = '';
            }
            send({ type: 'keypress', key: 'Enter' });
        }
    });

    document.querySelectorAll('.key-btn[data-key]').forEach(btn => {
        btn.addEventListener('click', () => {
            send({ type: 'keypress', key: btn.dataset.key });
        });
    });

    document.getElementById('select-quality').addEventListener('change', function () {
        send({ type: 'settings', quality: parseInt(this.value) });
    });

    document.getElementById('select-scale').addEventListener('change', function () {
        send({ type: 'settings', scale: parseFloat(this.value) });
    });

    document.getElementById('btn-fullscreen').addEventListener('click', () => {
        if (document.fullscreenElement) document.exitFullscreen();
        else document.documentElement.requestFullscreen().catch(() => { });
    });

    document.getElementById('btn-reconnect').addEventListener('click', () => {
        if (ws) ws.close();
        connect();
    });

    connect();
})();
