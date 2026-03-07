# Couch Control — Improvement Plan

> This document combines code-analysis findings with feature requests. Review each section, pick what to build, and use it as the development roadmap.

---

## Table of Contents

1. [Current Architecture Summary](#1-current-architecture-summary)
2. [Bugs & Critical Issues Found](#2-bugs--critical-issues-found)
3. [Your Requested Features](#3-your-requested-features)
4. [UX / UI Improvements](#4-ux--ui-improvements)
5. [Performance Improvements](#5-performance-improvements)
6. [Security Improvements](#6-security-improvements)
7. [Cross-Platform & Distribution](#7-cross-platform--distribution)
8. [Remote Access — Cloudflare Tunnel](#8-remote-access--cloudflare-tunnel)
9. [Implementation Priority Roadmap](#9-implementation-priority-roadmap)

---

## 1. Current Architecture Summary

```
Browser (phone/PC)
    │
    ├── HTTP :8080   → aiohttp (serves index.html, style.css, app.js)
    └── WS   :8081   → websockets (binary JPEG frames + JSON input events)

Server side
    ├── capture.py      — mss screen grab → Pillow/TurboJPEG → bytes
    ├── input_handler.py — xdotool subprocess for mouse/keyboard
    ├── server.py        — asyncio event loop, frame streaming, input routing
    ├── config.py        — YAML config + sensible defaults
    └── cli.py           — argparse CLI (start / stop / status / ip / config)
```

**Platforms tested**: Linux only (X11 via `xdotool` + `mss`)
**Client**: Vanilla JS canvas. Touch + mouse. No framework.
**Startup**: `systemd` service script (`setup_service.sh`)

---

## 2. Bugs & Critical Issues Found

### 2.1 PIN authentication is declared but never enforced

**File**: `server.py:_websocket_handler`
`config.pin` is stored and printed at startup, but the WebSocket handler never checks it. Any client that connects gets full control.

**Fix needed**: On first WebSocket message, check a JSON `{ "type": "auth", "pin": "..." }` handshake before processing any input.

---

### 2.2 `max_clients` config setting is never enforced

**File**: `config.py:DEFAULT_CONFIG` → `performance.max_clients = 3`
**File**: `server.py:_websocket_handler` — no check on `len(self.clients)`

If 10 phones connect simultaneously, all get full mouse/keyboard control at the same time — chaotic.

**Fix needed**: Reject connection with a close code when `len(self.clients) >= max_clients`.

---

### 2.3 Two separate ports required (HTTP :8080 + WS :8081)

The app opens two listening ports. This means two firewall rules, two Cloudflare Tunnel entries, and two proxy rules. It also breaks when behind any reverse proxy that can't handle port arithmetic.

**Fix needed**: Serve the WebSocket on the same HTTP port using aiohttp's built-in WebSocket upgrade handler (`aiohttp.web.WebSocketResponse`). Removes `websockets` dependency.

---

### 2.4 Fallback HTML in `server.py` is a second copy of the UI

`server.py:_get_fallback_html()` (line 262) duplicates the entire UI as an f-string. It will always be out of date with `static/index.html`.

**Fix needed**: If static files are missing, serve an error page instead of a stale duplicate UI.

---

### 2.5 Image memory leak risk in `app.js`

**File**: `app.js:renderFrame` (line 115)
Each frame creates a `Blob`, an `<img>` element, and a `URL.createObjectURL`. If the connection is fast (24 fps) and the previous frame hasn't decoded yet, old blobs pile up.

**Fix needed**: Track the in-flight image decode. If a new frame arrives before the previous one finishes, revoke the old URL immediately and skip rendering the old frame.

---

### 2.6 xdotool subprocess spawned per input event

**File**: `input_handler.py:_run_xdotool`
Every mouse move, click, or keypress does `subprocess.run(["xdotool", ...])` — a new process fork. At 60 mouse events per second this creates 60 child processes per second, wasting CPU.

**Fix needed**: Use `python-xlib` (pure Python, zero subprocess overhead) or keep a persistent `xdotool` process open with `--clearmodifiers` chain mode.

---

### 2.7 No Wayland input support

`xdotool` only works on X11. On Wayland (GNOME 45+, KDE 6) it silently fails — the cursor doesn't move.

**Fix needed**: Detect Wayland via `$WAYLAND_DISPLAY`. Fall back to `ydotool` (already partially scaffolded in `input_handler.py` line 22 but unused).

---

### 2.8 `longPressTimer` logic bug in `app.js`

**File**: `app.js:handlePointerUp` (line 311)
```js
if (!touchState.isDragging && longPressTimer !== null && duration < 500)
```
After a long press fires, `longPressTimer` is set to `null` (line 241). But `duration < 500` will be `false` anyway since 500ms has elapsed. The logic accidentally works, but for the wrong reason. A fast lift after long-press could trigger a spurious click.

**Fix needed**: Use a dedicated `didLongPress` boolean flag instead of relying on `longPressTimer !== null`.

---

## 3. Your Requested Features

### 3.1 Ctrl+Shift+C and Ctrl+Shift+V in the keypad

**Current**: The keyboard panel in `index.html` has `Ctrl+C`, `Ctrl+V`, `Ctrl+Z` but no `Ctrl+Shift+C` or `Ctrl+Shift+V`.

**Change needed** in `couch_control/static/index.html` (keyboard panel key rows):

```html
<!-- Add to second key row -->
<button class="key-btn" data-key="ctrl+shift+c">Ctrl+⇧+C</button>
<button class="key-btn" data-key="ctrl+shift+v">Ctrl+⇧+V</button>
```

**Change needed** in `couch_control/input_handler.py` (KEY_MAP):

```python
# These pass through to xdotool directly — xdotool already understands
# "ctrl+shift+c" syntax, so no mapping needed.
# Just verify the key-btn sends the correct string.
```

The `data-key` attribute value goes directly to `send({ type: 'keypress', key: btn.dataset.key })`, which then passes to `translate_key()` → `key_press()` → `xdotool key ctrl+shift+c`. This already works — just add the HTML buttons.

---

### 3.2 Windows startup app support

Windows has no `xdotool`, no `mss` X11 backend, and no `systemd`. The following changes are needed:

#### 3.2.1 Cross-platform input handler

Replace `xdotool` subprocess with `pyautogui` (works on Windows, macOS, Linux):

```
pip install pyautogui
```

Or better, use `pynput` (no GUI dependency, works headless on all platforms):

```
pip install pynput
```

Create `input_handler_win.py` that uses `pynput.mouse.Controller` and `pynput.keyboard.Controller`.

#### 3.2.2 Cross-platform screen capture

`mss` already works on Windows — no change needed there.

#### 3.2.3 Windows startup options

**Option A — Windows Registry (runs at login, no UAC):**
Add a registry entry under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.

**Option B — Windows Task Scheduler (recommended):**
Create a scheduled task that triggers on user logon. Can be done via `schtasks` command or Python `win32com`.

**Option C — Windows startup folder:**
Place a `.bat` shortcut in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`.

**Packaging for Windows users:**
- Use `PyInstaller` to create a single `.exe` — no Python install required for end users.
- Provide a `install_windows.bat` that registers startup and creates a desktop shortcut.

```
pyproject.toml additions:
[project.optional-dependencies]
windows = ["pynput>=1.7", "pyinstaller>=6.0"]
```

#### 3.2.4 `setup.py` / `pyproject.toml` platform guards

```python
# In dependencies, guard xdotool-dependent code:
import sys
if sys.platform != "win32":
    # use xdotool path
else:
    # use pynput path
```

---

### 3.3 Cloudflare Tunnel (enable/disable toggle)

Cloudflare Tunnel (`cloudflared`) creates a secure HTTPS tunnel from Cloudflare's edge to your localhost — no port forwarding or public IP needed.

#### 3.3.1 What needs to be added

**Config additions** (`config.yaml`):
```yaml
cloudflare:
  enabled: false          # Toggle on/off
  tunnel_name: "couch-control"
  auto_start: false       # Start tunnel when server starts
```

**New module**: `couch_control/tunnel.py`
```python
# Manages cloudflared subprocess
# - check if cloudflared is installed
# - start tunnel: subprocess.Popen(["cloudflared", "tunnel", "--url", f"http://localhost:{port}"])
# - capture the tunnel URL from stdout (cloudflared prints "https://xxx.trycloudflare.com")
# - expose the URL via /status endpoint so the UI can show it
# - stop tunnel on server shutdown
```

**CLI additions**:
```
couch-control start --cloudflare        # Start with tunnel
couch-control tunnel start/stop/status  # Manage tunnel separately
```

**UI addition**: When Cloudflare Tunnel is active, show the public URL in the control bar so you can share it.

#### 3.3.2 Installation requirement

```bash
# Linux
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/

# Windows
# Download cloudflared.exe and place in PATH
```

#### 3.3.3 Security considerations when tunnel is enabled

- **Always require PIN** when Cloudflare Tunnel is active (enforce this automatically)
- Add a session token / one-time link option for sharing with others
- Show a clear warning in the UI: "Remote access is active"
- Rate-limit failed PIN attempts (5 tries, then 60s lockout)

---

## 4. UX / UI Improvements

### 4.1 Status bar enhancements

**Current**: Just shows "Connected" / "Disconnected"
**Add**:
- Live FPS counter (count frames per second in JS)
- Latency indicator (ping-pong timestamp in WebSocket message)
- Active tunnel URL (when Cloudflare is enabled)
- Number of connected clients (from `/status` endpoint)

### 4.2 Better reconnection UX

**Current**: Reconnects after 2 seconds, shows spinning "Reconnecting..." overlay
**Add**:
- Exponential backoff (2s → 4s → 8s → max 30s)
- "Retry Now" button on the overlay
- Show reason for disconnection (server stopped vs network error)

### 4.3 Connection setup / first-time experience

**Add a setup screen** shown before connecting:
- Input field: "Server address" (pre-filled with current host)
- Input field: "PIN" (if server has PIN enabled)
- "Remember this server" checkbox (saves to `localStorage`)
- Recent connections list

### 4.4 Settings panel (replace inline dropdowns)

**Current**: Quality and Scale are inline `<select>` dropdowns in the control bar — cramped on small phones
**Add**: A slide-up settings panel (like a modal sheet) with:
- Quality slider (10–95)
- FPS slider (5–30)
- Scale selector (50% / 75% / 100%)
- Monitor selector (if multiple monitors detected)
- Keyboard shortcut cheatsheet

### 4.5 Clipboard sync

**Add**:
- "Paste from phone clipboard" button: reads `navigator.clipboard.readText()` → sends as `type` event to server
- "Copy to phone clipboard" — harder (requires server-side clipboard read via `xclip`/`xsel`)

### 4.6 Visual feedback improvements

- Show mouse cursor position on canvas (small dot overlay that follows touch/mouse)
- Keyboard panel: highlight keys on press (active state animation)
- Show "Right click" indicator label when long-press fires
- Drag mode: show a "drag active" ribbon/banner so user knows they're in drag mode

### 4.7 Landscape mode keyboard

**Current**: Landscape adjustments exist in CSS but keyboard panel takes too much vertical space
**Add**: Compact 2-row keyboard layout for landscape with only the most-used keys

### 4.8 Dark/Light theme

Add a theme toggle. Use CSS `prefers-color-scheme` as default, allow manual override.

### 4.9 Progressive Web App (PWA)

**Add**:
- `manifest.json` — allows "Add to home screen" on Android/iOS
- Service worker for offline error page
- App icon

```json
// manifest.json
{
  "name": "Couch Control",
  "short_name": "CouchCtrl",
  "display": "fullscreen",
  "background_color": "#0a0a0f",
  "theme_color": "#0a0a0f",
  "icons": [...]
}
```

This makes the web app feel native — users can add it to their home screen and it opens fullscreen without browser chrome.

### 4.10 Scroll gesture on touch (two-finger scroll without mode switch)

**Current**: Scrolling requires mouse wheel from a desktop, or using the View Mode toggle
**Add**: Detect two-finger vertical swipe in Mouse Mode and send scroll events. Keep single-finger for click/drag. This is a very common expectation on mobile.

---

## 5. Performance Improvements

### 5.1 Merge HTTP and WebSocket onto one port

Use `aiohttp.web.WebSocketResponse` for the WebSocket, eliminating the second port and the `websockets` library dependency. This also fixes the Cloudflare Tunnel double-entry problem.

### 5.2 Delta/motion JPEG instead of full frames

Instead of sending a full JPEG every frame, only send frames when the screen has changed significantly. Compare a hash (or downsampled thumbnail) of the current frame to the previous one. Skip sending if difference is below a threshold.

**Expected savings**: 80–90% bandwidth reduction when the screen is idle.

### 5.3 Frame pipeline: decode while displaying

**Current**: `renderFrame()` creates a new `Image` for every frame, blocks canvas draw
**Add**: Use `ImageBitmap` API (`createImageBitmap(blob)`) which decodes off the main thread, then draws with `ctx.drawImage(imageBitmap)`. Faster and non-blocking.

```js
createImageBitmap(blob).then(bitmap => {
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    ctx.drawImage(bitmap, 0, 0);
    bitmap.close();
});
```

### 5.4 Input event throttling on client side

**Current**: Every `mousemove` event sends a WebSocket message immediately
**Add**: Throttle `move` events to one per animation frame (16ms) using `requestAnimationFrame`.

### 5.5 Adaptive quality / FPS

Monitor the WebSocket send queue or frame round-trip time. If the client is falling behind (frames queuing up), automatically lower quality or FPS. Restore when it catches up.

### 5.6 TurboJPEG: avoid numpy round-trip when not scaling

**File**: `capture.py:_encode_turbojpeg` line 140
When `scale == 1.0`, the code already does direct encoding — good. But when scaling, it converts BGRA → RGBA (via Pillow) → numpy array → TurboJPEG. This is slower than necessary.

**Fix**: When scaling, use Pillow's `Image.resize()` then convert directly to `bytes` for TurboJPEG, avoiding the numpy array creation.

---

## 6. Security Improvements

### 6.1 Enforce PIN authentication in WebSocket handler

**File**: `server.py:_websocket_handler`

```python
# First message must be: {"type": "auth", "pin": "1234"}
if self.config.pin:
    auth_msg = await asyncio.wait_for(websocket.recv(), timeout=10)
    data = json.loads(auth_msg)
    if data.get("type") != "auth" or data.get("pin") != self.config.pin:
        await websocket.close(code=4401, reason="Unauthorized")
        return
```

### 6.2 Rate limit PIN attempts

Track failed attempts by IP. After 5 failures, block that IP for 60 seconds.

### 6.3 HTTPS / WSS support

When not behind a tunnel, support optional TLS:
```yaml
security:
  tls_cert: "/path/to/cert.pem"
  tls_key: "/path/to/key.pem"
```

Use `ssl.create_default_context()` in the server. For self-signed certs, provide a script to generate one.

### 6.4 Enforce max_clients

**File**: `server.py:_websocket_handler`

```python
if len(self.clients) >= self.config.max_clients:
    await websocket.close(code=4429, reason="Too many clients")
    return
```

### 6.5 Input sanitization

Validate all incoming WebSocket message fields before use:
- `x`, `y` must be floats between 0.0 and 1.0
- `button` must be 1, 2, or 3
- `key` must match allowlist or safe regex (no shell injection risk since xdotool args are passed as list, but still good practice)
- `text` length limit (e.g., max 1000 chars per type event)

### 6.6 Access log

Log all connections with IP, timestamp, and actions (at info level, configurable). Useful for auditing when tunnel is enabled.

---

## 7. Cross-Platform & Distribution

### 7.1 Windows — complete support plan

| Component | Linux (current) | Windows (needed) |
|-----------|----------------|------------------|
| Screen capture | `mss` | `mss` (already works) |
| Mouse control | `xdotool` subprocess | `pynput.mouse.Controller` |
| Keyboard control | `xdotool` subprocess | `pynput.keyboard.Controller` |
| Startup | `systemd` service | Task Scheduler / Registry |
| Package | pip install | PyInstaller `.exe` |
| Installer | `setup_service.sh` | `install.bat` or NSIS installer |

#### Windows input handler (`input_handler_win.py`):
```python
from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyController, Key
```

#### Key mapping additions for Windows:
- `ctrl+shift+c`, `ctrl+shift+v` — already handled by `xdotool` on Linux; on Windows pynput needs explicit modifier press/release
- Windows-specific keys: `Win`, `PrintScreen`, `NumLock`

#### Windows auto-start installer script (`install_windows.bat`):
```batch
@echo off
schtasks /create /tn "Couch Control" /tr "%~dp0couch-control.exe start" /sc onlogon /rl limited /f
echo Couch Control will start automatically at login.
pause
```

#### System tray icon (Windows & macOS):
Using `pystray`, add a system tray icon with menu:
- Start / Stop server
- Show local URL
- Enable/Disable Cloudflare Tunnel
- Open in browser
- Exit

```
pip install pystray Pillow
```

### 7.2 macOS support

`mss` works on macOS. Input needs `pynput` (same as Windows) or `pyautogui`. The `screencapture` permission prompt must be handled gracefully.

### 7.3 Package as a standalone executable

```bash
# Linux
pyinstaller --onefile --add-data "couch_control/static:couch_control/static" couch_control/__main__.py -n couch-control

# Windows
pyinstaller --onefile --windowed --add-data "couch_control/static;couch_control/static" couch_control/__main__.py -n couch-control.exe
```

Provide pre-built binaries in GitHub Releases so non-technical users don't need Python.

---

## 8. Remote Access — Cloudflare Tunnel

### 8.1 How it works

```
Phone (anywhere in world)
    │
    └── HTTPS → Cloudflare Edge → cloudflared daemon (on your PC) → localhost:8080
```

`cloudflared tunnel --url http://localhost:8080` creates a public HTTPS URL like `https://abc123.trycloudflare.com` with zero configuration.

### 8.2 New module: `couch_control/tunnel.py`

```python
"""Manages Cloudflare Tunnel via cloudflared subprocess."""

import asyncio
import re
import shutil
import subprocess
from typing import Optional

class CloudflareTunnel:
    def __init__(self, port: int):
        self.port = port
        self.public_url: Optional[str] = None
        self._proc: Optional[asyncio.subprocess.Process] = None

    async def start(self) -> Optional[str]:
        """Start tunnel and return public URL."""
        if not shutil.which("cloudflared"):
            raise RuntimeError("cloudflared not found. Install from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/")

        self._proc = await asyncio.create_subprocess_exec(
            "cloudflared", "tunnel", "--url", f"http://localhost:{self.port}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Parse URL from cloudflared output
        url = await self._wait_for_url()
        self.public_url = url
        return url

    async def _wait_for_url(self, timeout: float = 30.0) -> Optional[str]:
        """Wait for cloudflared to print the tunnel URL."""
        deadline = asyncio.get_event_loop().time() + timeout
        url_pattern = re.compile(r'https://[a-z0-9\-]+\.trycloudflare\.com')

        while asyncio.get_event_loop().time() < deadline:
            line = await asyncio.wait_for(self._proc.stderr.readline(), timeout=5)
            match = url_pattern.search(line.decode())
            if match:
                return match.group(0)
        return None

    async def stop(self):
        """Stop the tunnel."""
        if self._proc:
            self._proc.terminate()
            await self._proc.wait()
            self._proc = None
            self.public_url = None
```

### 8.3 Config additions (`config.yaml`)

```yaml
cloudflare:
  enabled: false       # Set to true to start tunnel with server
  require_pin: true    # Force PIN when tunnel is enabled (recommended)
```

### 8.4 CLI additions

```
couch-control start --cloudflare        # Start server + tunnel
couch-control tunnel status             # Show current tunnel URL
```

### 8.5 UI addition

When tunnel is active, show a banner in the control bar:
```
🌐 Remote: https://abc123.trycloudflare.com  [Copy] [Stop]
```

### 8.6 Security warning when tunnel is enabled

Display a modal on first connection through the tunnel:
> "⚠️ You are accessing this device remotely over Cloudflare Tunnel. Make sure you trust this connection."

---

## 9. Implementation Priority Roadmap

### Phase 1 — Quick wins (1–3 days each)

| # | Task | File(s) | Impact |
|---|------|---------|--------|
| 1 | Add `Ctrl+Shift+C` and `Ctrl+Shift+V` buttons | `index.html` | Your request |
| 2 | Fix PIN enforcement in WebSocket handler | `server.py` | Security bug |
| 3 | Fix `max_clients` enforcement | `server.py` | Bug |
| 4 | Fix image memory leak in frame renderer | `app.js` | Performance |
| 5 | Fix `longPressTimer` logic bug | `app.js` | UX bug |
| 6 | Remove duplicate fallback HTML | `server.py` | Code quality |

### Phase 2 — UX improvements (1 week)

| # | Task | Impact |
|---|------|--------|
| 7 | FPS counter + latency display in status bar | UX |
| 8 | PWA manifest.json + home screen install | UX |
| 9 | Two-finger scroll in Mouse Mode | UX |
| 10 | Clipboard paste from phone | UX |
| 11 | Settings panel (slide-up sheet) | UX |
| 12 | Better reconnection with exponential backoff | UX |

### Phase 3 — Windows support (1–2 weeks)

| # | Task | Impact |
|---|------|--------|
| 13 | `pynput`-based input handler for Windows | Platform |
| 14 | Platform detection + handler selection | Platform |
| 15 | `install_windows.bat` with Task Scheduler startup | Platform |
| 16 | System tray icon (`pystray`) | Platform |
| 17 | PyInstaller build for Windows `.exe` | Distribution |

### Phase 4 — Cloudflare Tunnel (3–5 days)

| # | Task | Impact |
|---|------|--------|
| 18 | `tunnel.py` module | Remote access |
| 19 | Config + CLI integration | Remote access |
| 20 | UI tunnel URL banner | UX |
| 21 | Force PIN when tunnel active | Security |

### Phase 5 — Performance & architecture (ongoing)

| # | Task | Impact |
|---|------|--------|
| 22 | Merge HTTP + WS onto single port (aiohttp native WS) | Architecture |
| 23 | `ImageBitmap` frame decode in JS | Performance |
| 24 | Frame skip when screen unchanged | Bandwidth |
| 25 | Input event throttling (requestAnimationFrame) | Performance |
| 26 | Wayland support via `ydotool` | Platform |

---

## Appendix A — Suggested `config.yaml` after all improvements

```yaml
server:
  port: 8080
  host: "0.0.0.0"
  tls_cert: ""          # Path to TLS cert for HTTPS (optional)
  tls_key: ""           # Path to TLS key

capture:
  quality: 70
  fps: 24
  scale: 0.75
  monitor: 0            # 0 = all monitors, 1+ = specific
  adaptive_quality: true  # Auto-lower quality if client falls behind

security:
  pin: ""               # Require this PIN from all clients
  timeout_minutes: 30
  max_failed_pins: 5    # Lock IP after this many failures
  require_pin_on_tunnel: true  # Always enforce PIN when tunnel is active

performance:
  use_turbojpeg: true
  max_clients: 3
  frame_skip_threshold: 0.01  # Skip frame if pixel diff < 1%

cloudflare:
  enabled: false
  auto_start: false

ui:
  theme: "auto"         # "dark", "light", or "auto"
```

---

## Appendix B — Windows install flow (user perspective)

1. Download `couch-control-windows.exe` from GitHub Releases
2. Double-click → runs installer wizard
3. Wizard asks: "Start at Windows login? (Recommended)" → Yes
4. Wizard asks: "Set a PIN for security?" → user sets PIN
5. System tray icon appears
6. Balloon notification: "Couch Control running at http://192.168.1.100:8080"
7. User opens that URL on phone and starts controlling

---

*Document generated by analysis of Couch Control v1.0.0 — March 2026*
