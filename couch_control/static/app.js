/**
 * Couch Control - WebSocket Client
 * Real-time bidirectional remote desktop control
 */

(function() {
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
    
    // Touch/mouse state
    let touchState = {
        startTime: 0,
        startX: 0,
        startY: 0,
        lastX: 0,
        lastY: 0,
        isDragging: false
    };
    let longPressTimer = null;
    let lastTapTime = 0;

    // ===== WebSocket Connection =====
    
    function connect() {
        // WebSocket runs on HTTP port + 1
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
            
            // Clear any pending reconnect
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
            console.log('WebSocket closed');
            connected = false;
            statusDot.classList.remove('connected');
            statusText.textContent = 'Disconnected';
            scheduleReconnect();
        };
        
        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            ws.close();
        };
    }
    
    function scheduleReconnect() {
        loading.classList.remove('hidden');
        loadingText.textContent = 'Reconnecting...';
        
        if (reconnectTimeout) {
            clearTimeout(reconnectTimeout);
        }
        reconnectTimeout = setTimeout(connect, 2000);
    }
    
    function send(data) {
        if (connected && ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(data));
        }
    }

    // ===== Frame Rendering =====
    
    function renderFrame(arrayBuffer) {
        const blob = new Blob([arrayBuffer], { type: 'image/jpeg' });
        const url = URL.createObjectURL(blob);
        const img = new Image();
        
        img.onload = () => {
            // Resize canvas if needed
            if (canvas.width !== img.width || canvas.height !== img.height) {
                canvas.width = img.width;
                canvas.height = img.height;
            }
            
            // Draw frame
            ctx.drawImage(img, 0, 0);
            
            // Cleanup
            URL.revokeObjectURL(url);
        };
        
        img.onerror = () => {
            URL.revokeObjectURL(url);
        };
        
        img.src = url;
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
        
        return {
            x: Math.max(0, Math.min(1, (clientX - rect.left) / rect.width)),
            y: Math.max(0, Math.min(1, (clientY - rect.top) / rect.height)),
            clientX,
            clientY
        };
    }
    
    function showClickIndicator(x, y) {
        clickIndicator.style.left = x + 'px';
        clickIndicator.style.top = y + 'px';
        clickIndicator.classList.remove('active');
        // Force reflow
        void clickIndicator.offsetWidth;
        clickIndicator.classList.add('active');
    }
    
    function handlePointerDown(event) {
        // Ignore if on control elements
        if (event.target.closest('#control-bar') || event.target.closest('#keyboard-panel')) {
            return;
        }
        
        event.preventDefault();
        
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
        
        // Long press for right click
        longPressTimer = setTimeout(() => {
            send({ type: 'click', x: coords.x, y: coords.y, button: 3 });
            showClickIndicator(coords.clientX, coords.clientY);
            longPressTimer = null;
        }, 500);
    }
    
    function handlePointerMove(event) {
        if (!touchState.startTime) return;
        
        // Ignore if on control elements
        if (event.target.closest('#control-bar') || event.target.closest('#keyboard-panel')) {
            return;
        }
        
        event.preventDefault();
        
        const coords = getCoords(event);
        const dx = Math.abs(coords.x - touchState.startX);
        const dy = Math.abs(coords.y - touchState.startY);
        
        // Start dragging if moved enough
        if (!touchState.isDragging && (dx > 0.02 || dy > 0.02)) {
            touchState.isDragging = true;
            if (longPressTimer) {
                clearTimeout(longPressTimer);
                longPressTimer = null;
            }
        }
        
        // Send move event
        if (touchState.isDragging) {
            send({ type: 'move', x: coords.x, y: coords.y });
            touchState.lastX = coords.x;
            touchState.lastY = coords.y;
        }
    }
    
    function handlePointerUp(event) {
        // Ignore if on control elements
        if (event.target.closest('#control-bar') || event.target.closest('#keyboard-panel')) {
            return;
        }
        
        event.preventDefault();
        
        if (longPressTimer) {
            clearTimeout(longPressTimer);
        }
        
        const duration = Date.now() - touchState.startTime;
        
        // Short tap = left click
        if (!touchState.isDragging && longPressTimer !== null && duration < 500) {
            const now = Date.now();
            
            // Double tap detection
            if (now - lastTapTime < 300) {
                send({ type: 'dblclick', x: touchState.startX, y: touchState.startY });
                lastTapTime = 0;
            } else {
                send({ type: 'click', x: touchState.startX, y: touchState.startY, button: 1 });
                lastTapTime = now;
            }
            
            showClickIndicator(touchState.clientX, touchState.clientY);
        }
        
        // Reset state
        touchState.startTime = 0;
        touchState.isDragging = false;
        longPressTimer = null;
    }
    
    // ===== Event Listeners =====
    
    // Touch events
    container.addEventListener('touchstart', handlePointerDown, { passive: false });
    container.addEventListener('touchmove', handlePointerMove, { passive: false });
    container.addEventListener('touchend', handlePointerUp, { passive: false });
    container.addEventListener('touchcancel', handlePointerUp, { passive: false });
    
    // Mouse events
    container.addEventListener('mousedown', handlePointerDown);
    container.addEventListener('mousemove', handlePointerMove);
    container.addEventListener('mouseup', handlePointerUp);
    container.addEventListener('mouseleave', handlePointerUp);
    
    // Right click
    container.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        const coords = getCoords(e);
        send({ type: 'click', x: coords.x, y: coords.y, button: 3 });
        showClickIndicator(coords.clientX, coords.clientY);
    });
    
    // Scroll wheel
    container.addEventListener('wheel', (e) => {
        e.preventDefault();
        const direction = e.deltaY > 0 ? 'down' : 'up';
        send({ type: 'scroll', direction, amount: 3 });
    }, { passive: false });

    // ===== Keyboard Panel =====
    
    document.getElementById('btn-keyboard').addEventListener('click', () => {
        keyboardPanel.classList.toggle('visible');
        if (keyboardPanel.classList.contains('visible')) {
            textInput.focus();
        }
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
    
    // Key buttons
    document.querySelectorAll('.key-btn[data-key]').forEach(btn => {
        btn.addEventListener('click', () => {
            send({ type: 'keypress', key: btn.dataset.key });
        });
    });

    // ===== Control Bar =====
    
    document.getElementById('select-quality').addEventListener('change', function() {
        send({ type: 'settings', quality: parseInt(this.value) });
    });
    
    document.getElementById('select-scale').addEventListener('change', function() {
        send({ type: 'settings', scale: parseFloat(this.value) });
    });
    
    document.getElementById('btn-fullscreen').addEventListener('click', () => {
        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else {
            document.documentElement.requestFullscreen().catch(() => {});
        }
    });
    
    document.getElementById('btn-reconnect').addEventListener('click', () => {
        if (ws) {
            ws.close();
        }
        connect();
    });

    // ===== Keyboard Shortcuts (Desktop) =====
    
    document.addEventListener('keydown', (e) => {
        // Don't capture if typing in input
        if (document.activeElement === textInput) return;
        
        // Only forward when keyboard panel is hidden
        if (!keyboardPanel.classList.contains('visible')) {
            // Let browser handle some keys
            if (e.key === 'F5' || e.key === 'F11' || e.key === 'F12') return;
            if (e.ctrlKey && (e.key === 'r' || e.key === 'w' || e.key === 't')) return;
            
            e.preventDefault();
            
            let key = e.key;
            if (e.ctrlKey) key = 'ctrl+' + key.toLowerCase();
            else if (e.altKey) key = 'alt+' + key.toLowerCase();
            
            send({ type: 'keypress', key });
        }
    });

    // ===== Connection Check =====
    
    setInterval(() => {
        if (!connected) return;
        
        fetch('/ping')
            .then(res => {
                if (!res.ok) {
                    statusText.textContent = 'Error';
                }
            })
            .catch(() => {
                statusText.textContent = 'Offline';
            });
    }, 10000);

    // ===== Initialize =====
    
    connect();
    console.log('🛋️ Couch Control WebSocket client loaded');
    
})();
