#!/bin/bash

# Setup Couch Control System Service

SERVICE_NAME="couch-control"
SERVICE_FILE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
CURRENT_DIR=$(pwd)
USER_NAME=$(whoami)

# Detect python venv
if [ -d ".venv" ]; then
    PYTHON_EXEC="${CURRENT_DIR}/.venv/bin/python3"
else
    PYTHON_EXEC=$(which python3)
fi

echo "Installing Couch Control Service..."
echo "  User: ${USER_NAME}"
echo "  Dir:  ${CURRENT_DIR}"
echo "  Python: ${PYTHON_EXEC}"

# Create temporary service file
cat > /tmp/${SERVICE_NAME}.service << EOF
[Unit]
Description=Couch Control - Remote Desktop Control
After=network.target graphical.target
Wants=graphical.target

[Service]
Type=simple
Environment=DISPLAY=:0
ExecStart=${PYTHON_EXEC} -m couch_control start --port 8787
ExecStop=${PYTHON_EXEC} -m couch_control stop
Restart=on-failure
RestartSec=5
User=${USER_NAME}
WorkingDirectory=${CURRENT_DIR}

[Install]
WantedBy=default.target
EOF

# Install Service
echo "Requesting sudo permissions to install service to ${SERVICE_FILE_PATH}..."
sudo mv /tmp/${SERVICE_NAME}.service ${SERVICE_FILE_PATH}
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}

echo "Service installed and enabled."
echo "You can start it now with: sudo systemctl start ${SERVICE_NAME}"
