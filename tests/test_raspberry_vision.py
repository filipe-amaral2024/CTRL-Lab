import unittest

from app.vision.yolo_base import DetectionResult
from raspberry_pi.alerts import SystemState
from raspberry_pi.vision import RaspberryVisionService


class DummyCamera:
    def __init__(self, frame):
        self.frame = frame
        self.last_error = None
        self.opened = False

    def open(self):
        self.opened = True

    def read_frame(self):
        return self.frame

    def close(self):
        self.opened = False


class DummyDetector:
    def predict(self, frame):
        if frame == "entry":
            return [
                DetectionResult("person", 0.95),
                DetectionResult("lab_coat", 0.90),
                DetectionResult("safety_glasses", 0.88),
            ]
        return [
            DetectionResult("smoke", 0.82),
            DetectionResult("fire", 0.10),
        ]


class RaspberryVisionServiceTests(unittest.TestCase):
    def test_runs_ppe_and_fire_decisions_on_camera_frames(self):
        entry_camera = DummyCamera("entry")
        lab_camera = DummyCamera("lab")
        service = RaspberryVisionService(
            entry_camera=entry_camera,
            lab_camera=lab_camera,
            detector=DummyDetector(),
        )
        service.open()

        result = service.process_once()
        service.stop()

        self.assertEqual(result["state"], SystemState.EMERGENCY)
        self.assertEqual(result["details"]["entry"]["status"], "ALERTA")
        self.assertIn("Calçado inadequado", result["details"]["entry"]["reasons"])
        self.assertEqual(result["details"]["lab"]["risk"], "EMERGENCY")
        self.assertFalse(entry_camera.opened)
        self.assertFalse(lab_camera.opened)

    def test_no_person_does_not_report_missing_ppe(self):
        class NoPersonDetector:
            def predict(self, frame):
                return []

        camera = DummyCamera("entry")
        service = RaspberryVisionService(
            entry_camera=camera,
            lab_camera=None,
            detector=NoPersonDetector(),
        )
        service.open()
        result = service.process_once()
        service.stop()

        self.assertEqual(result["state"], SystemState.NORMAL)
        self.assertEqual(result["details"]["entry"]["status"], "SEM_PESSOA")


if __name__ == "__main__":
    unittest.main()
