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
ACCESS_ANNOTATION_MAX_AGE_SECONDS = 1.5


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
    """Executa os modelos configurados sobre frames da mesma câmera."""

    def __init__(
        self,
        camera: CameraSource,
        safety_detector: Optional[ObjectDetector] = None,
        access_detector: Optional[ObjectDetector] = None,
        inference_interval_seconds: float = 3.0,
        access_detector_factory: Optional[Callable[[], ObjectDetector]] = None,
        preview_enabled: bool = False,
        access_vote_window_seconds: float = 0.0,
    ):
        if safety_detector is None and access_detector is None and access_detector_factory is None:
            raise ValueError("Configure ao menos um modelo de visão.")
        if inference_interval_seconds <= 0:
            raise ValueError("O intervalo de inferência deve ser positivo.")
        if access_vote_window_seconds < 0:
            raise ValueError("A janela de votação deve ser zero ou maior.")
        if access_detector is not None and access_detector_factory is not None:
            raise ValueError("Configure o detector de acesso ou a fábrica, não ambos.")

        self.camera = camera
        self.safety_detector = safety_detector
        self._access_detector = access_detector
        self._access_detector_factory = access_detector_factory
        self.inference_interval_seconds = inference_interval_seconds
        self.preview_enabled = preview_enabled
        self.access_vote_window_seconds = access_vote_window_seconds
        self.ppe_evaluator = PPEEvaluator(
            required_equipment={"lab_coat": "Jaleco ausente"},
            require_tied_hair=False,
        )
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
        self._access_annotations_updated_at = None
        self._reset_access_voting()
        self._opened = False
        self._safety_ready = False
        self._access_enabled = (
            safety_detector is None
            and (access_detector is not None or access_detector_factory is not None)
        )
        self._state = SystemState.NORMAL
        self._details: Dict[str, dict] = {}
        self._error: Optional[str] = None

    @property
    def access_available(self) -> bool:
        with self._lock:
            return self._access_detector is not None or self._access_detector_factory is not None

    @property
    def running(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def start(self):
        if self.running:
            raise RuntimeError("O serviço de visão já está em execução.")

        if not self._opened:
            self.open()

        with self._lock:
            self._safety_ready = False
            self._state = SystemState.NORMAL
            self._error = None
            access_enabled = self._access_enabled
            access_available = (
                self._access_detector is not None
                or self._access_detector_factory is not None
            )
            self._details = {
                "safety": {
                    "risk": "AGUARDANDO" if self.safety_detector else "NAO_CONFIGURADO",
                    "detections": [],
                },
                "access": {
                    "status": "AGUARDANDO" if access_enabled else "DESABILITADO",
                    "enabled": access_enabled,
                    "available": access_available,
                },
            }
            self._reset_access_voting()
        with self._frame_lock:
            self._latest_frame = None
            self._latest_preview = None
        self._frame_ready.clear()
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
                details["access"] = {
                    "status": status,
                    "enabled": enabled,
                    "available": True,
                }
            self._details = details
            self._state = self._state_from_details(details)
            self._access_annotations_updated_at = None
            self._reset_access_voting()
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
            details["access"] = {
                "status": status,
                "enabled": enabled,
                "available": True,
            }
            self._details = details
            self._state = self._state_from_details(details)
            self._access_annotations_updated_at = None
            self._reset_access_voting()
        logger.info("Modelo de acesso %s.", "habilitado" if enabled else "desabilitado")
        return enabled

    def process_once(self):
        if not self._opened:
            raise RuntimeError("A câmera ainda não foi aberta. Chame start() primeiro.")

        frame = self._get_latest_frame()
        if frame is None:
            error = self.camera.last_error or "Não foi possível capturar um frame."
            logger.warning("Câmera indisponível: %s", error)
            with self._lock:
                details = dict(self._details)
                if self.safety_detector is not None:
                    details["safety"] = {
                        "risk": "ERRO",
                        "detections": [],
                        "error": error,
                    }
                if self._access_enabled:
                    details["access"] = {
                        "status": "ERRO",
                        "enabled": True,
                        "available": True,
                        "error": error,
                    }
                self._details = details
                self._error = error
                self._state = self._state_from_details(details)
                self._safety_ready = False
            return self.snapshot()

        if self.safety_detector is None:
            safety = {
                "risk": "NAO_CONFIGURADO",
                "detections": [],
            }
        else:
            safety_detections = self.safety_detector.predict(frame)
            safety = self._evaluate_safety(
                safety_detections,
                self._serialize_detections(safety_detections),
            )

        with self._lock:
            access_enabled = self._access_enabled

        if not self.access_available:
            access = {
                "status": "NAO_CONFIGURADO",
                "enabled": False,
                "available": False,
            }
        elif not access_enabled:
            access = {"status": "DESABILITADO", "enabled": False, "available": True}
        else:
            access = self._evaluate_access_model(frame)

        with self._lock:
            if self._access_detector is not None or self._access_detector_factory is not None:
                if self._access_enabled and not access_enabled:
                    access = {
                        "status": "AGUARDANDO",
                        "enabled": True,
                        "available": True,
                    }
                elif not self._access_enabled:
                    access = {
                        "status": "DESABILITADO",
                        "enabled": False,
                        "available": True,
                    }
            access = self._stabilize_access_result(access, time.monotonic())
            details = {"safety": safety, "access": access}
            state = self._state_from_details(details)
            self._safety_ready = (
                safety.get("risk") != "ERRO"
                and access.get("status") != "ERRO"
            )
            self._details = details
            self._state = state
            self._error = None
            self._access_annotations_updated_at = (
                time.monotonic()
                if access.get("enabled") is True and access.get("annotations")
                else None
            )
        if self.preview_enabled and access.get("enabled") is True:
            self._store_preview(frame, access.get("annotations", []))
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
            result["available"] = True
            return result
        except Exception as exc:
            logger.exception("Falha na inferência do modelo de acesso.")
            return {
                "status": "ERRO",
                "enabled": True,
                "available": True,
                "error": str(exc),
            }

    def _reset_access_voting(self):
        self._access_vote_window_started_at = None
        self._access_tracks = {}
        self._next_access_track_id = 1
        self._stable_access_result = {
            "status": "AGUARDANDO",
            "reasons": [],
            "person_count": 0,
            "compliant_count": 0,
            "annotations": [],
        }

    def _stabilize_access_result(self, access, now):
        if (
            self.access_vote_window_seconds == 0
            or access.get("enabled") is not True
        ):
            return access
        if access.get("status") == "ERRO":
            self._reset_access_voting()
            return access

        if access.get("status") not in {"ALERTA", "PERMITIDO", "SEM_PESSOA"}:
            return access

        if self._access_vote_window_started_at is None:
            self._access_vote_window_started_at = now
        elif now - self._access_vote_window_started_at >= self.access_vote_window_seconds:
            self._complete_access_vote_window(now)
            self._access_vote_window_started_at = now

        annotations = access.get("annotations", [])
        current_tracks = self._update_access_tracks(annotations, now)
        voted_annotations = []
        for track in current_tracks:
            annotation = dict(track["latest_annotation"])
            annotation["status"] = track["stable_status"] or "ANALISANDO"
            if track["stable_confidence"] is not None:
                annotation["confidence"] = track["stable_confidence"]
            voted_annotations.append(annotation)

        result = dict(self._stable_access_result)
        result.update(
            annotations=voted_annotations,
            detections=access.get("detections", []),
            enabled=True,
            available=True,
            vote_window_seconds=self.access_vote_window_seconds,
            observed_person_count=len(current_tracks),
        )
        return result

    def _complete_access_vote_window(self, now):
        expired_track_ids = [
            track_id
            for track_id, track in self._access_tracks.items()
            if now - track["last_seen"] > self.access_vote_window_seconds
        ]
        for track_id in expired_track_ids:
            del self._access_tracks[track_id]

        for track in self._access_tracks.values():
            votes = track["votes"]
            if not votes:
                continue
            counts = {}
            confidence_totals = {}
            latest_positions = {}
            for index, (status, confidence) in enumerate(votes):
                counts[status] = counts.get(status, 0) + 1
                confidence_totals[status] = (
                    confidence_totals.get(status, 0.0) + confidence
                )
                latest_positions[status] = index

            winner = max(
                counts,
                key=lambda status: (
                    counts[status],
                    confidence_totals[status] / counts[status],
                    latest_positions[status],
                ),
            )
            track["stable_status"] = winner
            track["stable_confidence"] = (
                confidence_totals[winner] / counts[winner]
            )
            track["votes"] = []

        stable_tracks = [
            track
            for track in self._access_tracks.values()
            if track["stable_status"] is not None
        ]
        compliant_count = sum(
            track["stable_status"] == "PERMITIDO" for track in stable_tracks
        )
        missing_count = len(stable_tracks) - compliant_count
        if not stable_tracks:
            self._stable_access_result = {
                "status": "SEM_PESSOA",
                "reasons": [],
                "person_count": 0,
                "compliant_count": 0,
                "annotations": [],
            }
        else:
            self._stable_access_result = {
                "status": "ALERTA" if missing_count else "PERMITIDO",
                "reasons": (
                    [f"Jaleco ausente em {missing_count} pessoa(s)"]
                    if missing_count
                    else []
                ),
                "person_count": len(stable_tracks),
                "compliant_count": compliant_count,
                "annotations": [],
            }

    def _update_access_tracks(self, annotations, now):
        available_tracks = {
            track_id: track
            for track_id, track in self._access_tracks.items()
            if now - track["last_seen"] <= self.access_vote_window_seconds
        }
        matches = []
        for annotation_index, annotation in enumerate(annotations):
            for track_id, track in available_tracks.items():
                overlap = self._box_iou(annotation, track["latest_annotation"])
                if overlap >= 0.1:
                    matches.append((overlap, annotation_index, track_id))

        matched_annotations = set()
        matched_tracks = set()
        assignments = {}
        for _, annotation_index, track_id in sorted(matches, reverse=True):
            if annotation_index in matched_annotations or track_id in matched_tracks:
                continue
            assignments[annotation_index] = track_id
            matched_annotations.add(annotation_index)
            matched_tracks.add(track_id)

        current_tracks = []
        for annotation_index, annotation in enumerate(annotations):
            track_id = assignments.get(annotation_index)
            if track_id is None:
                track_id = self._next_access_track_id
                self._next_access_track_id += 1
                self._access_tracks[track_id] = {
                    "votes": [],
                    "stable_status": None,
                    "stable_confidence": None,
                }
            track = self._access_tracks[track_id]
            track["last_seen"] = now
            track["latest_annotation"] = dict(annotation)
            track["votes"].append(
                (
                    annotation["status"],
                    float(annotation.get("confidence") or 0.0),
                )
            )
            current_tracks.append(track)
        return current_tracks

    @staticmethod
    def _box_iou(first, second):
        first_box = tuple(first.get(key) for key in ("x1", "y1", "x2", "y2"))
        second_box = tuple(second.get(key) for key in ("x1", "y1", "x2", "y2"))
        if any(value is None for value in first_box + second_box):
            return 1.0 if first_box == second_box else 0.0

        left = max(first_box[0], second_box[0])
        top = max(first_box[1], second_box[1])
        right = min(first_box[2], second_box[2])
        bottom = min(first_box[3], second_box[3])
        intersection = max(0, right - left) * max(0, bottom - top)
        if intersection == 0:
            return 0.0
        first_area = max(0, first_box[2] - first_box[0]) * max(
            0, first_box[3] - first_box[1]
        )
        second_area = max(0, second_box[2] - second_box[0]) * max(
            0, second_box[3] - second_box[1]
        )
        union = first_area + second_area - intersection
        return intersection / union if union else 0.0

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
            "safety_ready": self._safety_ready,
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
                logger.error("A thread de visão não encerrou; a câmera continua em uso.")
                return False
            self._worker = None
        if self._capture_worker is not None:
            self._capture_worker.join(timeout=5.0)
            if self._capture_worker.is_alive():
                logger.error("A thread de captura não encerrou; a câmera continua em uso.")
                return False
            self._capture_worker = None

        if self._opened:
            self.camera.close()
            self._opened = False
        with self._lock:
            self._safety_ready = False
            self._state = SystemState.NORMAL
            self._error = None
            if self._access_detector_factory is not None:
                self._access_detector = None
            access_configured = (
                self._access_detector is not None
                or self._access_detector_factory is not None
            )
            if not access_configured:
                access_status = "NAO_CONFIGURADO"
            elif self._access_enabled:
                access_status = "PAUSADO"
            else:
                access_status = "DESABILITADO"
            self._details = {
                "safety": {
                    "risk": "PAUSADO" if self.safety_detector else "NAO_CONFIGURADO",
                    "detections": [],
                },
                "access": {
                    "status": access_status,
                    "enabled": self._access_enabled,
                    "available": access_configured,
                },
            }
        with self._frame_lock:
            self._latest_frame = None
            self._latest_preview = None
        self._frame_ready.clear()
        with self._lock:
            self._access_annotations_updated_at = None
            self._reset_access_voting()
        return True

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
                details = dict(self._details)
                if self.safety_detector is not None:
                    details["safety"] = {
                        "risk": "ERRO",
                        "detections": [],
                        "error": str(exc),
                    }
                self._details = details
                self._state = self._state_from_details(details)
                self._safety_ready = False
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

    def _store_preview(self, frame, annotations=None):
        if cv2 is None:
            if not self._preview_warning_logged:
                logger.warning("OpenCV indisponível; pré-visualização da câmera desativada.")
                self._preview_warning_logged = True
            return

        if annotations is None:
            with self._lock:
                access = self._details.get("access", {})
                updated_at = self._access_annotations_updated_at
                annotations = (
                    access.get("annotations", [])
                    if access.get("enabled") is True
                    and updated_at is not None
                    and time.monotonic() - updated_at
                    <= ACCESS_ANNOTATION_MAX_AGE_SECONDS
                    else []
                )
        preview_frame = frame
        if annotations:
            copy_frame = getattr(frame, "copy", None)
            if callable(copy_frame):
                preview_frame = copy_frame()
            for annotation in annotations:
                self._draw_access_annotation(preview_frame, annotation)

        encoded, buffer = cv2.imencode(".jpg", preview_frame)
        if not encoded:
            logger.warning("OpenCV não conseguiu codificar o frame da câmera.")
            return

        image_bytes = buffer.tobytes()
        with self._frame_lock:
            self._preview_sequence += 1
            self._latest_preview = (self._preview_sequence, image_bytes)

    @staticmethod
    def _draw_access_annotation(frame, annotation):
        x1, y1, x2, y2 = (
            annotation.get("x1"),
            annotation.get("y1"),
            annotation.get("x2"),
            annotation.get("y2"),
        )
        if any(value is None for value in (x1, y1, x2, y2)):
            return

        status = annotation.get("status")
        if status == "PERMITIDO":
            color = (0, 200, 0)
            label = "COM JALECO"
        elif status == "ALERTA":
            color = (0, 0, 255)
            label = "SEM JALECO"
        else:
            color = (0, 200, 255)
            label = "ANALISANDO"
        confidence = annotation.get("confidence")
        if confidence is not None:
            label = f"{label} {confidence:.0%}"

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            frame,
            label,
            (x1, max(y1 - 8, 16)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
            cv2.LINE_AA,
        )

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
        people_with_coat = [
            detection
            for detection in detections
            if detection.class_name.strip().lower() == "person_with_labcoat"
        ]
        people_without_coat = [
            detection
            for detection in detections
            if detection.class_name.strip().lower() == "person_without_labcoat"
        ]
        if people_with_coat or people_without_coat:
            person_count = len(people_with_coat) + len(people_without_coat)
            missing_count = len(people_without_coat)
            return {
                "status": "ALERTA" if missing_count else "PERMITIDO",
                "reasons": (
                    [f"Jaleco ausente em {missing_count} pessoa(s)"]
                    if missing_count
                    else []
                ),
                "person_count": person_count,
                "compliant_count": len(people_with_coat),
                "detections": serialized,
                "annotations": [
                    self._serialize_access_annotation(detection, "PERMITIDO")
                    for detection in people_with_coat
                ]
                + [
                    self._serialize_access_annotation(detection, "ALERTA")
                    for detection in people_without_coat
                ],
            }

        people = [
            detection
            for detection in detections
            if detection.class_name.strip().lower() == "person"
        ]
        if not people:
            return {
                "status": "SEM_PESSOA",
                "reasons": [],
                "person_count": 0,
                "compliant_count": 0,
                "detections": serialized,
                "annotations": [],
            }

        coats = [
            detection
            for detection in detections
            if detection.class_name.strip().lower() == "lab_coat"
        ]
        person_results = [
            self.ppe_evaluator.evaluate(
                {
                    "lab_coat": any(
                        self._belongs_to_person(coat, person, len(people))
                        for coat in coats
                    )
                }
            )
            for person in people
        ]
        compliant_count = sum(
            result["status"] == "PERMITIDO" for result in person_results
        )
        missing_count = len(people) - compliant_count
        reasons = (
            [f"Jaleco ausente em {missing_count} pessoa(s)"]
            if missing_count
            else []
        )
        return {
            "status": "ALERTA" if missing_count else "PERMITIDO",
            "reasons": reasons,
            "person_count": len(people),
            "compliant_count": compliant_count,
            "detections": serialized,
            "annotations": [
                self._serialize_access_annotation(
                    person,
                    "PERMITIDO"
                    if result["status"] == "PERMITIDO"
                    else "ALERTA",
                )
                for person, result in zip(people, person_results)
            ],
        }

    @staticmethod
    def _serialize_access_annotation(person, status):
        return {
            "x1": person.x1,
            "y1": person.y1,
            "x2": person.x2,
            "y2": person.y2,
            "status": status,
            "confidence": person.confidence,
        }

    @staticmethod
    def _belongs_to_person(item, person, person_count):
        item_bounds = (item.x1, item.y1, item.x2, item.y2)
        person_bounds = (person.x1, person.y1, person.x2, person.y2)
        if any(value is None for value in item_bounds + person_bounds):
            return person_count == 1
        center_x = (item.x1 + item.x2) / 2
        center_y = (item.y1 + item.y2) / 2
        return (
            person.x1 <= center_x <= person.x2
            and person.y1 <= center_y <= person.y2
        )

    @staticmethod
    def _state_from_details(details):
        safety_risk = details.get("safety", {}).get("risk")
        if safety_risk == "EMERGENCY":
            return SystemState.EMERGENCY
        if safety_risk == "ERRO" or details.get("access", {}).get("status") in {
            "ALERTA",
            "ERRO",
        }:
            return SystemState.ALERT
        return SystemState.NORMAL
