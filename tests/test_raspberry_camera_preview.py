import unittest
from types import SimpleNamespace
from unittest.mock import patch

from raspberry_pi.camera_preview import PREVIEW_FPS, RaspberryCameraPreview


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
    def test_default_preview_interval_targets_24_fps(self):
        preview = RaspberryCameraPreview(FakeCamera())

        self.assertAlmostEqual(
            preview.preview_interval_seconds,
            1 / 24,
        )
        self.assertEqual(PREVIEW_FPS, 24)

    def test_preview_captures_synchronously_at_the_configured_rate(self):
        camera = FakeCamera()
        cv2 = SimpleNamespace(
            imencode=lambda extension, frame: (
                True,
                SimpleNamespace(tobytes=lambda: b"jpeg-frame"),
            )
        )
        preview = RaspberryCameraPreview(camera, preview_interval_seconds=0.01)
        clock = [1.0]

        with (
            patch("raspberry_pi.camera_preview.cv2", cv2),
            patch("raspberry_pi.camera_preview.time.monotonic", side_effect=lambda: clock[0]),
        ):
            preview.start()
            self.assertTrue(preview.capture_if_due())
            first = preview.latest_preview()
            self.assertIsNotNone(first)
            self.assertEqual(first[1], b"jpeg-frame")
            clock[0] = 1.005
            self.assertFalse(preview.capture_if_due())
            self.assertEqual(camera.read_count, 1)
            clock[0] = 1.01
            self.assertTrue(preview.capture_if_due())
            self.assertEqual(camera.read_count, 2)
            self.assertTrue(preview.stop())
            self.assertFalse(camera.opened)
            self.assertIsNone(preview.latest_preview())

            camera.closed = False
            preview.start()
            clock[0] = 2.0
            self.assertTrue(preview.capture_if_due())
            self.assertTrue(preview.stop())

        self.assertEqual(camera.read_count, 3)

    def test_capture_requires_started_preview(self):
        camera = FakeCamera()
        preview = RaspberryCameraPreview(camera)

        with patch("raspberry_pi.camera_preview.cv2", SimpleNamespace()):
            with self.assertRaisesRegex(RuntimeError, "not running"):
                preview.capture_if_due()

    def test_start_rejects_camera_that_cannot_open(self):
        camera = FakeCamera()
        camera.open = lambda: False
        preview = RaspberryCameraPreview(camera)

        with patch("raspberry_pi.camera_preview.cv2", SimpleNamespace()):
            with self.assertRaisesRegex(RuntimeError, "Could not open"):
                preview.start()


if __name__ == "__main__":
    unittest.main()
