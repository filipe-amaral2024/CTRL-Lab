import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from raspberry_pi.camera_preview import RaspberryCameraPreview


class FakeCamera:
    def __init__(self):
        self.opened = False
        self.closed = False
        self.read_count = 0
        self.last_error = None

    def open(self):
        self.opened = True

    def read_frame(self):
        self.read_count += 1
        return "frame"

    def close(self):
        self.opened = False
        self.closed = True


class RaspberryCameraPreviewTests(unittest.TestCase):
    def test_preview_captures_frames_without_a_detector_and_can_restart(self):
        camera = FakeCamera()
        cv2 = SimpleNamespace(
            imencode=lambda extension, frame: (
                True,
                SimpleNamespace(tobytes=lambda: b"jpeg-frame"),
            )
        )
        preview = RaspberryCameraPreview(camera, preview_interval_seconds=0.01)

        with patch("raspberry_pi.camera_preview.cv2", cv2):
            preview.start()
            deadline = time.monotonic() + 2
            while preview.latest_preview() is None and time.monotonic() < deadline:
                time.sleep(0.01)

            first = preview.latest_preview()
            self.assertIsNotNone(first)
            self.assertEqual(first[1], b"jpeg-frame")
            self.assertTrue(preview.stop())
            self.assertFalse(camera.opened)
            self.assertIsNone(preview.latest_preview())

            camera.closed = False
            preview.start()
            deadline = time.monotonic() + 2
            while preview.latest_preview() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertIsNotNone(preview.latest_preview())
            self.assertTrue(preview.stop())

        self.assertGreater(camera.read_count, 1)

    def test_start_rejects_camera_that_cannot_open(self):
        camera = FakeCamera()
        camera.open = lambda: False
        preview = RaspberryCameraPreview(camera)

        with patch("raspberry_pi.camera_preview.cv2", SimpleNamespace()):
            with self.assertRaisesRegex(RuntimeError, "Could not open"):
                preview.start()


if __name__ == "__main__":
    unittest.main()
