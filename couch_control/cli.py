#!/usr/bin/env python3
"""
Couch Control CLI — start / stop / status / tunnel management.
"""

import argparse
import os
import signal
import sys
from pathlib import Path

PID_FILE = Path("/tmp/couch-control.pid")


def get_pid() -> int | None:
    """Get PID from file if process is still running."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return pid
        except (ValueError, OSError):
            PID_FILE.unlink(missing_ok=True)
    return None


def write_pid() -> None:
    PID_FILE.write_text(str(os.getpid()))


def remove_pid() -> None:
    PID_FILE.unlink(missing_ok=True)


# ─────────────────────── Commands ────────────────────────────────────


def cmd_start(args) -> int:
    """Start the server."""
    existing_pid = get_pid()
    if existing_pid:
        print(f"❌ Couch Control is already running (PID: {existing_pid})")
        print(f"   Run 'couch-control stop' first")
        return 1

    from .config import reload_config
    from .server import run_server

    config = reload_config()

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
    if args.cloudflare:
        config._config["cloudflare"]["enabled"] = True
    if args.no_frame_skip:
        config._config["capture"]["frame_skip"] = False

    write_pid()

    # Optional system tray
    tray = None
    if args.tray:
        _start_tray(config, tray_ref_holder=[])

    try:
        run_server(config, enable_tunnel=args.cloudflare)
    except KeyboardInterrupt:
        pass
    finally:
        remove_pid()

    return 0


def _start_tray(config, tray_ref_holder):
    """Start system tray in background thread."""
    try:
        from .tray import SystemTray
        from .config import get_local_ip

        display_host = config.host
        if display_host == "0.0.0.0":
            display_host = get_local_ip()

        local_url = f"http://{display_host}:{config.port}"

        tray = SystemTray(
            local_url=local_url,
            on_stop=lambda: os.kill(os.getpid(), signal.SIGTERM),
        )
        tray.start()
        tray_ref_holder.append(tray)
    except Exception as e:
        print(f"Warning: Could not start system tray: {e}")


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
        try:
            from .config import get_config
            config = get_config()
            from .config import get_local_ip
            display_host = config.host if config.host != "0.0.0.0" else get_local_ip()
            print(f"   URL: http://{display_host}:{config.port}")
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

    print("   Config file search paths:")
    for path in get_config_paths():
        exists = "✓" if path.exists() else " "
        print(f"   [{exists}] {path}")
    print()

    config = get_config()
    print("   Current settings:")
    print(f"   - Host:           {config.host}")
    print(f"   - Port:           {config.port}")
    print(f"   - Quality:        {config.quality}")
    print(f"   - FPS:            {config.fps}")
    print(f"   - Scale:          {config.scale}")
    print(f"   - Monitor:        {config.monitor}")
    print(f"   - Frame skip:     {config.frame_skip}")
    print(f"   - PIN:            {'***' if config.pin else '(none)'}")
    print(f"   - Timeout:        {config.timeout_minutes} minutes")
    print(f"   - Max clients:    {config.max_clients}")
    print(f"   - TurboJPEG:      {config.use_turbojpeg}")
    print(f"   - Cloudflare:     {config.cloudflare_enabled}")
    print(f"   - TLS cert:       {config.tls_cert or '(none)'}")

    return 0


def cmd_tunnel(args) -> int:
    """Manage Cloudflare Tunnel."""
    from .tunnel import CloudflareTunnel

    sub = args.tunnel_cmd

    if sub == "check":
        if CloudflareTunnel.is_available():
            print("✅ cloudflared is installed and available")
        else:
            print("❌ cloudflared not found")
            print(CloudflareTunnel.is_available.__doc__ or "")
            print("\nInstall cloudflared:")
            print("  Linux:   curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared")
            print("  macOS:   brew install cloudflared")
            print("  Windows: Download from https://github.com/cloudflare/cloudflared/releases/latest")
        return 0

    if sub == "start":
        import asyncio

        port = args.port or 8080

        async def run():
            tunnel = CloudflareTunnel(port=port)
            url = await tunnel.start()
            if url:
                print(f"✅ Tunnel active: {url}")
                print("   Press Ctrl+C to stop.")
                try:
                    while True:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    pass
            else:
                print("❌ Tunnel failed to start")
            await tunnel.stop()

        try:
            asyncio.run(run())
        except KeyboardInterrupt:
            pass
        return 0

    print("Usage: couch-control tunnel [check|start]")
    return 1


# ─────────────────────── Entry point ─────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="couch-control",
        description="Lightweight remote desktop control — control your PC from your phone",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  couch-control start                    # Start with defaults
  couch-control start --port 9090        # Different port
  couch-control start --pin 1234         # Require PIN
  couch-control start --cloudflare       # Enable Cloudflare Tunnel
  couch-control start --tray             # Show system tray icon
  couch-control stop                     # Stop the server
  couch-control status                   # Check if running
  couch-control ip                       # Show local IP
  couch-control tunnel check             # Check cloudflared install
  couch-control tunnel start --port 8080 # Start tunnel only
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # start
    start_parser = subparsers.add_parser("start", help="Start the server")
    start_parser.add_argument("--port", "-p", type=int, help="Port (default: 8080)")
    start_parser.add_argument("--quality", "-q", type=int, help="JPEG quality 1-95 (default: 70)")
    start_parser.add_argument("--fps", "-f", type=int, help="Frames per second (default: 24)")
    start_parser.add_argument("--scale", "-s", type=float, help="Scale factor 0.1-1.0 (default: 0.75)")
    start_parser.add_argument("--pin", type=str, help="PIN for authentication")
    start_parser.add_argument("--cloudflare", action="store_true", help="Enable Cloudflare Tunnel")
    start_parser.add_argument("--tray", action="store_true", help="Show system tray icon")
    start_parser.add_argument("--no-frame-skip", action="store_true", help="Disable frame skip (send every frame)")
    start_parser.set_defaults(func=cmd_start)

    # stop
    stop_parser = subparsers.add_parser("stop", help="Stop the server")
    stop_parser.set_defaults(func=cmd_stop)

    # status
    status_parser = subparsers.add_parser("status", help="Check server status")
    status_parser.set_defaults(func=cmd_status)

    # ip
    ip_parser = subparsers.add_parser("ip", help="Show local IP address")
    ip_parser.set_defaults(func=cmd_ip)

    # config
    config_parser = subparsers.add_parser("config", help="Show configuration")
    config_parser.set_defaults(func=cmd_config)

    # tunnel
    tunnel_parser = subparsers.add_parser("tunnel", help="Manage Cloudflare Tunnel")
    tunnel_sub = tunnel_parser.add_subparsers(dest="tunnel_cmd")
    tunnel_sub.add_parser("check", help="Check if cloudflared is installed")
    tunnel_start = tunnel_sub.add_parser("start", help="Start a quick tunnel")
    tunnel_start.add_argument("--port", type=int, default=8080, help="Local port to tunnel")
    tunnel_parser.set_defaults(func=cmd_tunnel)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
