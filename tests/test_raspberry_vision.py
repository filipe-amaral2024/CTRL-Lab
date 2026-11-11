import threading
import time
import unittest
from types import SimpleNamespace
from typing import List, Optional
from unittest.mock import patch

from app.vision.yolo_base import DetectionResult
from raspberry_pi.alerts import SystemState
from raspberry_pi.main import _handle_access_command, _supports_access_classes
from raspberry_pi.vision import CameraSource, ObjectDetector, RaspberryVisionService


class DummyCamera(CameraSource):
    def __init__(self, frame: object):
        self.frame = frame
        self.last_error: Optional[str] = None
        self.opened = False
        self.read_count = 0

    def open(self) -> None:
        self.opened = True

    def read_frame(self) -> object:
        self.read_count += 1
        return self.frame

    def close(self) -> None:
        self.opened = False


class DummyFrame:
    def copy(self):
        return DummyFrame()


class SafetyDetector(ObjectDetector):
    def __init__(self, detections: Optional[List[DetectionResult]] = None):
        self.detections = detections or []
        self.frames: List[object] = []

    def predict(self, image: object) -> List[DetectionResult]:
        self.frames.append(image)
        return self.detections


class AccessDetector(ObjectDetector):
    def __init__(self, detections: Optional[List[DetectionResult]] = None):
        self.detections = detections or []
        self.frames: List[object] = []

    def predict(self, image: object) -> List[DetectionResult]:
        self.frames.append(image)
        return self.detections


