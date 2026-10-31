import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from raspberry_pi.camera_stream import CameraStreamServer


class CameraStreamServerTests(unittest.TestCase):
    TOKEN = "camera-stream-token-123"

    def setUp(self):
        self.preview = (1, b"jpeg-frame")
        self.server = CameraStreamServer(
            lambda: self.preview,
            token=self.TOKEN,
            host="127.0.0.1",
            port=0,
        )
        self.server.start()
        self.url = f"http://127.0.0.1:{self.server.address[1]}/video.mjpg"

    def tearDown(self):
        self.server.stop()

    def test_stream_requires_token(self):
        request = Request(self.url)
        with self.assertRaises(HTTPError) as error:
            urlopen(request, timeout=2)
        self.assertEqual(error.exception.code, 403)
        error.exception.close()

    def test_authorized_stream_returns_mjpeg_frames(self):
        request = Request(self.url, headers={"X-CTRL-Lab-Token": self.TOKEN})
        with urlopen(request, timeout=2) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("multipart/x-mixed-replace", response.headers["Content-Type"])
            self.assertIn(b"--frame", response.read(16))

    def test_preview_must_be_available_before_stream_starts(self):
        self.preview = None
        request = Request(self.url, headers={"X-CTRL-Lab-Token": self.TOKEN})
        with self.assertRaises(HTTPError) as error:
            urlopen(request, timeout=2)
        self.assertEqual(error.exception.code, 503)
        error.exception.close()

    def test_token_must_be_long_enough(self):
        with self.assertRaisesRegex(ValueError, "16 caracteres"):
            CameraStreamServer(lambda: None, token="short")


if __name__ == "__main__":
    unittest.main()
