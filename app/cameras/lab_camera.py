from dataclasses import dataclass

from .entry_camera import CameraConfig, StreamCamera


@dataclass
class LabCameraConfig(CameraConfig):
    """Configuração da câmera do laboratório."""

    role: str = "laboratory"


class LabCamera(StreamCamera):
    """Abstração para a câmera interna do laboratório."""

    def __init__(self, config: LabCameraConfig, fallback_device: int = 1):
        super().__init__(config, fallback_device=fallback_device)
        self.role = config.role
