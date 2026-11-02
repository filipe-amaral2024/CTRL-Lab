import unittest
from types import SimpleNamespace

from raspberry_pi.main import _run_camera_test


class FakeCamera:
    def __init__(self, fail_on_frame=None):
        self.fail_on_frame = fail_on_frame
        self.frames_read = 0
        self.last_error = "camera frame failure"
        self.opened = False
        self.closed = False

    def open(self):
        self.opened = True

    def read_frame(self):
        self.frames_read += 1
        if self.frames_read == self.fail_on_frame:
            return None
        return SimpleNamespace(shape=(480, 640, 3))

    def close(self):
        self.closed = True


class CameraSmokeTestTests(unittest.TestCase):
    def test_camera_test_captures_requested_frames_and_closes_camera(self):
        camera = FakeCamera()

        with self.assertLogs("raspberry_pi.main", level="INFO") as logs:
            _run_camera_test(camera, frame_count=3)

        self.assertTrue(camera.opened)
        self.assertEqual(camera.frames_read, 3)
        self.assertTrue(camera.closed)
        self.assertIn("3 frames", logs.output[0])

    def test_camera_test_closes_camera_when_frame_capture_fails(self):
        camera = FakeCamera(fail_on_frame=2)

        with self.assertRaisesRegex(RuntimeError, "camera frame failure"):
            _run_camera_test(camera, frame_count=3)

        self.assertTrue(camera.closed)


if __name__ == "__main__":
    unittest.main()
