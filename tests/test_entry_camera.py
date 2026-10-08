import unittest

from app.cameras.entry_camera import CameraConfig, StreamCamera


class StreamCameraTests(unittest.TestCase):
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
