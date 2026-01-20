"""
Input handler using xdotool for mouse and keyboard control.
Uses subprocess calls for zero Python memory overhead.
"""

import subprocess
import shutil
from typing import Optional, Tuple


class InputHandler:
    """
    Handle mouse and keyboard input using xdotool.
    
    xdotool is used via subprocess to avoid Python library overhead.
    This approach uses virtually zero RAM beyond the subprocess itself.
    """
    
    def __init__(self):
        """Initialize the input handler."""
        self._xdotool_path = shutil.which("xdotool")
        self._ydotool_path = shutil.which("ydotool")  # Wayland fallback
        
        if not self._xdotool_path:
            raise RuntimeError(
                "xdotool not found. Please install it:\n"
                "  sudo apt install xdotool"
            )
        
        # Get screen dimensions for coordinate mapping
        self._screen_width: Optional[int] = None
        self._screen_height: Optional[int] = None
    
    def set_screen_size(self, width: int, height: int) -> None:
        """
        Set the screen size for coordinate normalization.
        
        Args:
            width: Screen width in pixels
            height: Screen height in pixels
        """
        self._screen_width = width
        self._screen_height = height
    
    def _run_xdotool(self, *args) -> bool:
        """
        Run xdotool with given arguments.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            subprocess.run(
                [self._xdotool_path, *args],
                check=True,
                capture_output=True,
                timeout=2
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False
    
    def move_mouse(self, x: float, y: float, normalized: bool = True) -> bool:
        """
        Move mouse to position.
        
        Args:
            x: X coordinate (0-1 if normalized, pixels otherwise)
            y: Y coordinate (0-1 if normalized, pixels otherwise)
            normalized: If True, x and y are 0-1 normalized coordinates
        
        Returns:
            True if successful
        """
        if normalized:
            if self._screen_width is None or self._screen_height is None:
                return False
            px = int(x * self._screen_width)
            py = int(y * self._screen_height)
        else:
            px = int(x)
            py = int(y)
        
        return self._run_xdotool("mousemove", str(px), str(py))
    
    def click(self, button: int = 1) -> bool:
        """
        Perform mouse click.
        
        Args:
            button: 1=left, 2=middle, 3=right
        
        Returns:
            True if successful
        """
        return self._run_xdotool("click", str(button))
    
    def click_at(self, x: float, y: float, button: int = 1, normalized: bool = True) -> bool:
        """
        Move mouse to position and click.
        
        Args:
            x: X coordinate
            y: Y coordinate
            button: 1=left, 2=middle, 3=right
            normalized: If True, coordinates are 0-1 normalized
        
        Returns:
            True if successful
        """
        if not self.move_mouse(x, y, normalized):
            return False
        return self.click(button)
    
    def double_click(self, button: int = 1) -> bool:
        """
        Perform double click.
        
        Args:
            button: 1=left, 2=middle, 3=right
        
        Returns:
            True if successful
        """
        return self._run_xdotool("click", "--repeat", "2", "--delay", "100", str(button))
    
    def mouse_down(self, button: int = 1) -> bool:
        """Press mouse button down."""
        return self._run_xdotool("mousedown", str(button))
    
    def mouse_up(self, button: int = 1) -> bool:
        """Release mouse button."""
        return self._run_xdotool("mouseup", str(button))
    
    def scroll(self, direction: str, amount: int = 3) -> bool:
        """
        Scroll mouse wheel.
        
        Args:
            direction: "up" or "down"
            amount: Number of scroll clicks
        
        Returns:
            True if successful
        """
        button = "4" if direction == "up" else "5"
        return self._run_xdotool("click", "--repeat", str(amount), button)
    
    def type_text(self, text: str) -> bool:
        """
        Type text using keyboard.
        
        Args:
            text: Text to type
        
        Returns:
            True if successful
        """
        if not text:
            return True
        
        # Use xdotool type with delay for reliability
        return self._run_xdotool("type", "--delay", "12", "--", text)
    
    def key_press(self, key: str) -> bool:
        """
        Press a key or key combination.
        
        Args:
            key: Key name (e.g., "Return", "BackSpace", "ctrl+c")
        
        Returns:
            True if successful
        """
        return self._run_xdotool("key", "--", key)
    
    def key_down(self, key: str) -> bool:
        """Press key down (without release)."""
        return self._run_xdotool("keydown", "--", key)
    
    def key_up(self, key: str) -> bool:
        """Release key."""
        return self._run_xdotool("keyup", "--", key)


# Singleton instance
_handler_instance: Optional[InputHandler] = None


def get_input_handler() -> InputHandler:
    """Get or create the input handler instance."""
    global _handler_instance
    
    if _handler_instance is None:
        _handler_instance = InputHandler()
    
    return _handler_instance


# Key name mapping from web key codes to xdotool key names
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
    "F1": "F1",
    "F2": "F2",
    "F3": "F3",
    "F4": "F4",
    "F5": "F5",
    "F6": "F6",
    "F7": "F7",
    "F8": "F8",
    "F9": "F9",
    "F10": "F10",
    "F11": "F11",
    "F12": "F12",
    "Control": "ctrl",
    "Alt": "alt",
    "Shift": "shift",
    "Meta": "super",
    " ": "space",
}


def translate_key(web_key: str) -> str:
    """Translate web key name to xdotool key name."""
    return KEY_MAP.get(web_key, web_key)
