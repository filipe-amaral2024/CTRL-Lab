from __future__ import annotations

import logging
import threading
import time
from typing import Dict, List, Optional, Protocol

from app.cameras.entry_camera import CameraConfig, StreamCamera
from app.cameras.lab_camera import LabCamera, LabCameraConfig
from app.safety.ppe_evaluator import PPEEvaluator
from app.vision.fire_detector import FireDetector
from app.vision.yolo_base import DetectionResult
from raspberry_pi.alerts import SystemState

logger = logging.getLogger(__name__)


class ObjectDetector(Protocol):
    def predict(self, image) -> List[DetectionResult]:
        ...


class RaspberryVisionService:
    """Executa inferência nas câmeras IP no Raspberry, fora do loop de sensores."""

    def __init__(
        self,
        entry_camera: Optional[StreamCamera],
        lab_camera: Optional[LabCamera],
        detector: ObjectDetector,
        inference_interval_seconds: float = 3.0,
    ):
        if inference_interval_seconds <= 0:
            raise ValueError("O intervalo de inferência deve ser positivo.")

        self.cameras = {
            name: camera
            for name, camera in (("entry", entry_camera), ("lab", lab_camera))
            if camera is not None
        }
        if not self.cameras:
            raise ValueError("Configure ao menos uma câmera para a análise visual.")

        self.detector = detector
        self.inference_interval_seconds = inference_interval_seconds
        self.ppe_evaluator = PPEEvaluator()
        self.fire_detector = FireDetector()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker = None
        self._opened = False
        self._state = SystemState.NORMAL
        self._details: Dict[str, dict] = {}
        self._error: Optional[str] = None

    def start(self):
        if self._worker is not None and self._worker.is_alive():
            raise RuntimeError("O serviço de visão já está em execução.")

        if not self._opened:
            self.open()

        self._stop_event.clear()
        self._worker = threading.Thread(
            target=self._run,
            name="ctrlab-vision",
            daemon=True,
        )
        self._worker.start()

    def open(self):
        if self._opened:
            raise RuntimeError("As câmeras do serviço de visão já estão abertas.")

        opened_cameras = []
        try:
            for camera in self.cameras.values():
                camera.open()
                opened_cameras.append(camera)
        except Exception:
            for camera in opened_cameras:
                camera.close()
            raise

        self._opened = True

    def process_once(self):
        if not self._opened:
            raise RuntimeError("As câmeras ainda não foram abertas. Chame start() primeiro.")

        details = self.snapshot()["details"]
        for camera_name, camera in self.cameras.items():
            frame = camera.read_frame()
            if frame is None:
                error = camera.last_error or "Não foi possível capturar um frame."
                logger.warning("Câmera %s indisponível: %s", camera_name, error)
                previous = details.get(camera_name, {})
                details[camera_name] = dict(previous, camera_error=error)
                continue

            detections = self.detector.predict(frame)
            serialized = [
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
            if camera_name == "entry":
                details[camera_name] = self._evaluate_entry(detections, serialized)
            else:
                details[camera_name] = self._evaluate_lab(detections, serialized)

        state = self._state_from_details(details)
        with self._lock:
            self._details = details
            self._state = state
            self._error = None
        return self.snapshot()

    def snapshot(self):
        with self._lock:
            details = {name: dict(result) for name, result in self._details.items()}
            state = self._state
            error = self._error
        if error:
            details["service_error"] = error
        return {"state": state, "details": details}

    def stop(self):
        self._stop_event.set()
        if self._worker is not None:
            self._worker.join(timeout=5.0)
            if self._worker.is_alive():
                logger.warning("A thread de visão ainda aguarda uma leitura de câmera.")
                return
            self._worker = None

        if self._opened:
            for camera in self.cameras.values():
                camera.close()
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
            for camera in self.cameras.values():
                camera.close()
            self._opened = False

    def _evaluate_entry(self, detections, serialized):
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

    def _evaluate_lab(self, detections, serialized):
        scores = {"smoke": 0.0, "fire": 0.0}
        for detection in detections:
            label = detection.class_name.strip().lower()
            if label in scores:
                scores[label] = max(scores[label], detection.confidence)
        result = self.fire_detector.classify(scores)
        return dict(result, detections=serialized)

    @staticmethod
    def _state_from_details(details):
        if details.get("lab", {}).get("risk") == "EMERGENCY":
            return SystemState.EMERGENCY
        if details.get("entry", {}).get("status") == "ALERTA":
            return SystemState.ALERT
        return SystemState.NORMAL
