#!/bin/bash
# Couch Control — Linux/macOS install script

set -e

echo "🛋️  Installing Couch Control..."
echo ""

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python 3.10+ required. Found: Python $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python $PYTHON_VERSION"

# Detect display server
if [ -n "$WAYLAND_DISPLAY" ] || [ "$XDG_SESSION_TYPE" = "wayland" ]; then
    DISPLAY_SERVER="wayland"
else
    DISPLAY_SERVER="x11"
fi
echo "✅ Display server: $DISPLAY_SERVER"

# Install system input tool
if [ "$DISPLAY_SERVER" = "wayland" ]; then
    if ! command -v ydotool &> /dev/null; then
        echo "📦 Installing ydotool (Wayland input control)..."
        if command -v apt &> /dev/null; then
            sudo apt install -y ydotool
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y ydotool
        elif command -v pacman &> /dev/null; then
            sudo pacman -S --noconfirm ydotool
        else
            echo "⚠️  Please install ydotool manually, then run: sudo systemctl enable --now ydotoold"
        fi
    fi
    echo "✅ ydotool installed"
else
    if ! command -v xdotool &> /dev/null; then
        echo "📦 Installing xdotool (X11 input control)..."
        if command -v apt &> /dev/null; then
            sudo apt install -y xdotool
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y xdotool
        elif command -v pacman &> /dev/null; then
            sudo pacman -S --noconfirm xdotool
        else
            echo "❌ Please install xdotool manually"
            exit 1
        fi
    fi
    echo "✅ xdotool installed"
fi

# Install Python package
echo "📦 Installing Python dependencies..."
pip install -e . --quiet
echo "✅ Couch Control installed"

# Check for TurboJPEG (optional, for faster encoding)
if python3 -c "from turbojpeg import TurboJPEG" 2>/dev/null; then
    echo "✅ TurboJPEG available (fast JPEG mode)"
else
    echo "ℹ️  TurboJPEG not installed (optional)"
    echo "   To install: sudo apt install libturbojpeg0 && pip install PyTurboJPEG"
fi

# Check for pystray (optional, for system tray)
if python3 -c "import pystray" 2>/dev/null; then
    echo "✅ pystray available (system tray mode)"
else
    echo "ℹ️  pystray not installed (optional, for system tray icon)"
    echo "   To install: pip install pystray"
fi

# Check for cloudflared (optional)
if command -v cloudflared &> /dev/null; then
    echo "✅ cloudflared installed (remote access via Cloudflare Tunnel)"
else
    echo "ℹ️  cloudflared not installed (optional, for remote access)"
    echo "   To install:"
    echo "   curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \\"
    echo "        -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared"
fi

echo ""
echo "🎉 Installation complete!"
echo ""
echo "Quick start:"
echo "  couch-control start                   # Local network only"
echo "  couch-control start --cloudflare       # With remote tunnel"
echo "  couch-control start --pin 1234         # With PIN protection"
echo "  couch-control start --tray             # With system tray icon"
echo ""
echo "Then open the URL on your phone!"
