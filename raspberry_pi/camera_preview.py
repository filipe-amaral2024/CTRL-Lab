from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

from app.cameras.entry_camera import cv2

logger = logging.getLogger(__name__)
Preview = Tuple[int, bytes]
PREVIEW_FPS = 24


class RaspberryCameraPreview:
    """Captures and publishes previews without running inference."""

    def __init__(
        self,
        camera,
        preview_interval_seconds: float = 1.0 / PREVIEW_FPS,
    ):
        if cv2 is None:
            raise RuntimeError("OpenCV is required for camera preview.")
        if preview_interval_seconds <= 0:
            raise ValueError("The preview interval must be positive.")

        self.camera = camera
        self.preview_interval_seconds = preview_interval_seconds
        self._preview: Optional[Preview] = None
        self._sequence = 0
        self._next_capture_at = 0.0
        self._opened = False

    @property
    def running(self) -> bool:
        return self._opened

    def latest_preview(self) -> Optional[Preview]:
        return self._preview

    def start(self):
        if self.running:
            raise RuntimeError("Camera preview is already running.")

        opened = self.camera.open()
        if opened is False:
            raise RuntimeError(
                self.camera.last_error or "Could not open the camera for preview."
            )
        self._opened = True
        self._preview = None
        self._next_capture_at = 0.0

    def stop(self) -> bool:
        if self._opened:
            self.camera.close()
            self._opened = False
        self._preview = None
        return True

    def capture_if_due(self) -> bool:
        """Capture one frame synchronously when its scheduled slot is due."""
        if not self._opened:
            raise RuntimeError("Camera preview is not running.")
        now = time.monotonic()
        if now < self._next_capture_at:
            return False

        try:
            frame = self.camera.read_frame()
            if frame is None:
                logger.warning(
                    "Camera preview frame unavailable: %s",
                    self.camera.last_error or "no frame returned",
                )
                return False

            encoded, buffer = cv2.imencode(".jpg", frame)
            if not encoded:
                logger.warning("OpenCV could not encode a camera preview frame.")
                return False

            self._sequence += 1
            self._preview = (self._sequence, buffer.tobytes())
            return True
        finally:
            self._next_capture_at = (
                time.monotonic() + self.preview_interval_seconds
            )
