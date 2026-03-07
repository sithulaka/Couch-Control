"""
System tray icon for Couch Control (Windows / macOS / Linux with AppIndicator).

Requires pystray and Pillow:
    pip install pystray Pillow

The tray runs in a background daemon thread so it doesn't block the
asyncio event loop.
"""

import threading
import webbrowser
from typing import Callable, Optional

try:
    import pystray
    from PIL import Image, ImageDraw
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False


def _create_icon_image(size: int = 64, color: str = "#e94560") -> "Image.Image":
    """Generate a simple couch-icon image programmatically."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Simple rounded-rectangle icon
    margin = size // 8
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=size // 6,
        fill=color,
    )

    # Small 'C' letter in center
    cx, cy = size // 2, size // 2
    r = size // 5
    draw.arc([cx - r, cy - r, cx + r, cy + r], start=40, end=320, fill="white", width=max(2, size // 12))

    return img


class SystemTray:
    """
    System tray icon with start/stop/status controls.

    Runs pystray in a background daemon thread.
    Communicates with the server via callbacks.
    """

    def __init__(
        self,
        local_url: str,
        on_stop: Callable,
        get_tunnel_url: Callable[[], Optional[str]] = lambda: None,
        on_toggle_tunnel: Optional[Callable] = None,
    ):
        """
        Args:
            local_url: Local URL like http://192.168.1.x:8080
            on_stop: Callback to stop the server.
            get_tunnel_url: Callable that returns current tunnel URL or None.
            on_toggle_tunnel: Callback to toggle Cloudflare Tunnel on/off.
        """
        self.local_url = local_url
        self._on_stop = on_stop
        self._get_tunnel_url = get_tunnel_url
        self._on_toggle_tunnel = on_toggle_tunnel

        self._icon: Optional["pystray.Icon"] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        """Start the tray icon in a background thread. Returns False if pystray unavailable."""
        if not PYSTRAY_AVAILABLE:
            print("Info: pystray not installed — system tray disabled.")
            print("      To enable: pip install pystray")
            return False

        self._thread = threading.Thread(target=self._run, daemon=True, name="couch-tray")
        self._thread.start()
        return True

    def stop(self) -> None:
        """Stop the tray icon."""
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

    def update_tooltip(self, text: str) -> None:
        """Update the tray icon tooltip."""
        if self._icon:
            self._icon.title = text

    def _build_menu(self) -> "pystray.Menu":
        """Build the right-click context menu."""
        import pystray

        items = [
            pystray.MenuItem("Couch Control", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                f"Open Local: {self.local_url}",
                lambda: webbrowser.open(self.local_url),
            ),
        ]

        tunnel_url = self._get_tunnel_url()
        if tunnel_url:
            items.append(
                pystray.MenuItem(
                    f"Open Remote: {tunnel_url[:40]}...",
                    lambda: webbrowser.open(tunnel_url),
                )
            )

        if self._on_toggle_tunnel:
            label = "Disable Cloudflare Tunnel" if tunnel_url else "Enable Cloudflare Tunnel"
            items.append(pystray.MenuItem(label, self._toggle_tunnel))

        items += [
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Stop Server", self._stop_server),
        ]

        return pystray.Menu(*items)

    def _toggle_tunnel(self, icon, item) -> None:
        if self._on_toggle_tunnel:
            threading.Thread(target=self._on_toggle_tunnel, daemon=True).start()

    def _stop_server(self, icon, item) -> None:
        icon.stop()
        if self._on_stop:
            self._on_stop()

    def _run(self) -> None:
        """Entry point for the tray thread."""
        import pystray

        icon_image = _create_icon_image()

        self._icon = pystray.Icon(
            name="couch-control",
            icon=icon_image,
            title=f"Couch Control — {self.local_url}",
            menu=pystray.Menu(lambda: self._build_menu()),
        )

        self._icon.run()
