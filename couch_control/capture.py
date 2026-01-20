"""
Screen capture module using mss for ultra-low memory usage.
Supports turbojpeg for fast encoding, falls back to Pillow.
"""

import io
from typing import Optional, Tuple

import mss
import mss.tools

# Try to import turbojpeg for faster encoding
try:
    from turbojpeg import TurboJPEG, TJPF_BGRA, TJSAMP_420
    TURBOJPEG_AVAILABLE = True
    _jpeg = TurboJPEG()
except ImportError:
    TURBOJPEG_AVAILABLE = False
    _jpeg = None

# Fallback to Pillow
from PIL import Image


class ScreenCapture:
    """
    Ultra-lightweight screen capture using mss.
    
    Memory optimization:
    - Reuses mss instance (no recreation per frame)
    - Uses turbojpeg when available (10x faster, less memory)
    - Direct byte streaming (no intermediate Image objects when possible)
    """
    
    def __init__(
        self,
        monitor: int = 0,
        quality: int = 50,
        scale: float = 0.5,
        use_turbojpeg: bool = True
    ):
        """
        Initialize screen capture.
        
        Args:
            monitor: Monitor index (0 = all monitors combined, 1+ = specific monitor)
            quality: JPEG quality (1-95)
            scale: Scale factor (0.1-1.0)
            use_turbojpeg: Try to use turbojpeg if available
        """
        self.monitor_index = monitor
        self.quality = max(1, min(95, quality))
        self.scale = max(0.1, min(1.0, scale))
        self.use_turbojpeg = use_turbojpeg and TURBOJPEG_AVAILABLE
        
        # Create mss instance (reused for all captures)
        self._sct = mss.mss()
        
        # Cache monitor info
        self._update_monitor_info()
    
    def _update_monitor_info(self) -> None:
        """Update cached monitor information."""
        monitors = self._sct.monitors
        
        # Monitor 0 is the combined virtual screen, 1+ are individual monitors
        if self.monitor_index < len(monitors):
            mon = monitors[self.monitor_index]
        else:
            # Fallback to primary (index 1) or combined (index 0)
            mon = monitors[1] if len(monitors) > 1 else monitors[0]
        
        self._monitor = mon
        self._width = mon["width"]
        self._height = mon["height"]
        
        # Calculate scaled dimensions
        self._scaled_width = max(1, int(self._width * self.scale))
        self._scaled_height = max(1, int(self._height * self.scale))
    
    @property
    def width(self) -> int:
        """Original screen width."""
        return self._width
    
    @property
    def height(self) -> int:
        """Original screen height."""
        return self._height
    
    @property
    def scaled_width(self) -> int:
        """Scaled screen width."""
        return self._scaled_width
    
    @property
    def scaled_height(self) -> int:
        """Scaled screen height."""
        return self._scaled_height
    
    def capture_jpeg(self) -> bytes:
        """
        Capture screen and return JPEG bytes.
        
        This is the main method - optimized for minimal memory usage.
        
        Returns:
            JPEG image as bytes
        """
        # Grab screen (returns raw BGRA bytes)
        sct_img = self._sct.grab(self._monitor)
        
        if self.use_turbojpeg and _jpeg is not None:
            return self._encode_turbojpeg(sct_img)
        else:
            return self._encode_pillow(sct_img)
    
    def _encode_turbojpeg(self, sct_img) -> bytes:
        """Encode using turbojpeg (fast, low memory)."""
        # Get raw bytes
        raw = bytes(sct_img.raw)
        
        # If scaling, we need to use Pillow for resize then turbojpeg for encode
        if self.scale < 1.0:
            # Create PIL Image from raw bytes
            img = Image.frombytes("RGBA", (sct_img.width, sct_img.height), raw, "raw", "BGRA")
            img = img.resize((self._scaled_width, self._scaled_height), Image.Resampling.LANCZOS)
            
            # Convert to RGB for JPEG (drop alpha)
            img = img.convert("RGB")
            
            # Use turbojpeg to encode
            import numpy as np
            arr = np.array(img)
            return _jpeg.encode(arr, quality=self.quality)
        else:
            # No scaling - encode directly
            # Convert BGRA to BGR for turbojpeg
            import numpy as np
            arr = np.frombuffer(raw, dtype=np.uint8).reshape((sct_img.height, sct_img.width, 4))
            # Drop alpha channel, convert BGRA to BGR
            arr = arr[:, :, :3][:, :, ::-1]  # BGRA -> RGB
            return _jpeg.encode(arr, quality=self.quality)
    
    def _encode_pillow(self, sct_img) -> bytes:
        """Encode using Pillow (fallback, slower)."""
        # Create PIL Image from raw bytes
        img = Image.frombytes("RGBA", (sct_img.width, sct_img.height), bytes(sct_img.raw), "raw", "BGRA")
        
        # Scale if needed
        if self.scale < 1.0:
            img = img.resize((self._scaled_width, self._scaled_height), Image.Resampling.LANCZOS)
        
        # Convert to RGB (JPEG doesn't support alpha)
        img = img.convert("RGB")
        
        # Encode to JPEG
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=self.quality, optimize=False)
        return buffer.getvalue()
    
    def set_quality(self, quality: int) -> None:
        """Update JPEG quality."""
        self.quality = max(1, min(95, quality))
    
    def set_scale(self, scale: float) -> None:
        """Update scale factor."""
        self.scale = max(0.1, min(1.0, scale))
        self._update_monitor_info()
    
    def close(self) -> None:
        """Clean up resources."""
        if self._sct:
            self._sct.close()
            self._sct = None


# Singleton instance (created on first use)
_capture_instance: Optional[ScreenCapture] = None


def get_capture(
    monitor: int = 0,
    quality: int = 50,
    scale: float = 0.5,
    use_turbojpeg: bool = True
) -> ScreenCapture:
    """
    Get or create the screen capture instance.
    
    Uses a singleton pattern to avoid memory waste from multiple instances.
    """
    global _capture_instance
    
    if _capture_instance is None:
        _capture_instance = ScreenCapture(
            monitor=monitor,
            quality=quality,
            scale=scale,
            use_turbojpeg=use_turbojpeg
        )
    
    return _capture_instance


def close_capture() -> None:
    """Close and clean up the capture instance."""
    global _capture_instance
    
    if _capture_instance is not None:
        _capture_instance.close()
        _capture_instance = None
