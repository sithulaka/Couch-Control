"""
Cloudflare Tunnel integration for Couch Control.

Uses the `cloudflared` binary to create a secure HTTPS tunnel
from Cloudflare's edge to localhost, enabling remote access
from anywhere in the world without port forwarding.

Usage:
    tunnel = CloudflareTunnel(port=8080)
    url = await tunnel.start()   # returns https://xxx.trycloudflare.com
    await tunnel.stop()
"""

import asyncio
import re
import shutil
from typing import Callable, Optional


TUNNEL_URL_PATTERN = re.compile(r'https://[a-z0-9\-]+\.trycloudflare\.com')
INSTALL_INSTRUCTIONS = """
cloudflared not found. Install it:

  Linux (amd64):
    curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \\
         -o /usr/local/bin/cloudflared
    chmod +x /usr/local/bin/cloudflared

  macOS:
    brew install cloudflared

  Windows:
    Download from: https://github.com/cloudflare/cloudflared/releases/latest
    Add cloudflared.exe to your PATH.
"""


class CloudflareTunnel:
    """Manages a Cloudflare Quick Tunnel via the cloudflared subprocess."""

    def __init__(self, port: int, on_url: Optional[Callable[[str], None]] = None):
        """
        Args:
            port: Local HTTP port to tunnel to.
            on_url: Optional callback fired with the public URL when the tunnel is ready.
        """
        self.port = port
        self.on_url = on_url
        self.public_url: Optional[str] = None
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._url_found = asyncio.Event()

    @staticmethod
    def is_available() -> bool:
        """Return True if cloudflared binary is on PATH."""
        return shutil.which("cloudflared") is not None

    async def start(self, timeout: float = 30.0) -> Optional[str]:
        """
        Start the tunnel and wait for the public URL.

        Returns:
            The public HTTPS URL, or None if it couldn't be established.
        Raises:
            RuntimeError: If cloudflared is not installed.
        """
        if not self.is_available():
            raise RuntimeError(INSTALL_INSTRUCTIONS)

        print("Starting Cloudflare Tunnel...")

        self._proc = await asyncio.create_subprocess_exec(
            "cloudflared", "tunnel", "--url", f"http://localhost:{self.port}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Monitor stderr for the tunnel URL (cloudflared logs to stderr)
        asyncio.create_task(self._monitor_output())

        # Wait for URL with timeout
        try:
            await asyncio.wait_for(self._url_found.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            print("Warning: Cloudflare Tunnel URL not received within timeout.")
            return None

        return self.public_url

    async def _monitor_output(self) -> None:
        """Read cloudflared stderr and extract the tunnel URL."""
        if not self._proc or not self._proc.stderr:
            return

        try:
            while True:
                line = await self._proc.stderr.readline()
                if not line:
                    break

                decoded = line.decode("utf-8", errors="replace")

                # Look for the tunnel URL in output
                match = TUNNEL_URL_PATTERN.search(decoded)
                if match and not self.public_url:
                    self.public_url = match.group(0)
                    self._url_found.set()
                    print(f"Cloudflare Tunnel active: {self.public_url}")
                    if self.on_url:
                        self.on_url(self.public_url)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Tunnel monitor error: {e}")

    async def stop(self) -> None:
        """Stop the tunnel gracefully."""
        if self._proc:
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._proc.kill()
            except Exception:
                pass
            finally:
                self._proc = None
                self.public_url = None
                self._url_found.clear()
                print("Cloudflare Tunnel stopped.")

    @property
    def is_running(self) -> bool:
        """Return True if the tunnel process is active."""
        return self._proc is not None and self._proc.returncode is None

    def status(self) -> dict:
        """Return tunnel status as a dictionary."""
        return {
            "running": self.is_running,
            "url": self.public_url,
            "available": self.is_available(),
        }
