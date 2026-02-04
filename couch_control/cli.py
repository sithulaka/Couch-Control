#!/usr/bin/env python3
"""
Couch Control CLI - Command line interface for starting/stopping the server.
"""

import argparse
import os
import signal
import sys
from pathlib import Path

# PID file location
PID_FILE = Path("/tmp/couch-control.pid")


def get_pid() -> int | None:
    """Get PID from file if exists."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            # Check if process is running
            os.kill(pid, 0)
            return pid
        except (ValueError, OSError):
            PID_FILE.unlink(missing_ok=True)
    return None


def write_pid() -> None:
    """Write current PID to file."""
    PID_FILE.write_text(str(os.getpid()))


def remove_pid() -> None:
    """Remove PID file."""
    PID_FILE.unlink(missing_ok=True)


def cmd_start(args) -> int:
    """Start the server."""
    # Check if already running
    existing_pid = get_pid()
    if existing_pid:
        print(f"❌ Couch Control is already running (PID: {existing_pid})")
        print(f"   Run 'couch-control stop' first")
        return 1
    
    # Import here to avoid loading when not needed
    from .config import Config, reload_config
    from .server import run_server
    
    # Create config with CLI overrides
    config = reload_config()
    
    # Override with CLI args if provided
    if args.port:
        config._config["server"]["port"] = args.port
    if args.quality:
        config._config["capture"]["quality"] = args.quality
    if args.fps:
        config._config["capture"]["fps"] = args.fps
    if args.scale:
        config._config["capture"]["scale"] = args.scale
    if args.pin:
        config._config["security"]["pin"] = args.pin
    
    # Write PID
    write_pid()
    
    try:
        run_server(config)
    except KeyboardInterrupt:
        pass
    finally:
        remove_pid()
    
    return 0


def cmd_stop(args) -> int:
    """Stop the server."""
    pid = get_pid()
    
    if not pid:
        print("ℹ️  Couch Control is not running")
        return 0
    
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"✅ Stopped Couch Control (PID: {pid})")
        remove_pid()
        return 0
    except OSError as e:
        print(f"❌ Failed to stop: {e}")
        remove_pid()
        return 1


def cmd_status(args) -> int:
    """Check server status."""
    pid = get_pid()
    
    if pid:
        print(f"✅ Couch Control is running (PID: {pid})")
        
        # Try to get more info
        try:
            from .config import get_config
            config = get_config()
            print(f"   URL: http://{config.host}:{config.port}")
        except Exception:
            pass
        
        return 0
    else:
        print("❌ Couch Control is not running")
        return 1


def cmd_ip(args) -> int:
    """Show local IP address."""
    from .config import get_local_ip
    
    ip = get_local_ip()
    print(f"📍 Local IP: {ip}")
    print(f"   URL: http://{ip}:8080")
    return 0


def cmd_config(args) -> int:
    """Show current configuration."""
    from .config import get_config, get_config_paths
    
    print("📝 Configuration:")
    print()
    
    # Show config file locations
    print("   Config file search paths:")
    for path in get_config_paths():
        exists = "✓" if path.exists() else " "
        print(f"   [{exists}] {path}")
    print()
    
    # Show current config
    config = get_config()
    print("   Current settings:")
    print(f"   - Host: {config.host}")
    print(f"   - Port: {config.port}")
    print(f"   - Quality: {config.quality}")
    print(f"   - FPS: {config.fps}")
    print(f"   - Scale: {config.scale}")
    print(f"   - Monitor: {config.monitor}")
    print(f"   - PIN: {'***' if config.pin else '(none)'}")
    print(f"   - Timeout: {config.timeout_minutes} minutes")
    print(f"   - TurboJPEG: {config.use_turbojpeg}")
    
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="couch-control",
        description="Ultra-lightweight remote desktop control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  couch-control start              # Start with default settings
  couch-control start --port 9090  # Start on different port
  couch-control start --pin 1234   # Start with PIN authentication
  couch-control stop               # Stop the server
  couch-control status             # Check if running
  couch-control ip                 # Show local IP address
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start the server")
    start_parser.add_argument("--port", "-p", type=int, help="Port number (default: 8080)")
    start_parser.add_argument("--quality", "-q", type=int, help="JPEG quality 1-95 (default: 50)")
    start_parser.add_argument("--fps", "-f", type=int, help="Frames per second (default: 15)")
    start_parser.add_argument("--scale", "-s", type=float, help="Scale factor 0.1-1.0 (default: 0.5)")
    start_parser.add_argument("--pin", type=str, help="PIN for authentication")
    start_parser.set_defaults(func=cmd_start)
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop the server")
    stop_parser.set_defaults(func=cmd_stop)
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check server status")
    status_parser.set_defaults(func=cmd_status)
    
    # IP command
    ip_parser = subparsers.add_parser("ip", help="Show local IP address")
    ip_parser.set_defaults(func=cmd_ip)
    
    # Config command
    config_parser = subparsers.add_parser("config", help="Show configuration")
    config_parser.set_defaults(func=cmd_config)
    
    # Parse args
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
