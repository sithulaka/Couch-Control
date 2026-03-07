"""
Input handler — auto-selects backend based on platform and display server.

Backends:
  - X11  (Linux, X11 session)  → xdotool subprocess
  - Wayland (Linux, Wayland)   → ydotool subprocess
  - Windows                    → pynput
"""

import os
import sys
import shutil
import subprocess
from typing import Optional


def _detect_platform() -> str:
    """Detect the current platform and display server."""
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"

    # Linux: check for Wayland
    wayland_display = os.environ.get("WAYLAND_DISPLAY", "")
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if wayland_display or session_type == "wayland":
        return "wayland"

    return "x11"


# ─────────────────────────── X11 Backend ────────────────────────────


class X11InputHandler:
    """Handle input using xdotool (X11 only)."""

    def __init__(self):
        self._xdotool_path = shutil.which("xdotool")
        if not self._xdotool_path:
            raise RuntimeError(
                "xdotool not found. Install it:\n"
                "  sudo apt install xdotool        # Debian/Ubuntu\n"
                "  sudo dnf install xdotool        # Fedora\n"
                "  sudo pacman -S xdotool          # Arch"
            )
        self._screen_width: Optional[int] = None
        self._screen_height: Optional[int] = None

    def set_screen_size(self, width: int, height: int) -> None:
        self._screen_width = width
        self._screen_height = height

    def _run(self, *args) -> bool:
        try:
            subprocess.run(
                [self._xdotool_path, *args],
                check=True,
                capture_output=True,
                timeout=2,
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _to_px(self, x: float, y: float, normalized: bool):
        if normalized:
            if self._screen_width is None:
                return None, None
            return int(x * self._screen_width), int(y * self._screen_height)
        return int(x), int(y)

    def move_mouse(self, x: float, y: float, normalized: bool = True) -> bool:
        px, py = self._to_px(x, y, normalized)
        if px is None:
            return False
        return self._run("mousemove", str(px), str(py))

    def click(self, button: int = 1) -> bool:
        return self._run("click", str(button))

    def click_at(self, x: float, y: float, button: int = 1, normalized: bool = True) -> bool:
        if not self.move_mouse(x, y, normalized):
            return False
        return self.click(button)

    def double_click(self, button: int = 1) -> bool:
        return self._run("click", "--repeat", "2", "--delay", "100", str(button))

    def mouse_down(self, button: int = 1) -> bool:
        return self._run("mousedown", str(button))

    def mouse_up(self, button: int = 1) -> bool:
        return self._run("mouseup", str(button))

    def scroll(self, direction: str, amount: int = 3) -> bool:
        button = "4" if direction == "up" else "5"
        return self._run("click", "--repeat", str(amount), button)

    def type_text(self, text: str) -> bool:
        if not text:
            return True
        return self._run("type", "--delay", "12", "--", text)

    def key_press(self, key: str) -> bool:
        return self._run("key", "--", key)

    def key_down(self, key: str) -> bool:
        return self._run("keydown", "--", key)

    def key_up(self, key: str) -> bool:
        return self._run("keyup", "--", key)


# ─────────────────────────── Wayland Backend ────────────────────────


class WaylandInputHandler(X11InputHandler):
    """Handle input using ydotool (Wayland)."""

    def __init__(self):
        self._xdotool_path = shutil.which("ydotool")
        if not self._xdotool_path:
            raise RuntimeError(
                "ydotool not found. Install it:\n"
                "  sudo apt install ydotool\n"
                "Also ensure ydotoold daemon is running:\n"
                "  sudo systemctl enable --now ydotoold"
            )
        self._screen_width: Optional[int] = None
        self._screen_height: Optional[int] = None

    # ydotool uses the same CLI interface as xdotool for basic commands
    # so inheriting X11InputHandler works for most operations.


# ─────────────────────────── Windows Backend ────────────────────────


class WindowsInputHandler:
    """Handle input using pynput (Windows / macOS)."""

    def __init__(self):
        try:
            from pynput.mouse import Controller as MouseController, Button
            from pynput.keyboard import Controller as KeyController, Key, KeyCode
        except ImportError:
            raise RuntimeError(
                "pynput not found. Install it:\n"
                "  pip install pynput"
            )

        self._mouse = MouseController()
        self._keyboard = KeyController()
        self._Button = Button
        self._Key = Key
        self._KeyCode = KeyCode

        self._screen_width: Optional[int] = None
        self._screen_height: Optional[int] = None

    def set_screen_size(self, width: int, height: int) -> None:
        self._screen_width = width
        self._screen_height = height

    def _to_px(self, x: float, y: float, normalized: bool):
        if normalized:
            if self._screen_width is None:
                return None, None
            return int(x * self._screen_width), int(y * self._screen_height)
        return int(x), int(y)

    def move_mouse(self, x: float, y: float, normalized: bool = True) -> bool:
        px, py = self._to_px(x, y, normalized)
        if px is None:
            return False
        self._mouse.position = (px, py)
        return True

    def click(self, button: int = 1) -> bool:
        btn = self._Button.left if button == 1 else (self._Button.middle if button == 2 else self._Button.right)
        self._mouse.click(btn)
        return True

    def click_at(self, x: float, y: float, button: int = 1, normalized: bool = True) -> bool:
        if not self.move_mouse(x, y, normalized):
            return False
        return self.click(button)

    def double_click(self, button: int = 1) -> bool:
        btn = self._Button.left if button == 1 else self._Button.right
        self._mouse.click(btn, 2)
        return True

    def mouse_down(self, button: int = 1) -> bool:
        btn = self._Button.left if button == 1 else (self._Button.middle if button == 2 else self._Button.right)
        self._mouse.press(btn)
        return True

    def mouse_up(self, button: int = 1) -> bool:
        btn = self._Button.left if button == 1 else (self._Button.middle if button == 2 else self._Button.right)
        self._mouse.release(btn)
        return True

    def scroll(self, direction: str, amount: int = 3) -> bool:
        dy = amount if direction == "up" else -amount
        self._mouse.scroll(0, dy)
        return True

    def type_text(self, text: str) -> bool:
        if not text:
            return True
        self._keyboard.type(text)
        return True

    def _parse_key_combo(self, key_str: str):
        """Parse 'ctrl+shift+c' into a list of pynput keys."""
        Key = self._Key
        KeyCode = self._KeyCode

        modifier_map = {
            "ctrl": Key.ctrl,
            "control": Key.ctrl,
            "shift": Key.shift,
            "alt": Key.alt,
            "super": Key.cmd,
            "win": Key.cmd,
            "meta": Key.cmd,
        }

        special_map = {
            "Return": Key.enter,
            "return": Key.enter,
            "enter": Key.enter,
            "BackSpace": Key.backspace,
            "backspace": Key.backspace,
            "Tab": Key.tab,
            "tab": Key.tab,
            "Escape": Key.esc,
            "escape": Key.esc,
            "Delete": Key.delete,
            "delete": Key.delete,
            "Up": Key.up,
            "up": Key.up,
            "Down": Key.down,
            "down": Key.down,
            "Left": Key.left,
            "left": Key.left,
            "Right": Key.right,
            "right": Key.right,
            "Home": Key.home,
            "home": Key.home,
            "End": Key.end,
            "end": Key.end,
            "Page_Up": Key.page_up,
            "Page_Down": Key.page_down,
            "Insert": Key.insert,
            "space": Key.space,
            "F1": Key.f1, "F2": Key.f2, "F3": Key.f3, "F4": Key.f4,
            "F5": Key.f5, "F6": Key.f6, "F7": Key.f7, "F8": Key.f8,
            "F9": Key.f9, "F10": Key.f10, "F11": Key.f11, "F12": Key.f12,
        }

        parts = key_str.split("+")
        keys = []
        for part in parts:
            if part.lower() in modifier_map:
                keys.append(modifier_map[part.lower()])
            elif part in special_map:
                keys.append(special_map[part])
            elif len(part) == 1:
                keys.append(KeyCode(char=part))
            else:
                keys.append(KeyCode(char=part))
        return keys

    def key_press(self, key: str) -> bool:
        keys = self._parse_key_combo(key)
        for k in keys:
            self._keyboard.press(k)
        for k in reversed(keys):
            self._keyboard.release(k)
        return True

    def key_down(self, key: str) -> bool:
        keys = self._parse_key_combo(key)
        for k in keys:
            self._keyboard.press(k)
        return True

    def key_up(self, key: str) -> bool:
        keys = self._parse_key_combo(key)
        for k in reversed(keys):
            self._keyboard.release(k)
        return True


# ─────────────────────── macOS Backend ──────────────────────────────

# macOS reuses WindowsInputHandler (pynput supports macOS too)
MacOSInputHandler = WindowsInputHandler


# ─────────────────────── Factory ────────────────────────────────────

InputHandler = X11InputHandler  # type alias for type hints

_handler_instance: Optional[object] = None


def get_input_handler():
    """Get or create the input handler for the current platform."""
    global _handler_instance

    if _handler_instance is None:
        platform = _detect_platform()

        if platform == "windows":
            _handler_instance = WindowsInputHandler()
        elif platform == "macos":
            _handler_instance = MacOSInputHandler()
        elif platform == "wayland":
            try:
                _handler_instance = WaylandInputHandler()
            except RuntimeError:
                # Fall back to X11 via XWayland if ydotool not available
                print("Warning: ydotool not found, falling back to xdotool (XWayland)")
                _handler_instance = X11InputHandler()
        else:
            _handler_instance = X11InputHandler()

    return _handler_instance


# Key name mapping from web key codes to xdotool/ydotool key names
KEY_MAP = {
    "Enter": "Return",
    "Backspace": "BackSpace",
    "Tab": "Tab",
    "Escape": "Escape",
    "Delete": "Delete",
    "ArrowUp": "Up",
    "ArrowDown": "Down",
    "ArrowLeft": "Left",
    "ArrowRight": "Right",
    "Home": "Home",
    "End": "End",
    "PageUp": "Page_Up",
    "PageDown": "Page_Down",
    "Insert": "Insert",
    "F1": "F1", "F2": "F2", "F3": "F3", "F4": "F4",
    "F5": "F5", "F6": "F6", "F7": "F7", "F8": "F8",
    "F9": "F9", "F10": "F10", "F11": "F11", "F12": "F12",
    "Control": "ctrl",
    "Alt": "alt",
    "Shift": "shift",
    "Meta": "super",
    " ": "space",
}


def translate_key(web_key: str) -> str:
    """Translate web key name to xdotool/pynput key name."""
    return KEY_MAP.get(web_key, web_key)