class RaspberryVisionServiceTests(unittest.TestCase):
    def test_access_class_validation_supports_both_model_profiles(self):
        self.assertTrue(_supports_access_classes(["person", "lab_coat"]))
        self.assertTrue(
            _supports_access_classes(
                ["person_with_labcoat", "person_without_labcoat"]
            )
        )
        self.assertFalse(
            _supports_access_classes(
                ["person_with_labcoat", "labcoat"]
            )
        )

    def test_preview_captures_frames_without_waiting_for_inference_interval(self):
        fake_cv2 = SimpleNamespace(
            imencode=lambda extension, frame: (True, SimpleNamespace(tobytes=lambda: b"jpeg"))
        )
        camera = DummyCamera("ps3-eye-frame")
        service = RaspberryVisionService(
            camera=camera,
            safety_detector=SafetyDetector(),
            inference_interval_seconds=10,
            preview_enabled=True,
        )

        with patch("raspberry_pi.vision.cv2", fake_cv2):
            service.start()
            deadline = time.monotonic() + 2
            while (
                (
                    service.latest_preview() is None
                    or service.latest_preview()[0] < 2
                    or camera.read_count < 2
                )
                and time.monotonic() < deadline
            ):
                time.sleep(0.01)
            preview = service.latest_preview()
            service.stop()

        self.assertIsNotNone(preview)
        self.assertEqual(preview[1], b"jpeg")
        self.assertGreater(camera.read_count, 1)

    def test_stopped_vision_can_restart_for_safe_reset_verification(self):
        camera = DummyCamera("frame")
        service = RaspberryVisionService(
            camera=camera,
            safety_detector=SafetyDetector(),
            inference_interval_seconds=0.01,
            preview_enabled=True,
        )
        fake_cv2 = SimpleNamespace(
            imencode=lambda extension, frame: (
                True,
                SimpleNamespace(tobytes=lambda: b"jpeg"),
            )
        )

        with patch("raspberry_pi.vision.cv2", fake_cv2):
            service.start()
            deadline = time.monotonic() + 2
            while not service.snapshot()["safety_ready"] and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(service.snapshot()["safety_ready"])

            self.assertTrue(service.stop())
            paused = service.snapshot()
            self.assertFalse(paused["safety_ready"])
            self.assertEqual(paused["details"]["safety"]["risk"], "PAUSADO")
            self.assertIsNone(service.latest_preview())

            service.start()
            deadline = time.monotonic() + 2
            while not service.snapshot()["safety_ready"] and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(service.snapshot()["safety_ready"])
            self.assertTrue(service.stop())

    def test_safety_runs_and_access_is_opt_in_on_same_frame(self):
        camera = DummyCamera("ps3-eye-frame")
        safety_detector = SafetyDetector(
            [DetectionResult("smoke", 0.82), DetectionResult("fire", 0.10)]
        )
        access_detector = AccessDetector(
            [
                DetectionResult("person", 0.95),
                DetectionResult("lab_coat", 0.90),
                DetectionResult("trousers", 0.88),
            ]
        )
        service = RaspberryVisionService(
            camera=camera,
            safety_detector=safety_detector,
            access_detector=access_detector,
        )
        service.open()

        disabled_result = service.process_once()
        self.assertEqual(disabled_result["details"]["safety"]["risk"], "EMERGENCY")
        self.assertEqual(disabled_result["details"]["access"]["status"], "DESABILITADO")
        self.assertEqual(len(safety_detector.frames), 1)
        self.assertEqual(access_detector.frames, [])

        self.assertTrue(service.toggle_access())
        enabled_result = service.process_once()
        service.stop()

        self.assertEqual(enabled_result["state"], SystemState.EMERGENCY)
        self.assertEqual(enabled_result["details"]["access"]["status"], "PERMITIDO")
        self.assertEqual(safety_detector.frames, ["ps3-eye-frame", "ps3-eye-frame"])
        self.assertEqual(access_detector.frames, ["ps3-eye-frame"])
        self.assertEqual(camera.read_count, 2)
        self.assertFalse(camera.opened)

    def test_access_alert_does_not_replace_continuous_safety_model(self):
        camera = DummyCamera("frame")
        safety_detector = SafetyDetector()
        access_detector = AccessDetector([DetectionResult("person", 0.95)])
        service = RaspberryVisionService(camera, safety_detector, access_detector)
        service.open()
        service.set_access_enabled(True)

        result = service.process_once()
        service.stop()

        self.assertEqual(result["state"], SystemState.ALERT)
        self.assertEqual(safety_detector.frames, ["frame"])
        self.assertEqual(result["details"]["safety"]["risk"], "NORMAL")

    def test_access_evaluation_requires_only_a_person_and_lab_coat(self):
        camera = DummyCamera("frame")
        access_detector = AccessDetector(
            [
                DetectionResult("person", 0.95),
                DetectionResult("lab_coat", 0.9),
                DetectionResult("trousers", 0.9),
                DetectionResult("closed_shoes", 0.9),
            ]
        )
        service = RaspberryVisionService(
            camera=camera,
            safety_detector=SafetyDetector(),
            access_detector=access_detector,
        )
        service.open()
        service.set_access_enabled(True)

        result = service.process_once()
        service.stop()

        self.assertEqual(result["details"]["access"]["status"], "PERMITIDO")
        self.assertEqual(result["details"]["access"]["person_count"], 1)
        self.assertEqual(result["details"]["access"]["compliant_count"], 1)

    def test_access_preview_draws_green_and_red_person_boxes(self):
        drawing_calls = []
        fake_cv2 = SimpleNamespace(
            rectangle=lambda frame, start, end, color, thickness: drawing_calls.append(
                ("rectangle", start, end, color)
            ),
            putText=lambda frame, text, origin, font, scale, color, thickness, line: drawing_calls.append(
                ("text", text, color)
            ),
            imencode=lambda extension, frame: (
                True,
                SimpleNamespace(tobytes=lambda: b"jpeg"),
            ),
            FONT_HERSHEY_SIMPLEX=0,
            LINE_AA=1,
        )
        detections = [
            DetectionResult("person_with_labcoat", 0.91, 10, 20, 100, 180),
            DetectionResult("person_without_labcoat", 0.87, 120, 25, 210, 185),
        ]
        service = RaspberryVisionService(
            camera=DummyCamera(DummyFrame()),
            safety_detector=SafetyDetector(),
            access_detector=AccessDetector(detections),
            preview_enabled=True,
        )
        service.open()
        service.set_access_enabled(True)

        with patch("raspberry_pi.vision.cv2", fake_cv2):
            service.process_once()
            annotated_calls = list(drawing_calls)
            with service._lock:
                service._access_annotations_updated_at = time.monotonic() - 2
            service._store_preview(DummyFrame())
        service.stop()

        self.assertIn(("rectangle", (10, 20), (100, 180), (0, 200, 0)), drawing_calls)
        self.assertIn(("rectangle", (120, 25), (210, 185), (0, 0, 255)), drawing_calls)
        self.assertIn(("text", "COM JALECO 91%", (0, 200, 0)), drawing_calls)
        self.assertIn(("text", "SEM JALECO 87%", (0, 0, 255)), drawing_calls)
        self.assertEqual(drawing_calls, annotated_calls)

    def test_access_status_uses_majority_of_each_five_second_window(self):
        service = RaspberryVisionService(
            camera=DummyCamera("frame"),
            access_detector=AccessDetector(),
            access_vote_window_seconds=5,
        )

        def result_at(second, status):
            return service._stabilize_access_result(
                {
                    "status": status,
                    "enabled": True,
                    "annotations": [
                        {
                            "x1": 10,
                            "y1": 10,
                            "x2": 100,
                            "y2": 180,
                            "status": status,
                            "confidence": 0.9,
                        }
                    ],
                    "detections": [],
                },
                second,
            )

        self.assertEqual(result_at(0, "PERMITIDO")["status"], "AGUARDANDO")
        result_at(1, "ALERTA")
        result_at(2, "PERMITIDO")
        result_at(3, "ALERTA")
        self.assertEqual(result_at(4, "PERMITIDO")["status"], "AGUARDANDO")
        first_window = result_at(5, "ALERTA")
        self.assertEqual(first_window["status"], "PERMITIDO")
        self.assertEqual(first_window["annotations"][0]["status"], "PERMITIDO")

        result_at(6, "ALERTA")
        result_at(7, "ALERTA")
        result_at(8, "PERMITIDO")
        result_at(9, "ALERTA")
        second_window = result_at(10, "ALERTA")
        self.assertEqual(second_window["status"], "ALERTA")
        self.assertEqual(second_window["annotations"][0]["status"], "ALERTA")

    def test_access_vote_tracks_people_independently_across_frames(self):
        service = RaspberryVisionService(
            camera=DummyCamera("frame"),
            access_detector=AccessDetector(),
            access_vote_window_seconds=5,
        )
        result = None
        for second in range(6):
            result = service._stabilize_access_result(
                {
                    "status": "ALERTA",
                    "enabled": True,
                    "annotations": [
                        {
                            "x1": 10 + second,
                            "y1": 10,
                            "x2": 100 + second,
                            "y2": 180,
                            "status": "PERMITIDO",
                            "confidence": 0.9,
                        },
                        {
                            "x1": 200 + second,
                            "y1": 10,
                            "x2": 290 + second,
                            "y2": 180,
                            "status": "ALERTA",
                            "confidence": 0.9,
                        },
                    ],
                    "detections": [],
                },
                second,
            )

        self.assertEqual(result["status"], "ALERTA")
        self.assertEqual(result["person_count"], 2)
        self.assertEqual(result["compliant_count"], 1)
        self.assertEqual(
            [annotation["status"] for annotation in result["annotations"]],
            ["PERMITIDO", "ALERTA"],
        )

    def test_access_evaluation_does_not_require_unconfigured_equipment(self):
        camera = DummyCamera("frame")
        access_detector = AccessDetector(
            [
                DetectionResult("person", 0.95),
                DetectionResult("lab_coat", 0.9),
                DetectionResult("trousers", 0.9),
                DetectionResult("closed_shoes", 0.9),
                DetectionResult("long_hair", 0.9),
            ]
        )
        service = RaspberryVisionService(
            camera=camera,
            safety_detector=SafetyDetector(),
            access_detector=access_detector,
        )
        service.open()
        service.set_access_enabled(True)

        result = service.process_once()
        service.stop()

        self.assertEqual(result["details"]["access"]["status"], "PERMITIDO")

    def test_access_only_model_starts_enabled_without_visual_safety_model(self):
        camera = DummyCamera("frame")
        access_detector = AccessDetector(
            [
                DetectionResult("person", 0.95, 10, 10, 90, 100),
                DetectionResult("lab_coat", 0.9, 25, 20, 75, 65),
            ]
        )
        service = RaspberryVisionService(
            camera=camera,
            access_detector=access_detector,
        )
        service.open()

        self.assertTrue(service.snapshot()["access_enabled"])
        result = service.process_once()
        service.stop()

        self.assertEqual(result["details"]["safety"]["risk"], "NAO_CONFIGURADO")
        self.assertEqual(result["details"]["access"]["status"], "PERMITIDO")
        self.assertEqual(result["state"], SystemState.NORMAL)

    def test_lab_coat_is_associated_with_its_person(self):
        service = RaspberryVisionService(
            camera=DummyCamera("frame"),
            access_detector=AccessDetector(
                [
                    DetectionResult("person", 0.95, 0, 0, 100, 200),
                    DetectionResult("person", 0.95, 100, 0, 200, 200),
                    DetectionResult("lab_coat", 0.9, 20, 20, 80, 80),
                ]
            ),
        )
        service.open()

        result = service.process_once()
        service.stop()

        access = result["details"]["access"]
        self.assertEqual(access["status"], "ALERTA")
        self.assertEqual(access["person_count"], 2)
        self.assertEqual(access["compliant_count"], 1)
        self.assertIn("Jaleco ausente em 1 pessoa(s)", access["reasons"])

    def test_person_status_classes_evaluate_each_detected_person(self):
        service = RaspberryVisionService(
            camera=DummyCamera("frame"),
            access_detector=AccessDetector(
                [
                    DetectionResult("person_with_labcoat", 0.94, 10, 10, 90, 100),
                    DetectionResult("person_without_labcoat", 0.91, 100, 10, 190, 100),
                ]
            ),
        )
        service.open()

        result = service.process_once()
        service.stop()

        access = result["details"]["access"]
        self.assertEqual(access["status"], "ALERTA")
        self.assertEqual(access["person_count"], 2)
        self.assertEqual(access["compliant_count"], 1)
        self.assertIn("Jaleco ausente em 1 pessoa(s)", access["reasons"])

    def test_person_status_model_allows_all_detected_people_with_labcoats(self):
        service = RaspberryVisionService(
            camera=DummyCamera("frame"),
            access_detector=AccessDetector(
                [
                    DetectionResult("person_with_labcoat", 0.94),
                    DetectionResult("person_with_labcoat", 0.90),
                ]
            ),
        )
        service.open()

        result = service.process_once()
        service.stop()

        access = result["details"]["access"]
        self.assertEqual(access["status"], "PERMITIDO")
        self.assertEqual(access["person_count"], 2)
        self.assertEqual(access["compliant_count"], 2)

    def test_access_model_error_is_not_reported_as_normal(self):
        def fail_to_create_detector():
            raise RuntimeError("invalid model")

        service = RaspberryVisionService(
            camera=DummyCamera("frame"),
            access_detector_factory=fail_to_create_detector,
        )
        service.open()

        with self.assertLogs("raspberry_pi.vision", level="ERROR"):
            result = service.process_once()
        service.stop()

        self.assertEqual(result["details"]["access"]["status"], "ERRO")
        self.assertEqual(result["state"], SystemState.ALERT)
        self.assertFalse(result["safety_ready"])

    def test_access_only_camera_failure_is_not_reported_as_normal(self):
        camera = DummyCamera(None)
        camera.last_error = "camera disconnected"
        service = RaspberryVisionService(
            camera=camera,
            access_detector=AccessDetector(),
        )
        service.open()

        with self.assertLogs("raspberry_pi.vision", level="WARNING"):
            result = service.process_once()
        service.stop()

        self.assertEqual(result["details"]["access"]["status"], "ERRO")
        self.assertEqual(result["state"], SystemState.ALERT)
        self.assertFalse(result["safety_ready"])

    def test_no_person_does_not_report_missing_ppe(self):
        camera = DummyCamera("entry")
        service = RaspberryVisionService(
            camera=camera,
            safety_detector=SafetyDetector(),
            access_detector=AccessDetector(),
        )
        service.open()
        service.set_access_enabled(True)

        result = service.process_once()
        service.stop()

        self.assertEqual(result["state"], SystemState.NORMAL)
        self.assertEqual(result["details"]["access"]["status"], "SEM_PESSOA")

    def test_cannot_enable_unconfigured_access_model(self):
        service = RaspberryVisionService(
            camera=DummyCamera("frame"),
            safety_detector=SafetyDetector(),
        )

        with self.assertRaisesRegex(ValueError, "não foi configurado"):
            service.set_access_enabled(True)

    def test_factory_loads_access_model_only_while_enabled(self):
        created_detectors: List[AccessDetector] = []

        def create_detector() -> AccessDetector:
            detector = AccessDetector()
            created_detectors.append(detector)
            return detector

        service = RaspberryVisionService(
            camera=DummyCamera("frame"),
            safety_detector=SafetyDetector(),
            access_detector_factory=create_detector,
        )
        service.open()
        service.process_once()
        self.assertEqual(created_detectors, [])

        service.set_access_enabled(True)
        service.process_once()
        self.assertEqual(len(created_detectors), 1)

        service.set_access_enabled(False)
        service.set_access_enabled(True)
        service.process_once()
        service.stop()

        self.assertEqual(len(created_detectors), 2)

    def test_access_model_failure_does_not_stop_safety_inference(self):
        attempts = 0

        def create_detector() -> AccessDetector:
            nonlocal attempts
            attempts += 1
            raise RuntimeError("falha simulada no modelo de acesso")

        camera = DummyCamera("frame")
        safety_detector = SafetyDetector()
        service = RaspberryVisionService(
            camera=camera,
            safety_detector=safety_detector,
            access_detector_factory=create_detector,
        )
        service.open()
        service.set_access_enabled(True)

        with self.assertLogs("raspberry_pi.vision", level="ERROR"):
            first_result = service.process_once()
            second_result = service.process_once()
        service.stop()

        self.assertEqual(first_result["details"]["access"]["status"], "ERRO")
        self.assertIn("falha simulada", first_result["details"]["access"]["error"])
        self.assertEqual(len(safety_detector.frames), 2)
        self.assertEqual(attempts, 2)
        self.assertEqual(second_result["details"]["safety"]["risk"], "NORMAL")

    def test_dashboard_command_controls_only_access_model(self):
        service = RaspberryVisionService(
            camera=DummyCamera("frame"),
            safety_detector=SafetyDetector(),
            access_detector=AccessDetector(),
        )

        _handle_access_command(
            {"command": "set_access_model", "enabled": True},
            service,
        )

        self.assertTrue(service.snapshot()["access_enabled"])
        self.assertEqual(service.snapshot()["details"]["access"]["status"], "AGUARDANDO")

        _handle_access_command(
            {"command": "set_access_model", "enabled": False},
            service,
        )

        self.assertFalse(service.snapshot()["access_enabled"])
        self.assertEqual(service.snapshot()["details"]["access"]["status"], "DESABILITADO")

    def test_disabling_access_during_inference_prevents_stale_enabled_status(self):
        started = threading.Event()
        release = threading.Event()

        class SlowAccessDetector(AccessDetector):
            def predict(self, image: object) -> List[DetectionResult]:
                self.frames.append(image)
                started.set()
                release.wait(timeout=2)
                return [DetectionResult("person", 0.95)]

        camera = DummyCamera("frame")
        access_detector = SlowAccessDetector()
        service = RaspberryVisionService(
            camera=camera,
            safety_detector=SafetyDetector(),
            access_detector=access_detector,
        )
        service.open()
        service.set_access_enabled(True)

        worker = threading.Thread(target=service.process_once)
        worker.start()
        self.assertTrue(started.wait(timeout=2))
        service.set_access_enabled(False)
        release.set()
        worker.join(timeout=2)
        service.stop()

        self.assertFalse(worker.is_alive())
        self.assertFalse(service.snapshot()["access_enabled"])
        self.assertEqual(service.snapshot()["details"]["access"]["status"], "DESABILITADO")
        self.assertEqual(len(access_detector.frames), 1)


if __name__ == "__main__":
    unittest.main()
