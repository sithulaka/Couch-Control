# Couch Control 🛋️

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux-orange.svg)](https://www.linux.org/)

Ultra-lightweight remote desktop control for your local network. Control your Linux desktop from your phone's browser while relaxing on the couch.

**Perfect for developers** who need to click "Allow" buttons or type prompts for AI agents (Claude Code, Gemini, etc.) without getting up from the couch!

## ✨ Features

- **🚀 Real-time WebSocket streaming** - Bidirectional communication with ~50ms latency
- **💨 Ultra-lightweight** - < 50MB RAM when streaming
- **🔌 No conflicts** - Works alongside KDE, GNOME, and other DEs
- **📱 Browser-based** - No app installation needed on your phone
- **👆 Touch-friendly** - Tap to click, long-press for right-click, drag to move
- **⌨️ Virtual keyboard** - Type text and send special keys
- **🔒 Secure** - Local network only, optional PIN protection

## 🚀 Quick Start

### 1. Install & Setup Service

The improved installer sets up everything for you, including the system service.

```bash
# Clone the repository
git clone https://github.com/sithulaka/Couch-Control.git
cd Couch-Control

# Run the setup script (installs dependencies + system service)
./setup_service.sh
```

### 2. Start

```bash
# Start the service
sudo systemctl start couch-control

# Check status
sudo systemctl status couch-control
```

The app runs automatically on startup!

### 3. Open on Your Phone

Open the Web UI URL shown in the logs (or find IP via `ip a`).


## 📖 Usage

### Control Modes

| Mode | Icon | Description |
|------|------|-------------|
| **Mouse Mode** (Default) | 🔍 Zoom | **Interact with Desktop.** Click, drag windows, type. Pan/Zoom is disabled. Press "Zoom" to switch to View Mode. |
| **View Mode** | 🔒 Lock | **Adjust View.** Pan (1 finger) or Zoom (2 fingers). Desktop interaction is disabled. Press "Lock" to switch back. |

### 👆 Touch Gestures (Mouse Mode)

| Gesture | Action |
|---------|--------|
| Tap | Left click (Jumps to finger) |
| Tap + Drag (in Drag Mode) | Click & Drag (Select text) |
| Long press (500ms) | Right click |
| Double tap | Double click |
| Scroll (mouse wheel) | Two-finger scroll (if supported) or use buttons |

### 🎮 Control Bar

- **👆 Select**: Toggle "Drag/Select Mode". When active, touching stamps "Left Click Down" so you can drag to select text.
- **🔍/🔒 Zoom/Lock**: Toggle between Mouse Mode (Interact) and View Mode (Pan/Zoom).
- **🎯 Reset**: Instantly reset view to center and 100% zoom.
- **⌨️ Kbd**: Show virtual keyboard.
- **⛶ Full**: Toggle fullscreen.
- **🔄 Sync**: Reconnect WebSocket.

## ⚙️ Configuration

Create `config.yaml` in the project directory:

```yaml
server:
  port: 8080
  host: "0.0.0.0"

capture:
  quality: 70     # JPEG quality (10-95)
  fps: 24         # Frames per second
  scale: 0.75     # Scale factor (0.25-1.0)
  monitor: 0      # Monitor index

security:
  pin: ""         # Optional PIN
  timeout_minutes: 30

performance:
  max_clients: 3
```

## 📋 Requirements

- **OS**: Linux (X11) - tested on Linux Mint, Ubuntu, Fedora
- **Python**: 3.10+
- **System packages**: `xdotool`

## 🔧 How It Works

```
┌─────────────────────────────────────────────────────┐
│               COUCH CONTROL SERVER                  │
│                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │   Screen    │  │  WebSocket  │  │    Input    │ │
│  │   Capture   │─▶│   Server    │◀─│   Handler   │ │
│  │   (mss)     │  │             │  │  (xdotool)  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
│                          │                          │
└──────────────────────────│──────────────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Phone Browser  │
                  │    <canvas>     │
                  └─────────────────┘
```

1. **Screen Capture**: Uses `mss` for efficient X11 screen capture
2. **JPEG Encoding**: Compresses frames using Pillow
3. **WebSocket Streaming**: Binary frames sent in real-time (bidirectional)
4. **Input Handling**: Uses `xdotool` for mouse/keyboard injection

## 🔍 Troubleshooting

### "xdotool not found"

```bash
sudo apt install xdotool
```

### High CPU usage

Lower quality and FPS:
```bash
couch-control start --quality 40 --fps 15
```

### Can't connect from phone

1. Make sure you're on the same WiFi network
2. Check firewall allows ports 8080 and 8081
3. Run `couch-control ip` to verify the correct IP

### Wayland support

Currently X11 only. For Wayland, switch to X11 session or use XWayland.

## 🔒 Security Notes

- Only accessible on your local network
- No internet traffic (all local)
- Optional PIN authentication
- Auto-stops after 30 minutes of inactivity
- No data is stored or logged

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

Made with ❤️ by [sithulaka](https://github.com/sithulaka)
