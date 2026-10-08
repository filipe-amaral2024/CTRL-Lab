from __future__ import annotations

from typing import Dict, List

from .entry_camera import StreamCamera
from .lab_camera import LabCamera


class MultiStreamController:
    """Gerencia múltiplas câmeras em paralelo."""

    def __init__(self, entry_camera: StreamCamera, lab_camera: LabCamera):
        self.entry_camera = entry_camera
        self.lab_camera = lab_camera
        self._opened = False

    def open_all(self):
        self.entry_camera.open()
        self.lab_camera.open()
        self._opened = True
        return self

    def read_all(self):
        if not self._opened:
            raise RuntimeError("As câmeras ainda não foram abertas. Chame open_all() primeiro.")

        frames = {
            "entry": self.entry_camera.read_frame(),
            "lab": self.lab_camera.read_frame(),
        }
        return frames

    def close_all(self):
        self.entry_camera.close()
        self.lab_camera.close()
        self._opened = False

    def __enter__(self):
        self.open_all()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_all()
