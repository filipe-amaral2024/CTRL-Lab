from __future__ import annotations

import logging
import threading
import time
from typing import Optional, Tuple

from app.cameras.entry_camera import cv2

logger = logging.getLogger(__name__)
Preview = Tuple[int, bytes]


class RaspberryCameraPreview:
    """Captures and publishes camera previews without running an inference model."""

    def __init__(self, camera, preview_interval_seconds: float = 0.2):
        if cv2 is None:
            raise RuntimeError("OpenCV is required for camera preview.")
        if preview_interval_seconds <= 0:
            raise ValueError("The preview interval must be positive.")

        self.camera = camera
        self.preview_interval_seconds = preview_interval_seconds
        self._stop_event = threading.Event()
        self._frame_lock = threading.Lock()
        self._preview: Optional[Preview] = None
        self._sequence = 0
        self._worker: Optional[threading.Thread] = None
        self._opened = False

    @property
    def running(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def latest_preview(self) -> Optional[Preview]:
        with self._frame_lock:
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
        self._stop_event.clear()
        with self._frame_lock:
            self._preview = None
        self._worker = threading.Thread(
            target=self._capture,
            name="ctrlab-camera-preview",
            daemon=True,
        )
        self._worker.start()

    def stop(self) -> bool:
        self._stop_event.set()
        if self._worker is not None:
            self._worker.join(timeout=5.0)
            if self._worker.is_alive():
                logger.error("Camera preview thread did not stop; camera remains open.")
                return False
            self._worker = None

        if self._opened:
            self.camera.close()
            self._opened = False
        with self._frame_lock:
            self._preview = None
        return True

    def _capture(self):
        next_preview_at = 0.0
        while not self._stop_event.is_set():
            frame = self.camera.read_frame()
            if frame is None:
                self._stop_event.wait(0.1)
                continue

            now = time.monotonic()
            if now < next_preview_at:
                self._stop_event.wait(0.01)
                continue

            encoded, buffer = cv2.imencode(".jpg", frame)
            if not encoded:
                logger.warning("OpenCV could not encode a camera preview frame.")
                self._stop_event.wait(0.1)
                continue

            with self._frame_lock:
                self._sequence += 1
                self._preview = (self._sequence, buffer.tobytes())
            next_preview_at = now + self.preview_interval_seconds
