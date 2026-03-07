#!/bin/bash
# Setup Couch Control as a systemd service

SERVICE_NAME="couch-control"
SERVICE_FILE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
CURRENT_DIR=$(pwd)
USER_NAME=$(whoami)

# Detect Python executable
if [ -d ".venv" ]; then
    PYTHON_EXEC="${CURRENT_DIR}/.venv/bin/python3"
else
    PYTHON_EXEC=$(which python3)
fi

# Parse optional arguments
CLOUDFLARE_FLAG=""
PIN_FLAG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --cloudflare) CLOUDFLARE_FLAG="--cloudflare"; shift ;;
        --pin) PIN_FLAG="--pin $2"; shift 2 ;;
        *) shift ;;
    esac
done

echo "Installing Couch Control Service..."
echo "  User:       ${USER_NAME}"
echo "  Directory:  ${CURRENT_DIR}"
echo "  Python:     ${PYTHON_EXEC}"
if [ -n "$CLOUDFLARE_FLAG" ]; then
    echo "  Cloudflare: enabled"
fi

cat > /tmp/${SERVICE_NAME}.service << EOF
[Unit]
Description=Couch Control - Remote Desktop Control
After=network.target graphical.target
Wants=graphical.target

[Service]
Type=simple
Environment=DISPLAY=:0
ExecStart=${PYTHON_EXEC} -m couch_control start ${CLOUDFLARE_FLAG} ${PIN_FLAG}
ExecStop=${PYTHON_EXEC} -m couch_control stop
Restart=on-failure
RestartSec=5
User=${USER_NAME}
WorkingDirectory=${CURRENT_DIR}

[Install]
WantedBy=default.target
EOF

echo "Installing service to ${SERVICE_FILE_PATH}..."
sudo mv /tmp/${SERVICE_NAME}.service ${SERVICE_FILE_PATH}
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}

echo ""
echo "✅ Service installed and enabled."
echo ""
echo "Commands:"
echo "  sudo systemctl start ${SERVICE_NAME}    # Start now"
echo "  sudo systemctl stop ${SERVICE_NAME}     # Stop"
echo "  sudo systemctl status ${SERVICE_NAME}   # Check status"
echo "  journalctl -u ${SERVICE_NAME} -f        # View logs"
echo ""
echo "The service will start automatically on next boot."
