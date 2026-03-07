# Couch Control 🛋️

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-2.0.0-orange.svg)](https://github.com/sithulaka/Couch-Control/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-brightgreen.svg)](https://github.com/sithulaka/Couch-Control)

> Control your desktop from your phone's browser — on your local network or from **anywhere in the world** via Cloudflare Tunnel. No app installation needed.

Perfect for developers who need to click "Allow" or type prompts for AI agents (Claude Code, Gemini CLI, etc.) without leaving the couch.

---

## Table of Contents

- [Features](#-features)
- [Quick Start](#-quick-start)
- [Usage Guide](#-usage-guide)
- [Configuration](#-configuration)
- [Remote Access — Cloudflare Tunnel](#-remote-access--cloudflare-tunnel)
- [Windows Setup](#-windows-setup)
- [Linux Startup Service](#-linux-startup-service)
- [CLI Reference](#-cli-reference)
- [How It Works](#-how-it-works)
- [Requirements](#-requirements)
- [Troubleshooting](#-troubleshooting)
- [Security](#-security)
- [What's New in v2.0](#-whats-new-in-v20)

---

## ✨ Features

| | Feature | Details |
|---|---------|---------|
| 🚀 | **Real-time streaming** | WebSocket binary frames, ~50ms latency, single port |
| 💨 | **Ultra-lightweight** | < 50MB RAM, frame-skip saves bandwidth when idle |
| 📱 | **Browser-based** | Works in Safari, Chrome, Firefox — no app install |
| 📲 | **PWA** | Add to phone home screen for a native fullscreen feel |
| 👆 | **Touch gestures** | Tap, double-tap, long-press, two-finger scroll, drag |
| ⌨️ | **Virtual keyboard** | `Ctrl+Shift+C/V`, arrows, clipboard paste from phone |
| 🌐 | **Remote access** | Cloudflare Tunnel — no port forwarding, no public IP |
| 🔒 | **Secure** | PIN auth with rate limiting, max client cap, auto-timeout |
| 🪟 | **Windows** | pynput input, Task Scheduler startup, system tray, .exe build |
| 🐧 | **Linux** | X11 (xdotool) and Wayland (ydotool) auto-detected |
| 🍎 | **macOS** | pynput backend, works out of the box |
| 🎨 | **Themes** | Dark / Light / Auto (follows system preference) |

---

## 🚀 Quick Start

### Linux / macOS

```bash
git clone https://github.com/sithulaka/Couch-Control.git
cd Couch-Control

# Install system dependencies + Python package
./install.sh

# Start
couch-control start
```

### Windows

```batch
git clone https://github.com/sithulaka/Couch-Control.git
cd Couch-Control

REM Run the installer — sets up deps, startup task, PIN, desktop shortcut
install_windows.bat
```

Or install manually:
```batch
pip install aiohttp mss Pillow PyYAML netifaces pynput
pip install -e .
python -m couch_control start
```

### Open on your phone

Look for the URL printed in the terminal and open it in your phone's browser:

```
🛋️  Couch Control started!
   Web UI:    http://192.168.1.100:8080
   WebSocket: ws://192.168.1.100:8080/ws
```

> **Tip:** Add the page to your phone's home screen (Share → Add to Home Screen on iOS, or the browser install prompt on Android) for a fullscreen, app-like experience.

---

## 📖 Usage Guide

### Two interaction modes

| Mode | How to enter | What it does |
|------|-------------|--------------|
| 🖱️ **Mouse Mode** (default) | Press the 🔒 Lock button | Your touch controls the real mouse — tap, drag, type |
| 🔍 **View Mode** | Press the 🔍 Zoom button | Pan with one finger, pinch to zoom — no desktop input |

### Touch gestures (Mouse Mode)

| Gesture | Action on desktop |
|---------|------------------|
| Tap | Left click |
| Double tap | Double click |
| Long press (500 ms) | Right click |
| Two-finger swipe up/down | Scroll |
| Touch + drag (Select mode) | Click and drag — select text, move windows |

### ⌨️ Keyboard panel

Open with the **⌨️** button. Rows include:

| Row | Keys |
|-----|------|
| Text row | Type field → **Send Text**, Enter, Backspace |
| Modifiers | Tab, Esc, Ctrl+C, Ctrl+V, Ctrl+Z |
| Terminal shortcuts | **Ctrl+Shift+C**, **Ctrl+Shift+V**, Ctrl+A, Ctrl+X, Ctrl+S |
| Navigation | ↑ ↓ ← → Space |
| Clipboard | **📋 Paste Clipboard** — reads your phone clipboard and types it on the desktop |

### 🎮 Control bar buttons

| Button | Action |
|--------|--------|
| ⌨️ | Toggle keyboard panel |
| 👆 Select | Toggle drag/select mode (hold left button while moving) |
| 🔍 / 🔒 | Switch between Mouse Mode and View Mode |
| 🎯 Reset | Reset pan/zoom to default |
| Quality | Low / Med / High / Ultra JPEG quality |
| ⛶ Full | Toggle fullscreen |
| ⚙️ | Settings panel — quality slider, resolution, theme |
| 🔄 | Reconnect |

### Status bar

The bottom-right status area shows:
- 🟢 / 🔴 connection dot
- `Connected` / `Disconnected`
- Live **FPS** counter
- Round-trip **latency** in ms

---

## ⚙️ Configuration

Config file is auto-discovered in this order:

1. `./config.yaml` (project directory)
2. `$XDG_CONFIG_HOME/couch-control/config.yaml`
3. `~/.config/couch-control/config.yaml`
4. `~/.couch-control.yaml`

Run `couch-control config` to see which file is active and all current values.

**Full reference:**

```yaml
server:
  port: 8080
  host: "0.0.0.0"       # Bind to all interfaces
  tls_cert: ""           # Path to TLS .pem for HTTPS (optional)
  tls_key: ""

capture:
  quality: 70            # JPEG quality 10–95
  fps: 24                # Frames per second
  scale: 0.75            # Resolution scale 0.25–1.0
  monitor: 0             # 0 = all monitors combined, 1+ = specific
  frame_skip: true       # Only send frames when screen changes

security:
  pin: ""                # Require this PIN from every client
  timeout_minutes: 30    # Auto-stop after N minutes idle (0 = never)
  max_failed_pins: 5     # Lock IP for 60s after N wrong attempts
  require_pin_on_tunnel: true  # Force PIN when Cloudflare Tunnel is on

performance:
  use_turbojpeg: true    # Use libturbojpeg if available (10× faster)
  max_clients: 3         # Reject connections beyond this limit

cloudflare:
  enabled: false         # Start Cloudflare Tunnel automatically
  auto_start: false

ui:
  theme: "auto"          # "dark" | "light" | "auto"
```

---

## 🌐 Remote Access — Cloudflare Tunnel

Access your desktop from **anywhere in the world** — through a firewall, behind NAT, without a static IP or port forwarding — via [Cloudflare Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/).

### Step 1 — Install cloudflared

```bash
# Linux (amd64)
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
     -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared

# macOS
brew install cloudflared

# Windows
# Download cloudflared.exe from:
# https://github.com/cloudflare/cloudflared/releases/latest
# and place it in a folder on your PATH.
```

### Step 2 — Start with tunnel

```bash
# Always set a PIN when enabling remote access
couch-control start --cloudflare --pin 1234
```

The terminal prints a public URL and a banner appears in the browser UI:

```
🛋️  Couch Control started!
   Web UI:    http://192.168.1.100:8080
   Tunnel:    https://abc123.trycloudflare.com
   PIN:       1234
```

Share the `trycloudflare.com` URL with anyone who needs access. The URL changes each time you restart — this is normal for Quick Tunnels.

### Check cloudflared installation

```bash
couch-control tunnel check
```

> **Security note:** PIN is automatically enforced whenever the tunnel is active, even if you forgot `--pin`. Do not share the tunnel URL publicly.

---

## 🪟 Windows Setup

### Installer script (recommended)

```batch
install_windows.bat
```

The installer will:
1. Install all Python dependencies (`aiohttp`, `mss`, `Pillow`, `pynput`, etc.)
2. Ask if you want Couch Control to **start automatically at Windows login** (uses Task Scheduler)
3. Ask if you want to set a **PIN**
4. Create a **Desktop shortcut**

### Start manually

```batch
python -m couch_control start
python -m couch_control start --tray       # With system tray icon
python -m couch_control start --cloudflare # With remote tunnel
```

### System tray icon

Requires `pystray`:
```batch
pip install pystray
couch-control start --tray
```

Right-click the tray icon to open the web UI, toggle the tunnel, or stop the server.

### Manual startup (Task Scheduler)

```batch
schtasks /create /tn "Couch Control" /tr "python -m couch_control start" /sc onlogon /rl limited /f
```

### Build a standalone .exe

No Python required on the target machine:

```batch
build_windows.bat
```

Produces `dist\couch-control.exe` using PyInstaller.

---

## 🐧 Linux Startup Service

```bash
# Install as a systemd service (auto-starts on boot)
./setup_service.sh

# With Cloudflare Tunnel and PIN
./setup_service.sh --cloudflare --pin 1234
```

```bash
# Service control
sudo systemctl start couch-control
sudo systemctl stop couch-control
sudo systemctl status couch-control
journalctl -u couch-control -f          # Live logs
```

---

## 📋 CLI Reference

```
couch-control start                     Start with default settings
couch-control start --port 9090         Use a different port
couch-control start --pin 1234          Require PIN authentication
couch-control start --cloudflare        Enable Cloudflare Tunnel
couch-control start --tray              Show system tray icon
couch-control start --quality 50        Lower JPEG quality (saves bandwidth)
couch-control start --fps 15            Lower frame rate (saves CPU)
couch-control start --scale 0.5         Lower resolution (saves bandwidth)
couch-control start --no-frame-skip     Send every frame even if unchanged

couch-control stop                      Stop the running server
couch-control status                    Check if server is running
couch-control ip                        Print local IP address and URL
couch-control config                    Show full active configuration

couch-control tunnel check              Check if cloudflared is installed
couch-control tunnel start              Start a standalone Cloudflare Tunnel
couch-control tunnel start --port 8080  Tunnel a specific port
```

---

## 🔧 How It Works

```
Your Phone / Any Browser
        │
        │  GET  :8080/        → HTML, CSS, JS (served once)
        │  WS   :8080/ws      → JPEG frames (server→client, binary)
        │                        Input events (client→server, JSON)
        ▼
┌───────────────────────────────────────────────────┐
│                COUCH CONTROL SERVER               │
│                                                   │
│   mss (screen grab)                               │
│     → frame-skip hash check                       │
│     → Pillow / TurboJPEG (JPEG encode)            │
│     → aiohttp WebSocket (send binary frame)       │
│                                                   │
│   aiohttp WebSocket (receive JSON)                │
│     → input_handler                               │
│         xdotool  (Linux X11)                      │
│         ydotool  (Linux Wayland)                  │
│         pynput   (Windows / macOS)                │
│                                                   │
│   CloudflareTunnel (optional)                     │
│     → cloudflared subprocess                      │
│     → public trycloudflare.com URL                │
└───────────────────────────────────────────────────┘
```

**Key design decisions:**

- **Single port** — HTTP and WebSocket share port 8080 (`/ws` endpoint). One firewall rule, one Cloudflare Tunnel entry.
- **Frame skip** — An MD5 hash of sampled screen pixels is compared each frame. If unchanged, encoding and sending are skipped entirely — saving CPU and bandwidth when the screen is idle.
- **ImageBitmap rendering** — Frames are decoded off the main thread in the browser for smooth rendering without blocking.
- **Input throttle** — Mouse move events are throttled to one per animation frame (16ms) so the server isn't flooded.

---

## 📋 Requirements

| Platform | System package | Python packages |
|----------|---------------|-----------------|
| **Linux X11** | `xdotool` | `aiohttp mss Pillow PyYAML netifaces` |
| **Linux Wayland** | `ydotool` + `ydotoold` daemon | same as above |
| **Windows** | — | above + `pynput` |
| **macOS** | — | above + `pynput` |

**Optional extras:**

| Extra | Install | Benefit |
|-------|---------|---------|
| TurboJPEG | `sudo apt install libturbojpeg0` + `pip install PyTurboJPEG` | 10× faster JPEG encoding |
| System tray | `pip install pystray` | Tray icon on Windows/macOS/Linux |
| Remote access | Install `cloudflared` binary | Access from anywhere |

---

## 🔍 Troubleshooting

### "xdotool not found" (Linux X11)
```bash
sudo apt install xdotool       # Debian / Ubuntu / Mint
sudo dnf install xdotool       # Fedora
sudo pacman -S xdotool         # Arch
```

### Cursor doesn't move on Wayland
```bash
sudo apt install ydotool
sudo systemctl enable --now ydotoold
```

### Can't connect from my phone
1. Phone and PC must be on the **same Wi-Fi network**
2. Allow port 8080 through your firewall:
   ```bash
   sudo ufw allow 8080          # Linux
   # Windows: Windows Defender Firewall → Allow an app → add python.exe
   ```
3. Run `couch-control ip` to confirm the correct IP address
4. Try navigating to `http://<IP>:8080/ping` — it should return `pong`

### High CPU / lag
```bash
couch-control start --quality 40 --fps 15 --scale 0.5
```

### Mouse doesn't move on Windows
```bash
pip install pynput
```

### Cloudflare Tunnel URL not appearing
```bash
couch-control tunnel check    # Verify cloudflared is on PATH
```
If not found, install it per the [Remote Access](#-remote-access--cloudflare-tunnel) section.

### Screen is black / blank
- On Wayland, `mss` may need `DISPLAY=:0` exported. The systemd service already sets this.
- On multi-monitor setups, try `--monitor 1` to capture a specific screen.

---

## 🔒 Security

Couch Control is designed for **controlled use**. Keep these points in mind:

| Risk | Mitigation |
|------|-----------|
| Unauthorized local access | Set a PIN: `--pin 1234` |
| Too many clients | `max_clients: 3` (default) rejects extra connections |
| Brute-force PIN guessing | IP locked for 60s after 5 wrong attempts |
| Tunnel access without PIN | PIN is **automatically required** when tunnel is active |
| Idle sessions | Server auto-stops after 30 minutes with no activity |
| Malicious input | All coordinates and key events validated server-side |
| Network sniffing | Use `--cloudflare` (HTTPS/WSS) or provide your own TLS cert |

---

## 🆕 What's New in v2.0

**v2.0.0** is a major upgrade from v1.0.0.

### Architecture
- ✅ **Single port** — WebSocket and HTTP now share port 8080 (`/ws` path). No more dual-port setup.
- ✅ **Frame skip** — Server compares frame hashes and only sends when the screen actually changes.
- ✅ **ImageBitmap rendering** — Frames decoded off the main thread for smoother playback.
- ✅ **Input throttle** — Mouse moves batched to one per animation frame.

### New features
- ✅ **Cloudflare Tunnel** — One flag (`--cloudflare`) gives you a public HTTPS URL from anywhere.
- ✅ **Windows support** — Full pynput-based input, Task Scheduler startup, `.exe` build.
- ✅ **Wayland support** — Auto-detects session type and switches to `ydotool`.
- ✅ **Ctrl+Shift+C / Ctrl+Shift+V** — Terminal copy/paste buttons in the keyboard panel.
- ✅ **Two-finger scroll** — Scroll in Mouse Mode without switching to View Mode.
- ✅ **Clipboard paste** — Send your phone clipboard directly to the desktop.
- ✅ **PIN authentication** — Enforced in WebSocket handshake with rate limiting.
- ✅ **Max clients** — Enforced at connection time (HTTP 429 before WebSocket upgrade).
- ✅ **Settings panel** — Slide-up sheet with quality slider, resolution, theme selector.
- ✅ **FPS + latency display** — Live stats in the status bar.
- ✅ **Dark / Light / Auto theme** — Persisted in `localStorage`.
- ✅ **PWA** — Manifest + icons — add to phone home screen.
- ✅ **System tray** — Optional `pystray` tray icon with start/stop/tunnel controls.
- ✅ **TLS support** — Provide your own cert/key for HTTPS.
- ✅ **Exponential backoff** — Reconnects wait 2s → 4s → 8s → max 30s.

### Bug fixes
- ✅ PIN was declared in config but never actually checked — fixed.
- ✅ `max_clients` config was ignored — fixed.
- ✅ Image blob memory leak in JS frame renderer — fixed.
- ✅ Long-press timer logic bug caused spurious clicks — fixed.
- ✅ Stale duplicate fallback HTML in `server.py` — removed.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

Made with ❤️ by [sithulaka](https://github.com/sithulaka)
