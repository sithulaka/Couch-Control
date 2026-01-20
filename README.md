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

### 1. Install

```bash
# Clone the repository
git clone https://github.com/sithulaka/Couch-Control.git
cd Couch-Control

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the package
pip install -e .

# Install system dependency
sudo apt install xdotool
```

### 2. Run

```bash
# Start the server
couch-control start

# It will show something like:
# 🛋️  Couch Control started!
#    Web UI:    http://192.168.1.100:8080
#    WebSocket: ws://192.168.1.100:8081
```

### 3. Open on Your Phone

Open the Web UI URL in your phone's browser. That's it!

## 📖 Usage

### CLI Commands

```bash
couch-control start              # Start the server
couch-control start --port 9090  # Use different port
couch-control start --pin 1234   # Require PIN authentication
couch-control start --quality 70 # Higher quality (more bandwidth)
couch-control start --fps 30     # Higher FPS (more CPU)

couch-control stop               # Stop the server
couch-control status             # Check if running
couch-control ip                 # Show your local IP address
couch-control config             # Show current configuration
```

### 👆 Touch Gestures

| Gesture | Action |
|---------|--------|
| Tap | Left click |
| Long press (500ms) | Right click |
| Drag | Move mouse |
| Double tap | Double click |
| Scroll (mouse wheel) | Scroll up/down |
| Right-click (desktop) | Right click |

### ⌨️ Keyboard

Tap the ⌨️ button to show the virtual keyboard. Type your text and press Send.

Special keys available:
- Enter, Backspace, Tab, Escape, Space
- Arrow keys (↑ ↓ ← →)
- Ctrl+C, Ctrl+V, Ctrl+Z

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
