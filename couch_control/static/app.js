/**
 * Couch Control — WebSocket Client
 * All traffic on a single port via /ws endpoint.
 */

(function () {
    'use strict';

    // ── DOM ──────────────────────────────────────────────────────────────────
    const canvas      = document.getElementById('screen');
    const ctx         = canvas.getContext('2d');
    const loading     = document.getElementById('loading');
    const loadingText = document.getElementById('loading-text');
    const clickInd    = document.getElementById('click-indicator');
    const kbdPanel    = document.getElementById('keyboard-panel');
    const textInput   = document.getElementById('text-input');
    const statusDot   = document.getElementById('status-dot');
    const statusText  = document.getElementById('status-text');
    const statusFps   = document.getElementById('status-fps');
    const statusPing  = document.getElementById('status-ping');
    const container   = document.getElementById('container');

    // PIN dialog
    const pinOverlay  = document.getElementById('pin-overlay');
    const pinInput    = document.getElementById('pin-input');
    const pinError    = document.getElementById('pin-error');
    const btnPinSub   = document.getElementById('btn-pin-submit');

    // Tunnel banner
    const tunnelBanner   = document.getElementById('tunnel-banner');
    const tunnelUrlText  = document.getElementById('tunnel-url-text');
    const btnCopyTunnel  = document.getElementById('btn-copy-tunnel');
    const btnCloseTunnel = document.getElementById('btn-close-tunnel-banner');

    // Settings panel
    const settingsPanel  = document.getElementById('settings-panel');
    const sliderQuality  = document.getElementById('slider-quality');
    const labelQuality   = document.getElementById('label-quality');
    const selectScaleSt  = document.getElementById('select-scale-settings');
    const selectTheme    = document.getElementById('select-theme');
    const infoVersion    = document.getElementById('info-version');
    const infoClients    = document.getElementById('info-clients');
    const infoTunnel     = document.getElementById('info-tunnel');
    const controlQuality = document.getElementById('select-quality');

    // ── State ────────────────────────────────────────────────────────────────
    let ws            = null;
    let connected     = false;
    let pinRequired   = false;
    let pendingPinResolve = null;
    let reconnectTimeout  = null;
    let reconnectDelay    = 2000;

    // Interaction modes
    let isZoomLocked = true;   // true = Mouse Mode, false = View Mode
    let isDragMode   = false;

    // Pan/zoom
    let zoomLevel = 1.0;
    let panX = 0, panY = 0;
    let pinchStartDist = 0;
    let panStart = { x: 0, y: 0 };

    // Touch state
    let touchState = {
        startTime: 0, startX: 0, startY: 0,
        lastX: 0, lastY: 0,
        isDragging: false, didLongPress: false,
        clientX: 0, clientY: 0,
        twoFingerStartY: null,
    };
    let longPressTimer = null;
    let lastTapTime    = 0;

    // Perf metrics
    let frameCount    = 0;
    let fpsLastTime   = performance.now();
    let latencyMs     = 0;
    let pendingDecode  = false;   // prevent frame pile-up

    // Move event throttle
    let pendingMove   = null;
    let moveScheduled = false;

    // Theme
    let currentTheme = localStorage.getItem('cc-theme') || 'auto';
    applyTheme(currentTheme);

    // ── WebSocket connection ─────────────────────────────────────────────────

    function wsUrl() {
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${proto}//${location.host}/ws`;
    }

    function connect() {
        loadingText.textContent = 'Connecting...';
        loading.classList.remove('hidden');

        try {
            ws = new WebSocket(wsUrl());
            ws.binaryType = 'arraybuffer';
        } catch (e) {
            scheduleReconnect();
            return;
        }

        ws.onopen = () => {
            console.log('WebSocket connected');
            // Server will send server_info first; we wait for that.
        };

        ws.onmessage = (event) => {
            if (event.data instanceof ArrayBuffer) {
                renderFrame(event.data);
            } else {
                handleServerMessage(JSON.parse(event.data));
            }
        };

        ws.onclose = () => {
            connected = false;
            statusDot.classList.remove('connected');
            statusText.textContent = 'Disconnected';
            scheduleReconnect();
        };

        ws.onerror = () => { ws.close(); };
    }

    function handleServerMessage(msg) {
        switch (msg.type) {
            case 'server_info':
                pinRequired = msg.pin_required;
                infoVersion.textContent = `Version: ${msg.version || '?'}`;
                if (msg.tunnel_url) showTunnelBanner(msg.tunnel_url);
                if (pinRequired) {
                    showPinDialog().then(pin => {
                        send({ type: 'auth', pin });
                        finalizeConnect();
                    });
                } else {
                    finalizeConnect();
                }
                break;

            case 'pong':
                latencyMs = Date.now() - msg.t;
                statusPing.textContent = `${latencyMs}ms`;
                break;

            case 'tunnel_url':
                showTunnelBanner(msg.url);
                infoTunnel.textContent = `Tunnel: ${msg.url}`;
                break;
        }
    }

    function finalizeConnect() {
        connected = true;
        reconnectDelay = 2000;
        loading.classList.add('hidden');
        statusDot.classList.add('connected');
        statusText.textContent = 'Connected';
        if (reconnectTimeout) { clearTimeout(reconnectTimeout); reconnectTimeout = null; }

        // Start latency ping every 5s
        setInterval(() => { if (connected) send({ type: 'ping', t: Date.now() }); }, 5000);
    }

    function scheduleReconnect() {
        loading.classList.remove('hidden');
        loadingText.textContent = `Reconnecting in ${Math.round(reconnectDelay / 1000)}s...`;
        if (reconnectTimeout) clearTimeout(reconnectTimeout);
        reconnectTimeout = setTimeout(() => {
            reconnectDelay = Math.min(reconnectDelay * 1.5, 30000);
            connect();
        }, reconnectDelay);
    }

    function send(data) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(data));
        }
    }

    // ── PIN dialog ───────────────────────────────────────────────────────────

    function showPinDialog() {
        pinOverlay.classList.remove('hidden');
        pinError.classList.add('hidden');
        pinInput.value = '';
        setTimeout(() => pinInput.focus(), 100);
        return new Promise(resolve => { pendingPinResolve = resolve; });
    }

    function submitPin() {
        const pin = pinInput.value.trim();
        if (!pin) return;
        pinOverlay.classList.add('hidden');
        if (pendingPinResolve) { pendingPinResolve(pin); pendingPinResolve = null; }
    }

    btnPinSub.addEventListener('click', submitPin);
    pinInput.addEventListener('keydown', e => { if (e.key === 'Enter') submitPin(); });

    // ── Tunnel banner ────────────────────────────────────────────────────────

    function showTunnelBanner(url) {
        tunnelUrlText.textContent = `Remote: ${url}`;
        tunnelBanner.classList.remove('hidden');
        infoTunnel.textContent = `Tunnel: ${url}`;
    }

    btnCopyTunnel.addEventListener('click', () => {
        const url = tunnelUrlText.textContent.replace('Remote: ', '');
        navigator.clipboard.writeText(url).catch(() => {});
        btnCopyTunnel.textContent = 'Copied!';
        setTimeout(() => { btnCopyTunnel.textContent = 'Copy'; }, 2000);
    });

    btnCloseTunnel.addEventListener('click', () => {
        tunnelBanner.classList.add('hidden');
    });

    // ── Frame rendering ──────────────────────────────────────────────────────

    function renderFrame(arrayBuffer) {
        if (pendingDecode) return; // Drop if previous frame still decoding
        pendingDecode = true;

        const blob = new Blob([arrayBuffer], { type: 'image/jpeg' });

        if ('createImageBitmap' in window) {
            createImageBitmap(blob).then(bitmap => {
                if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
                    canvas.width  = bitmap.width;
                    canvas.height = bitmap.height;
                }
                ctx.drawImage(bitmap, 0, 0);
                bitmap.close();
                pendingDecode = false;
                countFrame();
            }).catch(() => { pendingDecode = false; });
        } else {
            // Fallback for older browsers
            const url = URL.createObjectURL(blob);
            const img = new Image();
            img.onload = () => {
                if (canvas.width !== img.width || canvas.height !== img.height) {
                    canvas.width  = img.width;
                    canvas.height = img.height;
                }
                ctx.drawImage(img, 0, 0);
                URL.revokeObjectURL(url);
                pendingDecode = false;
                countFrame();
            };
            img.onerror = () => { URL.revokeObjectURL(url); pendingDecode = false; };
            img.src = url;
        }
    }

    function countFrame() {
        frameCount++;
        const now = performance.now();
        const elapsed = now - fpsLastTime;
        if (elapsed >= 1000) {
            const fps = Math.round((frameCount * 1000) / elapsed);
            statusFps.textContent = `${fps}fps`;
            frameCount = 0;
            fpsLastTime = now;
        }
    }

    // ── Zoom/pan ─────────────────────────────────────────────────────────────

    function updateTransform() {
        zoomLevel = Math.max(1.0, Math.min(5.0, zoomLevel));
        canvas.style.transform = `translate(${panX}px, ${panY}px) scale(${zoomLevel})`;
    }

    // ── Coordinate helper ────────────────────────────────────────────────────

    function getCoords(event) {
        const rect = canvas.getBoundingClientRect();
        let cx, cy;

        if (event.touches && event.touches.length > 0) {
            cx = event.touches[0].clientX;
            cy = event.touches[0].clientY;
        } else if (event.changedTouches && event.changedTouches.length > 0) {
            cx = event.changedTouches[0].clientX;
            cy = event.changedTouches[0].clientY;
        } else {
            cx = event.clientX;
            cy = event.clientY;
        }

        return {
            x: Math.max(0, Math.min(1, (cx - rect.left) / rect.width)),
            y: Math.max(0, Math.min(1, (cy - rect.top) / rect.height)),
            clientX: cx, clientY: cy,
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
            y: (e.touches[0].clientY + e.touches[1].clientY) / 2,
        };
    }

    function showClickIndicator(x, y, color) {
        clickInd.style.left = x + 'px';
        clickInd.style.top  = y + 'px';
        clickInd.style.borderColor = color || 'rgba(255,255,255,0.8)';
        clickInd.classList.remove('active');
        void clickInd.offsetWidth; // reflow to restart animation
        clickInd.classList.add('active');
    }

    // ── Throttled mouse move ─────────────────────────────────────────────────

    function scheduledMove() {
        if (pendingMove) {
            send(pendingMove);
            pendingMove = null;
        }
        moveScheduled = false;
    }

    function sendMove(x, y) {
        pendingMove = { type: 'move', x, y };
        if (!moveScheduled) {
            moveScheduled = true;
            requestAnimationFrame(scheduledMove);
        }
    }

    // ── Pointer event handlers ───────────────────────────────────────────────

    function handlePointerDown(event) {
        if (event.target.closest('#control-bar') ||
            event.target.closest('#keyboard-panel')) return;
        event.preventDefault();

        if (!isZoomLocked) {
            // VIEW MODE: start pan or pinch
            if (event.touches && event.touches.length === 2) {
                pinchStartDist = getDistance(event);
                const mid = getMidpoint(event);
                panStart = { x: mid.x - panX, y: mid.y - panY };
            } else {
                const c = event.touches ? event.touches[0] : event;
                panStart = { x: c.clientX - panX, y: c.clientY - panY };
            }
            return;
        }

        // MOUSE MODE
        // Two-finger in Mouse Mode = scroll
        if (event.touches && event.touches.length === 2) {
            const midY = (event.touches[0].clientY + event.touches[1].clientY) / 2;
            touchState.twoFingerStartY = midY;
            return;
        }

        const coords = getCoords(event);
        touchState = {
            startTime: Date.now(),
            startX: coords.x, startY: coords.y,
            lastX: coords.x, lastY: coords.y,
            isDragging: false, didLongPress: false,
            clientX: coords.clientX, clientY: coords.clientY,
            twoFingerStartY: null,
        };

        if (isDragMode) {
            send({ type: 'move', x: coords.x, y: coords.y });
            send({ type: 'mousedown', button: 1 });
            touchState.isDragging = true;
        } else {
            send({ type: 'move', x: coords.x, y: coords.y });
            longPressTimer = setTimeout(() => {
                touchState.didLongPress = true;
                longPressTimer = null;
                send({ type: 'click', x: coords.x, y: coords.y, button: 3 });
                showClickIndicator(coords.clientX, coords.clientY, '#e94560');
            }, 500);
        }
    }

    function handlePointerMove(event) {
        if (event.target.closest('#control-bar') ||
            event.target.closest('#keyboard-panel')) return;
        event.preventDefault();

        if (!isZoomLocked) {
            // VIEW MODE
            if (event.touches && event.touches.length === 2) {
                const dist = getDistance(event);
                if (pinchStartDist > 0) {
                    zoomLevel += (dist - pinchStartDist) * 0.005;
                    pinchStartDist = dist;
                }
                const mid = getMidpoint(event);
                panX = mid.x - panStart.x;
                panY = mid.y - panStart.y;
            } else {
                const c = event.touches ? event.touches[0] : event;
                panX = c.clientX - panStart.x;
                panY = c.clientY - panStart.y;
            }
            updateTransform();
            return;
        }

        // MOUSE MODE — two-finger scroll
        if (event.touches && event.touches.length === 2 && touchState.twoFingerStartY !== null) {
            const midY = (event.touches[0].clientY + event.touches[1].clientY) / 2;
            const dy = midY - touchState.twoFingerStartY;
            if (Math.abs(dy) > 12) {
                send({ type: 'scroll', direction: dy < 0 ? 'up' : 'down', amount: 3 });
                touchState.twoFingerStartY = midY;
            }
            return;
        }

        if (!touchState.startTime) return;

        const coords = getCoords(event);
        const dx = Math.abs(coords.x - touchState.startX);
        const dy = Math.abs(coords.y - touchState.startY);

        if (!touchState.isDragging && (dx > 0.005 || dy > 0.005)) {
            if (longPressTimer) { clearTimeout(longPressTimer); longPressTimer = null; }
            if (!isDragMode) touchState.isDragging = true;
        }

        if (touchState.isDragging || isDragMode) {
            sendMove(coords.x, coords.y);
        }
    }

    function handlePointerUp(event) {
        if (event.target.closest('#control-bar') ||
            event.target.closest('#keyboard-panel')) return;
        event.preventDefault();

        if (!isZoomLocked) return;

        if (longPressTimer) { clearTimeout(longPressTimer); longPressTimer = null; }

        if (isDragMode) {
            send({ type: 'mouseup', button: 1 });
            touchState.startTime = 0;
            return;
        }

        if (touchState.didLongPress) {
            touchState.startTime = 0;
            touchState.isDragging = false;
            touchState.didLongPress = false;
            return;
        }

        const duration = Date.now() - touchState.startTime;
        if (!touchState.isDragging && duration < 500) {
            const now = Date.now();
            if (now - lastTapTime < 300) {
                send({ type: 'dblclick', x: touchState.startX, y: touchState.startY });
                lastTapTime = 0;
            } else {
                send({ type: 'click', x: touchState.startX, y: touchState.startY, button: 1 });
                showClickIndicator(touchState.clientX, touchState.clientY);
                lastTapTime = now;
            }
        }

        touchState.startTime = 0;
        touchState.isDragging = false;
        touchState.didLongPress = false;
        touchState.twoFingerStartY = null;
    }

    // ── Event listeners ──────────────────────────────────────────────────────

    container.addEventListener('touchstart',  handlePointerDown, { passive: false });
    container.addEventListener('touchmove',   handlePointerMove, { passive: false });
    container.addEventListener('touchend',    handlePointerUp,   { passive: false });
    container.addEventListener('touchcancel', handlePointerUp,   { passive: false });

    container.addEventListener('mousedown', handlePointerDown);
    container.addEventListener('mousemove', handlePointerMove);
    container.addEventListener('mouseup',   handlePointerUp);

    container.addEventListener('contextmenu', e => {
        e.preventDefault();
        const coords = getCoords(e);
        send({ type: 'click', ...coords, button: 3 });
    });

    container.addEventListener('wheel', e => {
        e.preventDefault();
        send({ type: 'scroll', direction: e.deltaY > 0 ? 'down' : 'up', amount: 3 });
    }, { passive: false });

    // ── Control bar buttons ──────────────────────────────────────────────────

    document.getElementById('btn-drag').addEventListener('click', function () {
        isDragMode = !isDragMode;
        this.classList.toggle('active', isDragMode);
    });

    const btnMode  = document.getElementById('btn-mode');
    const modeIcon = document.getElementById('mode-icon');
    const modeLbl  = btnMode.querySelector('.btn-label');

    function updateModeUI() {
        if (isZoomLocked) {
            modeIcon.textContent = '🔍'; modeLbl.textContent = 'Zoom';
            btnMode.classList.remove('active');
        } else {
            modeIcon.textContent = '🔒'; modeLbl.textContent = 'Lock';
            btnMode.classList.add('active');
        }
    }
    updateModeUI();

    btnMode.addEventListener('click', () => { isZoomLocked = !isZoomLocked; updateModeUI(); });

    document.getElementById('btn-reset').addEventListener('click', () => {
        zoomLevel = 1.0; panX = 0; panY = 0;
        updateTransform();
    });

    document.getElementById('btn-keyboard').addEventListener('click', () => {
        kbdPanel.classList.toggle('visible');
        if (kbdPanel.classList.contains('visible')) textInput.focus();
    });

    document.getElementById('btn-fullscreen').addEventListener('click', () => {
        if (document.fullscreenElement) document.exitFullscreen();
        else document.documentElement.requestFullscreen().catch(() => {});
    });

    document.getElementById('btn-reconnect').addEventListener('click', () => {
        if (ws) ws.close();
        reconnectDelay = 2000;
        connect();
    });

    // Quality select in control bar
    controlQuality.addEventListener('change', function () {
        send({ type: 'settings', quality: parseInt(this.value) });
        sliderQuality.value = this.value;
        labelQuality.textContent = this.value;
    });

    // ── Keyboard panel ───────────────────────────────────────────────────────

    document.getElementById('btn-send').addEventListener('click', () => {
        if (textInput.value) {
            send({ type: 'type', text: textInput.value });
            textInput.value = '';
            textInput.focus();
        }
    });

    textInput.addEventListener('keydown', e => {
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

    // Clipboard paste from phone
    document.getElementById('btn-clipboard-paste').addEventListener('click', async () => {
        try {
            const text = await navigator.clipboard.readText();
            if (text) {
                send({ type: 'clipboard', text });
            }
        } catch (e) {
            // Clipboard API might be unavailable or user denied
            const text = prompt('Paste your text here (clipboard API unavailable):');
            if (text) send({ type: 'clipboard', text });
        }
    });

    // ── Settings panel ───────────────────────────────────────────────────────

    document.getElementById('btn-settings').addEventListener('click', () => {
        settingsPanel.classList.remove('hidden');
        fetchStatus();
    });

    document.getElementById('btn-close-settings').addEventListener('click', () => {
        settingsPanel.classList.add('hidden');
    });

    settingsPanel.addEventListener('click', e => {
        if (e.target === settingsPanel) settingsPanel.classList.add('hidden');
    });

    sliderQuality.addEventListener('input', function () {
        labelQuality.textContent = this.value;
    });
    sliderQuality.addEventListener('change', function () {
        send({ type: 'settings', quality: parseInt(this.value) });
        // Sync the control-bar select
        const v = parseInt(this.value);
        const closest = [40, 60, 75, 90].reduce((a, b) => Math.abs(b - v) < Math.abs(a - v) ? b : a);
        controlQuality.value = String(closest);
    });

    selectScaleSt.addEventListener('change', function () {
        send({ type: 'settings', scale: parseFloat(this.value) });
    });

    selectTheme.addEventListener('change', function () {
        applyTheme(this.value);
        localStorage.setItem('cc-theme', this.value);
    });
    selectTheme.value = currentTheme;

    function fetchStatus() {
        fetch('/status').then(r => r.json()).then(d => {
            infoClients.textContent = `Clients: ${d.clients}`;
            if (d.tunnel) {
                infoTunnel.textContent = `Tunnel: ${d.tunnel}`;
            }
        }).catch(() => {});
    }

    // ── Theme ────────────────────────────────────────────────────────────────

    function applyTheme(theme) {
        currentTheme = theme;
        if (theme === 'auto') {
            document.documentElement.removeAttribute('data-theme');
        } else {
            document.documentElement.setAttribute('data-theme', theme);
        }
    }

    // ── Start ────────────────────────────────────────────────────────────────

    connect();

})();
