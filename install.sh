#!/bin/bash
# Quick install script for Couch Control

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

echo "✅ Python $PYTHON_VERSION detected"

# Check/install xdotool
if ! command -v xdotool &> /dev/null; then
    echo "📦 Installing xdotool..."
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

# Install Python package
echo "📦 Installing Python dependencies..."
pip install -e . --quiet

echo "✅ Python packages installed"

# Check for turbojpeg (optional)
if python3 -c "from turbojpeg import TurboJPEG" 2>/dev/null; then
    echo "✅ TurboJPEG available (fast mode)"
else
    echo "ℹ️  TurboJPEG not installed (optional, for faster encoding)"
    echo "   To install: sudo apt install libturbojpeg0 && pip install PyTurboJPEG"
fi

echo ""
echo "🎉 Installation complete!"
echo ""
echo "Quick start:"
echo "  couch-control start"
echo ""
echo "Then open the URL on your phone!"
