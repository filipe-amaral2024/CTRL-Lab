from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import cv2
except ImportError:  # pragma: no cover - depende do ambiente
    cv2 = None


@dataclass
class CameraConfig:
    """Configuração da câmera de entrada do laboratório."""

    name: str
    url: str = ""
    width: int = 1280
    height: int = 720
    fps: int = 30
    use_local_camera: bool = False

    @property
    def source_url(self) -> str:
        return self.url

    @property
    def is_ip_stream(self) -> bool:
        return bool(self.url) and any(self.url.lower().startswith(prefix) for prefix in ("http://", "https://", "rtsp://", "rtmp://"))


class StreamCamera:
    """Abstração para receber vídeo de uma câmera IP ou câmera local."""

    def __init__(self, config: CameraConfig, fallback_device: int = 0):
        self.name = config.name
        self.config = config
        self.fallback_device = fallback_device
        self.capture = None
        self.last_error: Optional[str] = None

    def open(self):
        if cv2 is None:
            raise RuntimeError("OpenCV não está instalado. Instale 'opencv-python-headless' ou 'opencv-python'.")

        source = self.config.source_url if self.config.source_url else self.fallback_device
        self.capture = cv2.VideoCapture(source)

        if not self.capture.isOpened():
            self.last_error = f"Não foi possível abrir a fonte de vídeo: {source}"
            self.capture = None
            raise RuntimeError(self.last_error)

        buffer_property = getattr(cv2, "CAP_PROP_BUFFERSIZE", None)
        if buffer_property is not None and not self.capture.set(buffer_property, 1):
            self.last_error = (
                "O backend da câmera não aceitou buffer de um frame; "
                "a pré-visualização pode apresentar atraso."
            )
            logger.warning("%s", self.last_error)

        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        self.capture.set(cv2.CAP_PROP_FPS, self.config.fps)
        return True

    def read_frame(self):
        if self.capture is None:
            self.last_error = "Câmera não inicializada. Chame open() antes de ler o frame."
            return None

        ok, frame = self.capture.read()
        if not ok or frame is None:
            self.last_error = "Não foi possível capturar um frame da câmera."
            return None

        return frame

    def close(self):
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
