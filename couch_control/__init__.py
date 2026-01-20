"""
Couch Control - Ultra-Lightweight Remote Desktop Control

A minimal, on-demand screen sharing and remote control solution
for local network use. Designed for extremely low RAM usage.

Features:
- MJPEG streaming over HTTP (works in any browser)
- Mouse and keyboard input via xdotool
- Auto-timeout for security
- No conflicts with KDE/GNOME

Usage:
    couch-control start   # Start the server
    couch-control stop    # Stop the server
    couch-control status  # Check server status
    couch-control ip      # Show local IP address
"""

__version__ = "1.0.0"
__author__ = "Couch Control"
