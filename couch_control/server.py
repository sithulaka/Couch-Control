"""
WebSocket server for Couch Control.

All traffic (HTTP static files + WebSocket) runs on a single port
using aiohttp's native WebSocket support — no separate WS port needed.

WebSocket endpoint: ws://host:port/ws
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

import aiohttp
from aiohttp import web

from .capture import ScreenCapture, get_capture, close_capture
from .config import Config, get_config
from .input_handler import get_input_handler, translate_key


class CouchControlServer:
    """
    Single-port aiohttp server for real-time remote desktop control.

    Features:
    - WebSocket binary frame streaming on the same port as HTTP
    - PIN authentication with rate limiting
    - Max client enforcement
    - Frame-skip (only sends frames when screen changes)
    - Cloudflare Tunnel integration
    - System tray support
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()

        # Active WebSocket connections
        self.clients: Set[web.WebSocketResponse] = set()
        self.last_activity = time.time()

        # Lazy-loaded capture and input
        self._capture: Optional[ScreenCapture] = None
        self._input = None

        # Server state
        self.http_runner: Optional[web.AppRunner] = None
        self.shutdown_event = asyncio.Event()

        # Rate limiting: {ip: (fail_count, first_fail_time)}
        self._pin_failures: Dict[str, Tuple[int, float]] = {}

        # Tunnel (optional)
        self._tunnel = None
        self._tunnel_url: Optional[str] = None

        # Setup aiohttp app
        self.app = web.Application()
        self._setup_routes()

    # ─────────────────────── Setup ───────────────────────

    def _setup_routes(self) -> None:
        self.app.router.add_get("/", self._handle_index)
        self.app.router.add_get("/ping", self._handle_ping)
        self.app.router.add_get("/status", self._handle_status)
        self.app.router.add_get("/ws", self._websocket_handler)

        static_path = Path(__file__).parent / "static"
        if static_path.exists():
            self.app.router.add_static("/static/", static_path)

    # ─────────────────────── Lazy init ───────────────────

    def _get_capture(self) -> ScreenCapture:
        if self._capture is None:
            self._capture = get_capture(
                monitor=self.config.monitor,
                quality=self.config.quality,
                scale=self.config.scale,
                use_turbojpeg=self.config.use_turbojpeg,
                frame_skip=self.config.frame_skip,
            )
        return self._capture

    def _get_input(self):
        if self._input is None:
            self._input = get_input_handler()
            capture = self._get_capture()
            self._input.set_screen_size(capture.width, capture.height)
        return self._input

    def _update_activity(self) -> None:
        self.last_activity = time.time()

    # ─────────────────────── HTTP handlers ───────────────

    async def _handle_index(self, request: web.Request) -> web.Response:
        self._update_activity()
        static_path = Path(__file__).parent / "static" / "index.html"
        if static_path.exists():
            return web.FileResponse(static_path)
        return web.Response(status=503, text="Static files not found. Check installation.")

    async def _handle_ping(self, request: web.Request) -> web.Response:
        return web.Response(text="pong")

    async def _handle_status(self, request: web.Request) -> web.Response:
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
            "tunnel": self._tunnel_url,
        }
        return web.json_response(status)

    # ─────────────────────── PIN / rate limiting ─────────

    def _pin_required(self) -> bool:
        """Return True if PIN authentication is currently required."""
        if self.config.pin:
            return True
        if self.config.require_pin_on_tunnel and self._tunnel_url:
            return True
        return False

    def _check_pin(self, pin: str, client_ip: str) -> bool:
        """Validate PIN and track failures. Returns True if allowed."""
        effective_pin = self.config.pin
        if not effective_pin:
            return True  # No PIN configured

        max_failures = self.config.max_failed_pins
        lockout_seconds = 60.0

        # Check lockout
        if client_ip in self._pin_failures:
            count, first_time = self._pin_failures[client_ip]
            if count >= max_failures:
                if time.time() - first_time < lockout_seconds:
                    return False
                else:
                    del self._pin_failures[client_ip]

        if pin == effective_pin:
            self._pin_failures.pop(client_ip, None)
            return True

        # Record failure
        count, first_time = self._pin_failures.get(client_ip, (0, time.time()))
        self._pin_failures[client_ip] = (count + 1, first_time)
        return False

    # ─────────────────────── WebSocket handler ───────────

    async def _websocket_handler(self, request: web.Request) -> web.StreamResponse:
        """Handle a WebSocket upgrade request."""
        self._update_activity()

        # Enforce max clients before upgrading
        if len(self.clients) >= self.config.max_clients:
            return web.Response(status=429, text="Too many clients connected.")

        ws = web.WebSocketResponse(
            max_msg_size=10 * 1024 * 1024,
            heartbeat=20,
        )
        await ws.prepare(request)

        client_ip = request.remote or "unknown"
        print(f"Client connected: {client_ip}")

        # ── Send server info first so the client knows whether PIN is needed ──
        await ws.send_json({
            "type": "server_info",
            "pin_required": self._pin_required(),
            "tunnel_url": self._tunnel_url,
            "version": "2.0.0",
        })

        # ── PIN authentication (client must reply with auth message) ──
        if self._pin_required():
            try:
                auth_msg = await asyncio.wait_for(ws.__anext__(), timeout=15.0)
            except (asyncio.TimeoutError, StopAsyncIteration):
                await ws.close(code=4401, message=b"Auth timeout")
                return ws

            if auth_msg.type != aiohttp.WSMsgType.TEXT:
                await ws.close(code=4401, message=b"Auth required")
                return ws

            try:
                auth_data = json.loads(auth_msg.data)
            except json.JSONDecodeError:
                await ws.close(code=4401, message=b"Invalid auth")
                return ws

            if auth_data.get("type") != "auth" or not self._check_pin(
                auth_data.get("pin", ""), client_ip
            ):
                await ws.close(code=4401, message=b"Unauthorized")
                print(f"Auth failed from {client_ip}")
                return ws

        self.clients.add(ws)
        frame_task = asyncio.create_task(self._stream_frames(ws))

        try:
            async for msg in ws:
                self._update_activity()
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_input(ws, msg.data)
                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                    break
        except Exception:
            pass
        finally:
            frame_task.cancel()
            try:
                await frame_task
            except asyncio.CancelledError:
                pass
            self.clients.discard(ws)
            print(f"Client disconnected: {client_ip}")

        return ws

    # ─────────────────────── Frame streaming ─────────────

    async def _stream_frames(self, ws: web.WebSocketResponse) -> None:
        """Stream JPEG frames to the client. Skips unchanged frames."""
        capture = self._get_capture()
        frame_interval = self.config.frame_interval

        try:
            while not self.shutdown_event.is_set() and not ws.closed:
                start_time = time.time()

                jpeg_bytes = capture.capture_jpeg()

                if jpeg_bytes is not None and not ws.closed:
                    await ws.send_bytes(jpeg_bytes)

                elapsed = time.time() - start_time
                await asyncio.sleep(max(0.001, frame_interval - elapsed))

        except asyncio.CancelledError:
            pass
        except ConnectionResetError:
            pass
        except Exception as e:
            if not self.shutdown_event.is_set():
                print(f"Frame error: {e}")

    # ─────────────────────── Input handling ──────────────

    async def _handle_input(self, ws: web.WebSocketResponse, message: str) -> None:
        """Dispatch an input event from the client."""
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return

        event_type = data.get("type", "")

        # Ping/pong for latency measurement
        if event_type == "ping":
            await ws.send_json({"type": "pong", "t": data.get("t", 0)})
            return

        # Clipboard text from browser
        if event_type == "clipboard":
            text = data.get("text", "")
            if text:
                try:
                    input_handler = self._get_input()
                    input_handler.type_text(text[:2000])  # limit length
                except Exception as e:
                    print(f"Clipboard error: {e}")
            return

        try:
            input_handler = self._get_input()

            # Validate coordinate bounds
            def safe_coord(val, default=0.0):
                try:
                    v = float(val)
                    return max(0.0, min(1.0, v))
                except (TypeError, ValueError):
                    return default

            if event_type == "click":
                x = safe_coord(data.get("x"))
                y = safe_coord(data.get("y"))
                button = int(data.get("button", 1))
                if button not in (1, 2, 3):
                    button = 1
                input_handler.click_at(x, y, button, normalized=True)

            elif event_type == "dblclick":
                x = safe_coord(data.get("x"))
                y = safe_coord(data.get("y"))
                input_handler.move_mouse(x, y, normalized=True)
                input_handler.double_click()

            elif event_type == "move":
                x = safe_coord(data.get("x"))
                y = safe_coord(data.get("y"))
                input_handler.move_mouse(x, y, normalized=True)

            elif event_type == "mousedown":
                button = int(data.get("button", 1))
                if button not in (1, 2, 3):
                    button = 1
                input_handler.mouse_down(button)

            elif event_type == "mouseup":
                button = int(data.get("button", 1))
                if button not in (1, 2, 3):
                    button = 1
                input_handler.mouse_up(button)

            elif event_type == "scroll":
                direction = data.get("direction", "down")
                if direction not in ("up", "down"):
                    direction = "down"
                amount = max(1, min(10, int(data.get("amount", 3))))
                input_handler.scroll(direction, amount)

            elif event_type in ("keydown", "keypress"):
                key = data.get("key", "")
                if key and len(key) < 64:
                    xkey = translate_key(key)
                    input_handler.key_press(xkey)

            elif event_type == "type":
                text = data.get("text", "")
                if text and len(text) <= 1000:
                    input_handler.type_text(text)

            elif event_type == "settings":
                capture = self._get_capture()
                if "quality" in data:
                    q = max(10, min(95, int(data["quality"])))
                    capture.set_quality(q)
                if "scale" in data:
                    s = max(0.25, min(1.0, float(data["scale"])))
                    capture.set_scale(s)
                    if self._input:
                        self._input.set_screen_size(capture.width, capture.height)

        except Exception as e:
            print(f"Input error: {e}")

    # ─────────────────────── Tunnel ──────────────────────

    async def _start_tunnel(self) -> None:
        """Start Cloudflare Tunnel if configured."""
        from .tunnel import CloudflareTunnel

        # on_url is called from inside the running event loop (tunnel's async
        # _monitor_output coroutine), so asyncio.ensure_future is safe directly.
        def on_url(url: str):
            self._tunnel_url = url
            asyncio.ensure_future(self._broadcast_tunnel_url(url))

        self._tunnel = CloudflareTunnel(port=self.config.port, on_url=on_url)
        try:
            url = await self._tunnel.start()
            if url:
                self._tunnel_url = url
                print(f"\n   Cloudflare Tunnel: {url}\n")
            else:
                print("Warning: Cloudflare Tunnel failed to start.")
        except RuntimeError as e:
            print(f"Cloudflare Tunnel error: {e}")

    async def _broadcast_tunnel_url(self, url: str) -> None:
        """Send tunnel URL to all connected clients."""
        for ws in list(self.clients):
            try:
                await ws.send_json({"type": "tunnel_url", "url": url})
            except Exception:
                pass

    # ─────────────────────── Lifecycle ───────────────────

    async def start(self) -> None:
        """Start the HTTP+WebSocket server."""
        self.http_runner = web.AppRunner(self.app)
        await self.http_runner.setup()

        # TLS support
        ssl_context = None
        if self.config.tls_cert and self.config.tls_key:
            import ssl
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(self.config.tls_cert, self.config.tls_key)

        site = web.TCPSite(
            self.http_runner,
            self.config.host,
            self.config.port,
            ssl_context=ssl_context,
        )
        await site.start()

        # Start tunnel if enabled
        if self.config.cloudflare_enabled or self.config.cloudflare_auto_start:
            await self._start_tunnel()

        # Print startup info
        from .config import get_local_ip
        display_host = self.config.host
        if display_host == "0.0.0.0":
            display_host = get_local_ip()

        scheme = "https" if ssl_context else "http"
        ws_scheme = "wss" if ssl_context else "ws"

        print(f"\n🛋️  Couch Control started!")
        print(f"   Web UI:    {scheme}://{display_host}:{self.config.port}")
        print(f"   WebSocket: {ws_scheme}://{display_host}:{self.config.port}/ws")
        if self.config.pin:
            print(f"   PIN:       {self.config.pin}")
        if self._tunnel_url:
            print(f"   Tunnel:    {self._tunnel_url}")
        print(f"\n   Open the Web UI on your phone to control your desktop.\n")

    async def stop(self) -> None:
        """Stop the server and clean up resources."""
        self.shutdown_event.set()

        # Stop tunnel
        if self._tunnel and self._tunnel.is_running:
            await self._tunnel.stop()

        # Close all WebSocket connections
        for ws in list(self.clients):
            try:
                await ws.close()
            except Exception:
                pass
        self.clients.clear()

        # Stop HTTP server
        if self.http_runner:
            await self.http_runner.cleanup()

        # Cleanup capture
        close_capture()
        self._capture = None
        self._input = None

        print("\n🛋️  Couch Control stopped.\n")

    async def run_forever(self) -> None:
        """Run until shut down by signal or timeout."""
        await self.start()

        try:
            timeout_seconds = self.config.timeout_minutes * 60

            while not self.shutdown_event.is_set():
                await asyncio.sleep(30)

                if timeout_seconds > 0 and len(self.clients) == 0:
                    idle = time.time() - self.last_activity
                    if idle > timeout_seconds:
                        print(f"Auto-stopping after {self.config.timeout_minutes}m inactivity")
                        break

        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    def enable_tunnel(self) -> None:
        """Enable Cloudflare Tunnel at runtime (safe to call from tray thread)."""
        self.config._config["cloudflare"]["enabled"] = True
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self._start_tunnel()))
        except RuntimeError:
            pass

    async def disable_tunnel(self) -> None:
        """Disable Cloudflare Tunnel at runtime."""
        if self._tunnel:
            await self._tunnel.stop()
        self._tunnel_url = None
        self.config._config["cloudflare"]["enabled"] = False


def run_server(config: Optional[Config] = None, enable_tunnel: bool = False) -> None:
    """Run the server (blocking). Called from CLI."""
    import signal

    server = CouchControlServer(config)

    if enable_tunnel:
        server.config._config["cloudflare"]["enabled"] = True

    def handle_signal(signum, frame):
        server.shutdown_event.set()

    try:
        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)
    except (OSError, ValueError):
        # Windows / non-main-thread contexts may not support all signals
        pass

    try:
        asyncio.run(server.run_forever())
    except KeyboardInterrupt:
        pass
