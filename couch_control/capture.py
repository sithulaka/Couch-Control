"""
Screen capture module using mss for ultra-low memory usage.
Supports turbojpeg for fast encoding, falls back to Pillow.
Supports frame-skip to avoid sending unchanged frames.
"""

import hashlib
import io
from typing import Optional

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

from PIL import Image


class ScreenCapture:
    """
    Ultra-lightweight screen capture using mss.

    Memory optimization:
    - Reuses mss instance (no recreation per frame)
    - Uses turbojpeg when available (10x faster, less memory)
    - Direct byte streaming (no intermediate Image objects when possible)
    - Frame-skip: returns None when screen is unchanged
    """

    def __init__(
        self,
        monitor: int = 0,
        quality: int = 50,
        scale: float = 0.5,
        use_turbojpeg: bool = True,
        frame_skip: bool = True,
    ):
        self.monitor_index = monitor
        self.quality = max(1, min(95, quality))
        self.scale = max(0.1, min(1.0, scale))
        self.use_turbojpeg = use_turbojpeg and TURBOJPEG_AVAILABLE
        self.frame_skip = frame_skip

        # Create mss instance (reused for all captures)
        self._sct = mss.mss()

        # Frame skip state
        self._last_frame_hash: Optional[bytes] = None

        # Cache monitor info
        self._update_monitor_info()

    def _update_monitor_info(self) -> None:
        """Update cached monitor information."""
        monitors = self._sct.monitors

        if self.monitor_index < len(monitors):
            mon = monitors[self.monitor_index]
        else:
            mon = monitors[1] if len(monitors) > 1 else monitors[0]

        self._monitor = mon
        self._width = mon["width"]
        self._height = mon["height"]

        self._scaled_width = max(1, int(self._width * self.scale))
        self._scaled_height = max(1, int(self._height * self.scale))

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def scaled_width(self) -> int:
        return self._scaled_width

    @property
    def scaled_height(self) -> int:
        return self._scaled_height

    def _compute_frame_hash(self, raw: memoryview) -> bytes:
        """Compute a fast hash over a sample of raw frame bytes."""
        # Sample every 500th byte — fast and catches most visual changes
        sample = bytes(raw[::500])
        return hashlib.md5(sample).digest()

    def capture_jpeg(self) -> Optional[bytes]:
        """
        Capture screen and return JPEG bytes.

        Returns:
            JPEG image as bytes, or None if the frame is unchanged (frame_skip=True).
        """
        sct_img = self._sct.grab(self._monitor)

        if self.frame_skip:
            frame_hash = self._compute_frame_hash(sct_img.raw)
            if frame_hash == self._last_frame_hash:
                return None
            self._last_frame_hash = frame_hash

        if self.use_turbojpeg and _jpeg is not None:
            return self._encode_turbojpeg(sct_img)
        else:
            return self._encode_pillow(sct_img)

    def _encode_turbojpeg(self, sct_img) -> bytes:
        """Encode using turbojpeg (fast, low memory)."""
        import numpy as np

        if self.scale < 1.0:
            raw = bytes(sct_img.raw)
            img = Image.frombytes("RGBA", (sct_img.width, sct_img.height), raw, "raw", "BGRA")
            img = img.resize((self._scaled_width, self._scaled_height), Image.Resampling.LANCZOS)
            img = img.convert("RGB")
            arr = np.array(img)
            return _jpeg.encode(arr, quality=self.quality)
        else:
            raw = bytes(sct_img.raw)
            arr = np.frombuffer(raw, dtype=np.uint8).reshape((sct_img.height, sct_img.width, 4))
            arr = arr[:, :, :3][:, :, ::-1]  # BGRA -> RGB
            return _jpeg.encode(arr, quality=self.quality)

    def _encode_pillow(self, sct_img) -> bytes:
        """Encode using Pillow (fallback, slower)."""
        img = Image.frombytes("RGBA", (sct_img.width, sct_img.height), bytes(sct_img.raw), "raw", "BGRA")

        if self.scale < 1.0:
            img = img.resize((self._scaled_width, self._scaled_height), Image.Resampling.LANCZOS)

        img = img.convert("RGB")

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
        self._last_frame_hash = None  # Force next frame to send after scale change

    def force_next_frame(self) -> None:
        """Force the next capture to be sent regardless of frame skip."""
        self._last_frame_hash = None

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
    use_turbojpeg: bool = True,
    frame_skip: bool = True,
) -> ScreenCapture:
    """Get or create the screen capture instance."""
    global _capture_instance

    if _capture_instance is None:
        _capture_instance = ScreenCapture(
            monitor=monitor,
            quality=quality,
            scale=scale,
            use_turbojpeg=use_turbojpeg,
            frame_skip=frame_skip,
        )

    return _capture_instance


def close_capture() -> None:
    """Close and clean up the capture instance."""
    global _capture_instance

    if _capture_instance is not None:
        _capture_instance.close()
        _capture_instance = None
