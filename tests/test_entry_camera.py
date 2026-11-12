import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.cameras.entry_camera import CameraConfig, StreamCamera


class StreamCameraTests(unittest.TestCase):
    def test_camera_requests_single_frame_buffer_to_reduce_latency(self):
        class FakeCapture:
            def __init__(self):
                self.properties = []
                self.released = False

            def isOpened(self):
                return True

            def set(self, property_id, value):
                self.properties.append((property_id, value))
                return True

            def release(self):
                self.released = True

        capture = FakeCapture()
        fake_cv2 = SimpleNamespace(
            CAP_PROP_BUFFERSIZE=1,
            CAP_PROP_FRAME_WIDTH=2,
            CAP_PROP_FRAME_HEIGHT=3,
            CAP_PROP_FPS=4,
            VideoCapture=lambda source: capture,
        )
        camera = StreamCamera(
            CameraConfig(name="entry", width=640, height=480, fps=24)
        )

        with patch("app.cameras.entry_camera.cv2", fake_cv2):
            camera.open()
            camera.close()

        self.assertIn((fake_cv2.CAP_PROP_BUFFERSIZE, 1), capture.properties)
        self.assertTrue(capture.released)

    def test_camera_config_builds_url(self):
        config = CameraConfig(
            name="entry",
            url="http://192.168.0.10:8080/video",
            width=1280,
            height=720,
        )

        self.assertEqual(config.source_url, "http://192.168.0.10:8080/video")
        self.assertTrue(config.is_ip_stream)

    def test_camera_can_be_created_without_opening_device(self):
        camera = StreamCamera(CameraConfig(name="entry", url="http://example.com/stream"))
        self.assertEqual(camera.name, "entry")
        self.assertEqual(camera.config.source_url, "http://example.com/stream")


if __name__ == "__main__":
    unittest.main()
