from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, List, Optional, Protocol

from app.cameras.entry_camera import cv2
from app.safety.ppe_evaluator import PPEEvaluator
from app.vision.fire_detector import FireDetector
from app.vision.yolo_base import DetectionResult
from raspberry_pi.alerts import SystemState

logger = logging.getLogger(__name__)


class ObjectDetector(Protocol):
    def predict(self, image: object) -> List[DetectionResult]:
        ...


class CameraSource(Protocol):
    last_error: Optional[str]

    def open(self) -> bool | None:
        ...

    def read_frame(self) -> object | None:
        ...

    def close(self) -> None:
        ...


class RaspberryVisionService:
    """Executa os dois modelos sobre frames da mesma câmera."""

    def __init__(
        self,
        camera: CameraSource,
        safety_detector: ObjectDetector,
        access_detector: Optional[ObjectDetector] = None,
        inference_interval_seconds: float = 3.0,
        access_detector_factory: Optional[Callable[[], ObjectDetector]] = None,
        preview_enabled: bool = False,
    ):
        if inference_interval_seconds <= 0:
            raise ValueError("O intervalo de inferência deve ser positivo.")
        if access_detector is not None and access_detector_factory is not None:
            raise ValueError("Configure o detector de acesso ou a fábrica, não ambos.")

        self.camera = camera
        self.safety_detector = safety_detector
        self._access_detector = access_detector
        self._access_detector_factory = access_detector_factory
        self.inference_interval_seconds = inference_interval_seconds
        self.preview_enabled = preview_enabled
        self.ppe_evaluator = PPEEvaluator()
        self.fire_detector = FireDetector()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._capture_stop_event = threading.Event()
        self._frame_ready = threading.Event()
        self._frame_lock = threading.Lock()
        self._worker = None
        self._capture_worker = None
        self._latest_frame = None
        self._latest_preview = None
        self._preview_sequence = 0
        self._preview_warning_logged = False
        self._opened = False
        self._access_enabled = False
        self._state = SystemState.NORMAL
        self._details: Dict[str, dict] = {}
        self._error: Optional[str] = None

    @property
    def access_available(self) -> bool:
        with self._lock:
            return self._access_detector is not None or self._access_detector_factory is not None

    def start(self):
        if self._worker is not None and self._worker.is_alive():
            raise RuntimeError("O serviço de visão já está em execução.")

        if not self._opened:
            self.open()

        self._stop_event.clear()
        if self.preview_enabled:
            self._capture_stop_event.clear()
            self._capture_worker = threading.Thread(
                target=self._capture_frames,
                name="ctrlab-camera-capture",
                daemon=True,
            )
            self._capture_worker.start()
        self._worker = threading.Thread(
            target=self._run,
            name="ctrlab-vision",
            daemon=True,
        )
        self._worker.start()

    def open(self):
        if self._opened:
            raise RuntimeError("A câmera do serviço de visão já está aberta.")

        self.camera.open()
        self._opened = True

    def set_access_enabled(self, enabled: bool) -> bool:
        if not isinstance(enabled, bool):
            raise ValueError("O estado do modelo de acesso deve ser booleano.")
        if enabled and not self.access_available:
            raise ValueError("O modelo de acesso não foi configurado.")

        with self._lock:
            self._access_enabled = enabled
            if not enabled and self._access_detector_factory is not None:
                self._access_detector = None
            details = dict(self._details)
            if self._access_detector is not None or self._access_detector_factory is not None:
                status = "AGUARDANDO" if enabled else "DESABILITADO"
                details["access"] = {"status": status, "enabled": enabled}
            self._details = details
            self._state = self._state_from_details(details)
        logger.info("Modelo de acesso %s.", "habilitado" if enabled else "desabilitado")
        return enabled

    def toggle_access(self) -> bool:
        with self._lock:
            if self._access_detector is None and self._access_detector_factory is None:
                raise ValueError("O modelo de acesso não foi configurado.")
            self._access_enabled = not self._access_enabled
            enabled = self._access_enabled
            if not enabled and self._access_detector_factory is not None:
                self._access_detector = None
            details = dict(self._details)
            status = "AGUARDANDO" if enabled else "DESABILITADO"
            details["access"] = {"status": status, "enabled": enabled}
            self._details = details
            self._state = self._state_from_details(details)
        logger.info("Modelo de acesso %s.", "habilitado" if enabled else "desabilitado")
        return enabled

    def process_once(self):
        if not self._opened:
            raise RuntimeError("A câmera ainda não foi aberta. Chame start() primeiro.")

        frame = self._get_latest_frame()
        if frame is None:
            error = self.camera.last_error or "Não foi possível capturar um frame."
            logger.warning("Câmera indisponível: %s", error)
            details = self.snapshot()["details"]
            details["camera_error"] = error
            with self._lock:
                self._details = details
                self._error = error
            return self.snapshot()

        safety_detections = self.safety_detector.predict(frame)
        safety = self._evaluate_safety(
            safety_detections,
            self._serialize_detections(safety_detections),
        )

        with self._lock:
            access_enabled = self._access_enabled

        if not self.access_available:
            access = {"status": "NAO_CONFIGURADO", "enabled": False}
        elif not access_enabled:
            access = {"status": "DESABILITADO", "enabled": False}
        else:
            access = self._evaluate_access_model(frame)

        with self._lock:
            if self._access_detector is not None or self._access_detector_factory is not None:
                if self._access_enabled and not access_enabled:
                    access = {"status": "AGUARDANDO", "enabled": True}
                elif not self._access_enabled:
                    access = {"status": "DESABILITADO", "enabled": False}
            details = {"safety": safety, "access": access}
            state = self._state_from_details(details)
            self._details = details
            self._state = state
            self._error = None
        return self.snapshot()

    def _evaluate_access_model(self, frame):
        try:
            with self._lock:
                detector = self._access_detector
                factory = self._access_detector_factory

            if detector is None and factory is not None:
                detector = factory()
                with self._lock:
                    if self._access_enabled:
                        self._access_detector = detector
                    else:
                        detector = None

            if detector is None:
                return {"status": "DESABILITADO", "enabled": False}

            detections = detector.predict(frame)
            result = self._evaluate_access(
                detections,
                self._serialize_detections(detections),
            )
            result["enabled"] = True
            return result
        except Exception as exc:
            logger.exception("Falha no modelo de acesso; mantendo a checagem de segurança ativa.")
            return {
                "status": "ERRO",
                "enabled": True,
                "error": str(exc),
            }

    def snapshot(self):
        with self._lock:
            details = {name: dict(result) for name, result in self._details.items()}
            state = self._state
            error = self._error
            access_enabled = self._access_enabled
        if error:
            details["service_error"] = error
        return {
            "state": state,
            "details": details,
            "access_enabled": access_enabled,
        }

    def latest_preview(self):
        with self._frame_lock:
            return self._latest_preview

    def stop(self):
        self._stop_event.set()
        self._capture_stop_event.set()
        if self._worker is not None:
            self._worker.join(timeout=5.0)
            if self._worker.is_alive():
                logger.warning("A thread de visão ainda aguarda uma leitura de câmera.")
                return
            self._worker = None
        if self._capture_worker is not None:
            self._capture_worker.join(timeout=5.0)
            if self._capture_worker.is_alive():
                logger.warning("A thread de captura ainda aguarda uma leitura da câmera.")
                return
            self._capture_worker = None

        if self._opened:
            self.camera.close()
            self._opened = False

    def _run(self):
        try:
            while not self._stop_event.is_set():
                started_at = time.monotonic()
                self.process_once()
                remaining = self.inference_interval_seconds - (time.monotonic() - started_at)
                self._stop_event.wait(max(0.0, remaining))
        except Exception as exc:
            with self._lock:
                self._error = str(exc)
            logger.exception("Falha na inferência visual no Raspberry Pi.")
        finally:
            self._capture_stop_event.set()
            if self._capture_worker is not None:
                self._capture_worker.join(timeout=5.0)
                self._capture_worker = None
            self.camera.close()
            self._opened = False

    def _get_latest_frame(self):
        if self._capture_worker is not None and self._capture_worker.is_alive():
            if not self._frame_ready.wait(timeout=2.0):
                return None
            with self._frame_lock:
                return self._latest_frame

        frame = self.camera.read_frame()
        if frame is not None and self.preview_enabled:
            self._store_preview(frame)
        return frame

    def _capture_frames(self):
        next_preview_at = 0.0
        while not self._capture_stop_event.is_set():
            frame = self.camera.read_frame()
            if frame is None:
                self._capture_stop_event.wait(0.1)
                continue

            frame_copy = frame.copy() if callable(getattr(frame, "copy", None)) else frame
            with self._frame_lock:
                self._latest_frame = frame_copy
            self._frame_ready.set()

            now = time.monotonic()
            if now >= next_preview_at:
                self._store_preview(frame_copy)
                next_preview_at = now + 0.2
            self._capture_stop_event.wait(0.01)

    def _store_preview(self, frame):
        if cv2 is None:
            if not self._preview_warning_logged:
                logger.warning("OpenCV indisponível; pré-visualização da câmera desativada.")
                self._preview_warning_logged = True
            return

        encoded, buffer = cv2.imencode(".jpg", frame)
        if not encoded:
            logger.warning("OpenCV não conseguiu codificar o frame da câmera.")
            return

        image_bytes = buffer.tobytes()
        with self._frame_lock:
            self._preview_sequence += 1
            self._latest_preview = (self._preview_sequence, image_bytes)

    @staticmethod
    def _serialize_detections(detections: List[DetectionResult]) -> List[dict]:
        return [
            {
                "class_name": detection.class_name,
                "confidence": detection.confidence,
                "x1": detection.x1,
                "y1": detection.y1,
                "x2": detection.x2,
                "y2": detection.y2,
            }
            for detection in detections
        ]

    def _evaluate_safety(self, detections, serialized):
        scores = {"smoke": 0.0, "fire": 0.0}
        for detection in detections:
            label = detection.class_name.strip().lower()
            if label in scores:
                scores[label] = max(scores[label], detection.confidence)
        return dict(self.fire_detector.classify(scores), detections=serialized)

    def _evaluate_access(self, detections, serialized):
        labels = {detection.class_name.strip().lower() for detection in detections}
        if "person" not in labels:
            return {
                "status": "SEM_PESSOA",
                "reasons": [],
                "detections": serialized,
            }

        evaluation = self.ppe_evaluator.evaluate(
            {
                "person": True,
                "lab_coat": "lab_coat" in labels,
                "safety_glasses": "safety_glasses" in labels,
                "closed_shoes": "closed_shoes" in labels,
                "tied_hair": "tied_hair" in labels,
            }
        )
        return dict(evaluation, detections=serialized)

    @staticmethod
    def _state_from_details(details):
        if details.get("safety", {}).get("risk") == "EMERGENCY":
            return SystemState.EMERGENCY
        if details.get("access", {}).get("status") == "ALERTA":
            return SystemState.ALERT
        return SystemState.NORMAL
