"""
WebSocket server for Couch Control.
Provides real-time bidirectional streaming using WebSocket binary frames.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Optional, Set

from aiohttp import web
import websockets
from websockets.server import serve as ws_serve

from .capture import ScreenCapture, get_capture, close_capture
from .config import Config, get_config
from .input_handler import InputHandler, get_input_handler, translate_key


class CouchControlServer:
    """
    WebSocket-based server for real-time remote desktop control.
    
    Features:
    - WebSocket binary frame streaming (real-time)
    - Bidirectional communication on single connection
    - Mouse and keyboard input handling
    - Auto-timeout for security
    - PIN authentication (optional)
    """
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize the server."""
        self.config = config or get_config()
        
        # Track active WebSocket connections
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.last_activity = time.time()
        
        # Capture and input instances (lazy loaded)
        self._capture: Optional[ScreenCapture] = None
        self._input: Optional[InputHandler] = None
        
        # Server instances
        self.http_runner: Optional[web.AppRunner] = None
        self.ws_server = None
        
        # Shutdown event
        self.shutdown_event = asyncio.Event()
        
        # Setup HTTP app for static files
        self.http_app = web.Application()
        self._setup_http_routes()
    
    def _setup_http_routes(self) -> None:
        """Setup HTTP routes for static files."""
        self.http_app.router.add_get("/", self._handle_index)
        self.http_app.router.add_get("/ping", self._handle_ping)
        self.http_app.router.add_get("/status", self._handle_status)
        
        # Serve static files
        static_path = Path(__file__).parent / "static"
        if static_path.exists():
            self.http_app.router.add_static("/static/", static_path)
    
    def _get_capture(self) -> ScreenCapture:
        """Get or create screen capture instance."""
        if self._capture is None:
            self._capture = get_capture(
                monitor=self.config.monitor,
                quality=self.config.quality,
                scale=self.config.scale,
                use_turbojpeg=self.config.use_turbojpeg
            )
        return self._capture
    
    def _get_input(self) -> InputHandler:
        """Get or create input handler instance."""
        if self._input is None:
            self._input = get_input_handler()
            capture = self._get_capture()
            self._input.set_screen_size(capture.width, capture.height)
        return self._input
    
    def _update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = time.time()
    
    async def _handle_index(self, request: web.Request) -> web.Response:
        """Serve the main HTML page."""
        self._update_activity()
        
        static_path = Path(__file__).parent / "static" / "index.html"
        if static_path.exists():
            return web.FileResponse(static_path)
        
        return web.Response(
            text=self._get_fallback_html(),
            content_type="text/html"
        )
    
    async def _handle_ping(self, request: web.Request) -> web.Response:
        """Simple ping endpoint."""
        return web.Response(text="pong")
    
    async def _handle_status(self, request: web.Request) -> web.Response:
        """Return server status."""
        capture = self._get_capture()
        
        status = {
            "status": "running",
            "version": "2.0.0",
            "protocol": "websocket",
            "clients": len(self.clients),
            "screen": {
                "width": capture.width,
                "height": capture.height,
                "scaled_width": capture.scaled_width,
                "scaled_height": capture.scaled_height,
            },
            "settings": {
                "quality": self.config.quality,
                "fps": self.config.fps,
                "scale": self.config.scale,
            },
        }
        
        return web.json_response(status)
    
    async def _websocket_handler(self, websocket: websockets.WebSocketServerProtocol) -> None:
        """Handle a WebSocket connection."""
        self._update_activity()
        self.clients.add(websocket)
        
        print(f"Client connected: {websocket.remote_address}")
        
        try:
            # Start frame streaming task
            frame_task = asyncio.create_task(self._stream_frames(websocket))
            
            # Handle incoming messages (input events)
            try:
                async for message in websocket:
                    self._update_activity()
                    await self._handle_input(message)
            except websockets.exceptions.ConnectionClosed:
                pass
            
            # Cancel frame streaming
            frame_task.cancel()
            try:
                await frame_task
            except asyncio.CancelledError:
                pass
                
        finally:
            self.clients.discard(websocket)
            print(f"Client disconnected: {websocket.remote_address}")
    
    async def _stream_frames(self, websocket: websockets.WebSocketServerProtocol) -> None:
        """Stream frames to a WebSocket client."""
        capture = self._get_capture()
        frame_interval = self.config.frame_interval
        
        try:
            while True:
                start_time = time.time()
                
                # Capture and encode frame
                jpeg_bytes = capture.capture_jpeg()
                
                # Send as binary WebSocket message
                try:
                    await websocket.send(jpeg_bytes)
                except websockets.exceptions.ConnectionClosed:
                    break
                
                # Maintain FPS
                elapsed = time.time() - start_time
                sleep_time = max(0.001, frame_interval - elapsed)
                await asyncio.sleep(sleep_time)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Frame streaming error: {e}")
    
    async def _handle_input(self, message: str) -> None:
        """Handle an input event from WebSocket."""
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return
        
        event_type = data.get("type", "")
        
        try:
            input_handler = self._get_input()
            
            if event_type == "click":
                x = float(data.get("x", 0))
                y = float(data.get("y", 0))
                button = int(data.get("button", 1))
                input_handler.click_at(x, y, button, normalized=True)
            
            elif event_type == "dblclick":
                x = float(data.get("x", 0))
                y = float(data.get("y", 0))
                input_handler.move_mouse(x, y, normalized=True)
                input_handler.double_click()
            
            elif event_type == "move":
                x = float(data.get("x", 0))
                y = float(data.get("y", 0))
                input_handler.move_mouse(x, y, normalized=True)
            
            elif event_type == "scroll":
                direction = data.get("direction", "down")
                amount = int(data.get("amount", 3))
                input_handler.scroll(direction, amount)
            
            elif event_type in ("keydown", "keypress"):
                key = data.get("key", "")
                if key:
                    xkey = translate_key(key)
                    input_handler.key_press(xkey)
            
            elif event_type == "type":
                text = data.get("text", "")
                if text:
                    input_handler.type_text(text)
            
            elif event_type == "settings":
                # Update settings dynamically
                capture = self._get_capture()
                if "quality" in data:
                    capture.set_quality(int(data["quality"]))
                if "scale" in data:
                    capture.set_scale(float(data["scale"]))
                    if self._input:
                        self._input.set_screen_size(capture.width, capture.height)
                        
        except Exception as e:
            print(f"Input error: {e}")
    
    def _get_fallback_html(self) -> str:
        """Return fallback HTML if static files not found."""
        ws_port = self.config.port + 1
        return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
    <title>Couch Control</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }}
        html, body {{ width: 100%; height: 100%; overflow: hidden; background: #0a0a0f; 
                     font-family: system-ui; touch-action: none; user-select: none; }}
        #container {{ width: 100vw; height: calc(100vh - 60px); display: flex; 
                     justify-content: center; align-items: center; background: #000; }}
        #screen {{ max-width: 100%; max-height: 100%; }}
        #loading {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
                   color: white; text-align: center; }}
        .spinner {{ width: 40px; height: 40px; border: 3px solid rgba(255,255,255,0.2);
                   border-top-color: #e94560; border-radius: 50%; 
                   animation: spin 1s linear infinite; margin: 0 auto 15px; }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        #controls {{ position: fixed; bottom: 0; left: 0; right: 0; height: 60px;
                    background: rgba(20,20,35,0.95); display: flex; align-items: center;
                    justify-content: center; gap: 10px; padding: 0 15px; z-index: 100; }}
        .btn {{ background: rgba(255,255,255,0.15); border: none; color: white;
               font-size: 18px; width: 44px; height: 44px; border-radius: 10px; cursor: pointer; }}
        .btn:active {{ background: rgba(255,255,255,0.3); }}
        select {{ background: rgba(255,255,255,0.15); border: none; color: white;
                 padding: 10px; border-radius: 10px; font-size: 14px; }}
        select option {{ background: #1a1a2e; }}
        #status {{ font-size: 10px; color: #888; }}
        #keyboard {{ position: fixed; bottom: 60px; left: 0; right: 0; 
                    background: rgba(20,20,35,0.98); padding: 15px; display: none; z-index: 99; }}
        #keyboard.visible {{ display: block; }}
        #keyboard input {{ width: 100%; padding: 12px; font-size: 16px; 
                          background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2);
                          border-radius: 8px; color: white; margin-bottom: 10px; }}
        .keys {{ display: flex; gap: 8px; flex-wrap: wrap; }}
        .key {{ background: rgba(255,255,255,0.1); border: none; color: white;
               padding: 10px 14px; border-radius: 6px; font-size: 13px; flex: 1; min-width: 50px; }}
        .key:active {{ background: rgba(255,255,255,0.25); }}
        .key.send {{ background: #e94560; }}
    </style>
</head>
<body>
    <div id="container">
        <div id="loading"><div class="spinner"></div><p>Connecting...</p></div>
        <canvas id="screen"></canvas>
    </div>
    
    <div id="keyboard">
        <input type="text" id="text-input" placeholder="Type here..." autocomplete="off">
        <div class="keys">
            <button class="key send" id="send-btn">Send</button>
            <button class="key" data-key="Enter">↵</button>
            <button class="key" data-key="Backspace">⌫</button>
            <button class="key" data-key="Tab">Tab</button>
            <button class="key" data-key="Escape">Esc</button>
        </div>
        <div class="keys" style="margin-top: 8px">
            <button class="key" data-key="ctrl+c">Ctrl+C</button>
            <button class="key" data-key="ctrl+v">Ctrl+V</button>
            <button class="key" data-key="ctrl+z">Ctrl+Z</button>
            <button class="key" data-key="Up">↑</button>
            <button class="key" data-key="Down">↓</button>
        </div>
    </div>
    
    <div id="controls">
        <button class="btn" id="kbd-btn">⌨️</button>
        <select id="quality-select">
            <option value="40">Low</option>
            <option value="60">Med</option>
            <option value="75" selected>High</option>
        </select>
        <select id="scale-select">
            <option value="0.5">50%</option>
            <option value="0.75" selected>75%</option>
            <option value="1.0">100%</option>
        </select>
        <button class="btn" id="refresh-btn">🔄</button>
        <span id="status">Connecting...</span>
    </div>
    
    <script>
    (function() {{
        const canvas = document.getElementById('screen');
        const ctx = canvas.getContext('2d');
        const loading = document.getElementById('loading');
        const status = document.getElementById('status');
        const keyboard = document.getElementById('keyboard');
        const textInput = document.getElementById('text-input');
        
        let ws = null;
        let connected = false;
        let touchState = {{ startTime: 0, startX: 0, startY: 0, isDragging: false }};
        let longPressTimer = null;
        
        function connect() {{
            const wsUrl = 'ws://' + location.hostname + ':{ws_port}';
            ws = new WebSocket(wsUrl);
            ws.binaryType = 'arraybuffer';
            
            ws.onopen = () => {{
                connected = true;
                loading.style.display = 'none';
                status.textContent = 'Connected';
                status.style.color = '#4f4';
            }};
            
            ws.onmessage = (event) => {{
                if (event.data instanceof ArrayBuffer) {{
                    const blob = new Blob([event.data], {{ type: 'image/jpeg' }});
                    const url = URL.createObjectURL(blob);
                    const img = new Image();
                    img.onload = () => {{
                        if (canvas.width !== img.width || canvas.height !== img.height) {{
                            canvas.width = img.width;
                            canvas.height = img.height;
                        }}
                        ctx.drawImage(img, 0, 0);
                        URL.revokeObjectURL(url);
                    }};
                    img.src = url;
                }}
            }};
            
            ws.onclose = () => {{
                connected = false;
                status.textContent = 'Disconnected';
                status.style.color = '#f44';
                loading.style.display = 'block';
                loading.querySelector('p').textContent = 'Reconnecting...';
                setTimeout(connect, 2000);
            }};
            
            ws.onerror = () => {{
                ws.close();
            }};
        }}
        
        function send(data) {{
            if (connected && ws.readyState === WebSocket.OPEN) {{
                ws.send(JSON.stringify(data));
            }}
        }}
        
        function getCoords(e) {{
            const rect = canvas.getBoundingClientRect();
            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;
            return {{
                x: Math.max(0, Math.min(1, (clientX - rect.left) / rect.width)),
                y: Math.max(0, Math.min(1, (clientY - rect.top) / rect.height))
            }};
        }}
        
        // Touch/mouse handling
        canvas.addEventListener('touchstart', handleStart, {{ passive: false }});
        canvas.addEventListener('mousedown', handleStart);
        canvas.addEventListener('touchmove', handleMove, {{ passive: false }});
        canvas.addEventListener('mousemove', handleMove);
        canvas.addEventListener('touchend', handleEnd, {{ passive: false }});
        canvas.addEventListener('mouseup', handleEnd);
        canvas.addEventListener('contextmenu', (e) => {{
            e.preventDefault();
            const coords = getCoords(e);
            send({{ type: 'click', ...coords, button: 3 }});
        }});
        canvas.addEventListener('wheel', (e) => {{
            e.preventDefault();
            send({{ type: 'scroll', direction: e.deltaY > 0 ? 'down' : 'up', amount: 3 }});
        }}, {{ passive: false }});
        
        function handleStart(e) {{
            e.preventDefault();
            const coords = getCoords(e);
            touchState = {{ startTime: Date.now(), startX: coords.x, startY: coords.y, isDragging: false }};
            longPressTimer = setTimeout(() => {{
                send({{ type: 'click', x: coords.x, y: coords.y, button: 3 }});
                longPressTimer = null;
            }}, 500);
        }}
        
        function handleMove(e) {{
            if (!touchState.startTime) return;
            e.preventDefault();
            const coords = getCoords(e);
            const dx = Math.abs(coords.x - touchState.startX);
            const dy = Math.abs(coords.y - touchState.startY);
            if (!touchState.isDragging && (dx > 0.02 || dy > 0.02)) {{
                touchState.isDragging = true;
                clearTimeout(longPressTimer);
            }}
            if (touchState.isDragging) {{
                send({{ type: 'move', ...coords }});
            }}
        }}
        
        function handleEnd(e) {{
            e.preventDefault();
            clearTimeout(longPressTimer);
            if (!touchState.isDragging && longPressTimer !== null && Date.now() - touchState.startTime < 500) {{
                send({{ type: 'click', x: touchState.startX, y: touchState.startY, button: 1 }});
            }}
            touchState.startTime = 0;
            touchState.isDragging = false;
        }}
        
        // Keyboard panel
        document.getElementById('kbd-btn').onclick = () => {{
            keyboard.classList.toggle('visible');
            if (keyboard.classList.contains('visible')) textInput.focus();
        }};
        
        document.getElementById('send-btn').onclick = () => {{
            if (textInput.value) {{
                send({{ type: 'type', text: textInput.value }});
                textInput.value = '';
            }}
        }};
        
        textInput.onkeydown = (e) => {{
            if (e.key === 'Enter') {{
                e.preventDefault();
                if (textInput.value) {{
                    send({{ type: 'type', text: textInput.value }});
                    textInput.value = '';
                }}
                send({{ type: 'keypress', key: 'Enter' }});
            }}
        }};
        
        document.querySelectorAll('.key[data-key]').forEach(btn => {{
            btn.onclick = () => send({{ type: 'keypress', key: btn.dataset.key }});
        }});
        
        // Settings
        document.getElementById('quality-select').onchange = function() {{
            send({{ type: 'settings', quality: parseInt(this.value) }});
        }};
        document.getElementById('scale-select').onchange = function() {{
            send({{ type: 'settings', scale: parseFloat(this.value) }});
        }};
        document.getElementById('refresh-btn').onclick = () => {{
            if (ws) ws.close();
        }};
        
        connect();
    }})();
    </script>
</body>
</html>'''
    
    async def start(self) -> None:
        """Start both HTTP and WebSocket servers."""
        # Start HTTP server for static files
        self.http_runner = web.AppRunner(self.http_app)
        await self.http_runner.setup()
        http_site = web.TCPSite(self.http_runner, self.config.host, self.config.port)
        await http_site.start()
        
        # Start WebSocket server on port + 1
        ws_port = self.config.port + 1
        self.ws_server = await ws_serve(
            self._websocket_handler,
            self.config.host,
            ws_port,
            max_size=10 * 1024 * 1024,  # 10MB max message
            ping_interval=20,
            ping_timeout=20,
        )
        
        # Show user-friendly URL
        from .config import get_local_ip
        display_host = self.config.host
        if display_host == "0.0.0.0":
            display_host = get_local_ip()
        
        print(f"\n🛋️  Couch Control started!")
        print(f"   Web UI:    http://{display_host}:{self.config.port}")
        print(f"   WebSocket: ws://{display_host}:{ws_port}")
        if self.config.pin:
            print(f"   PIN: {self.config.pin}")
        print(f"\n   Open the Web UI on your phone to control your desktop.\n")
    
    async def stop(self) -> None:
        """Stop the servers."""
        # Close all WebSocket connections
        for client in list(self.clients):
            try:
                await client.close()
            except Exception:
                pass
        self.clients.clear()
        
        # Stop WebSocket server
        if self.ws_server:
            self.ws_server.close()
            await self.ws_server.wait_closed()
        
        # Stop HTTP server
        if self.http_runner:
            await self.http_runner.cleanup()
        
        # Cleanup capture
        close_capture()
        self._capture = None
        self._input = None
        
        print("\n🛋️  Couch Control stopped.\n")
    
    async def run_forever(self) -> None:
        """Run the server until interrupted."""
        await self.start()
        
        try:
            timeout_seconds = self.config.timeout_minutes * 60
            
            while not self.shutdown_event.is_set():
                await asyncio.sleep(30)
                
                # Check timeout
                if timeout_seconds > 0 and len(self.clients) == 0:
                    idle_time = time.time() - self.last_activity
                    if idle_time > timeout_seconds:
                        print(f"Auto-stopping after {self.config.timeout_minutes} minutes of inactivity")
                        break
        
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()


def run_server(config: Optional[Config] = None) -> None:
    """Run the server (blocking)."""
    server = CouchControlServer(config)
    
    try:
        asyncio.run(server.run_forever())
    except KeyboardInterrupt:
        print("\nShutting down...")
