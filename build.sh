#!/bin/bash
# Build a standalone Couch Control binary for Linux or macOS
set -e

PLATFORM=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)
OUTPUT="dist/couch-control-${PLATFORM}-${ARCH}"

echo "🛋️  Building Couch Control for ${PLATFORM}/${ARCH}..."
echo ""

# Install PyInstaller if not present
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    pip install pyinstaller
fi

# Clean previous build
rm -rf build dist __pycache__ couch-control.spec

# Build
pyinstaller \
    --onefile \
    --name couch-control \
    --add-data "couch_control/static:couch_control/static" \
    --hidden-import aiohttp \
    --hidden-import mss \
    --hidden-import PIL \
    --hidden-import yaml \
    --hidden-import netifaces \
    --hidden-import pynput.keyboard \
    --hidden-import pynput.mouse \
    main.py

# Rename with platform suffix
mv dist/couch-control "${OUTPUT}"
chmod +x "${OUTPUT}"

# Checksum
sha256sum "${OUTPUT}" > "${OUTPUT}.sha256"

echo ""
echo "✅  Build complete!"
echo "    Binary:   ${OUTPUT}"
echo "    Checksum: ${OUTPUT}.sha256"
echo ""
echo "Run it:"
echo "    ./${OUTPUT} start"
echo "    ./${OUTPUT} start --cloudflare --pin 1234"
