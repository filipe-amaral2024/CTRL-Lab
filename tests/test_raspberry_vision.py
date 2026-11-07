import threading
import time
import unittest
from types import SimpleNamespace
from typing import List, Optional
from unittest.mock import patch

from app.vision.yolo_base import DetectionResult
from raspberry_pi.alerts import SystemState
from raspberry_pi.main import _handle_access_command
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
                (service.latest_preview() is None or camera.read_count < 2)
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

    def test_safety_runs_continuously_and_access_is_opt_in_on_same_frame(self):
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
        self.assertEqual(enabled_result["details"]["access"]["status"], "ALERTA")
        self.assertIn(
            "Calçado fechado ausente",
            enabled_result["details"]["access"]["reasons"],
        )
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

    def test_access_evaluation_uses_only_lab_trousers_shoes_and_long_hair_rules(self):
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
        self.assertNotIn("safety_glasses", result["details"]["access"]["detections"])

    def test_access_evaluation_requires_long_hair_to_be_tied(self):
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

        self.assertEqual(result["details"]["access"]["status"], "ALERTA")
        self.assertIn(
            "Cabelo comprido não está amarrado",
            result["details"]["access"]["reasons"],
        )

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
