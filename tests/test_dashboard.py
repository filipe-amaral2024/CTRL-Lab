import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from central.dashboard import DashboardServer
from central.events import EventStore


class DummyListener:
    def __init__(self):
        self.connected = True
        self.handler = None
        self.commands = []

    def set_handler(self, handler):
        self.handler = handler

    def set_access_model_enabled(self, enabled):
        self.commands.append(enabled)
        return self.connected


class DashboardServerTests(unittest.TestCase):
    def setUp(self):
        descriptor, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.store = EventStore(self.db_path)
        self.listener = DummyListener()
        self.dashboard = DashboardServer(
            self.listener,
            self.store,
            host="127.0.0.1",
            port=0,
            control_token="test-control-token-123",
        )
        self.dashboard.start()
        self.base_url = f"http://127.0.0.1:{self.dashboard.address[1]}"

    def tearDown(self):
        self.dashboard.stop()
        os.remove(self.db_path)

    def request(self, path, method="GET", payload=None, token=None):
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if token is not None:
            headers["X-CTRL-Lab-Token"] = token
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        return urlopen(request, timeout=2)

    def test_dashboard_and_api_show_latest_status(self):
        self.listener.handler(
            {
                "state": "NORMAL",
                "temperature_c": 24.5,
                "vision": {
                    "safety": {"risk": "NORMAL"},
                    "access": {"status": "DESABILITADO", "enabled": False},
                },
            }
        )

        with self.request("/") as response:
            self.assertEqual(response.status, 200)
            page = response.read()
            self.assertIn(b"CTRL-Lab", page)
            self.assertIn(b"emergencyButton", page)
            self.assertIn(b"resetButton", page)
            self.assertIn(b"G\xc3\xa1s / limiar", page)

        with self.request("/api/state") as response:
            payload = json.loads(response.read())

        self.assertTrue(payload["mqtt_connected"])
        self.assertEqual(payload["status"]["temperature_c"], 24.5)
        self.assertTrue(payload["control_requires_token"])

    def test_remote_control_requires_token_and_sends_only_access_command(self):
        body = {"enabled": True}
        with self.assertRaises(HTTPError) as error:
            self.request("/api/access-model", method="POST", payload=body)
        self.assertEqual(error.exception.code, 403)
        error.exception.close()
        self.assertEqual(self.listener.commands, [])

        with self.request(
            "/api/access-model",
            method="POST",
            payload=body,
            token="test-control-token-123",
        ) as response:
            result = json.loads(response.read())

        self.assertEqual(response.status, 202)
        self.assertTrue(result["accepted"])
        self.assertEqual(self.listener.commands, [True])

    def test_remote_control_rejects_non_boolean_state(self):
        with self.assertRaises(HTTPError) as error:
            self.request(
                "/api/access-model",
                method="POST",
                payload={"enabled": "true"},
                token="test-control-token-123",
            )
        self.assertEqual(error.exception.code, 400)
        error.exception.close()
        self.assertEqual(self.listener.commands, [])

    def test_control_reports_missing_mqtt_connection(self):
        self.listener.connected = False

        with self.assertRaises(HTTPError) as error:
            self.request(
                "/api/access-model",
                method="POST",
                payload={"enabled": True},
                token="test-control-token-123",
            )
        self.assertEqual(error.exception.code, 503)
        error.exception.close()

    def test_camera_stream_is_proxied_with_server_side_token(self):
        received_tokens = []

        class CameraHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                received_tokens.append(self.headers.get("X-CTRL-Lab-Token"))
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "multipart/x-mixed-replace; boundary=frame",
                )
                self.end_headers()
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\njpeg\r\n")

            def log_message(self, format_string, *args):
                pass

        upstream = HTTPServer(("127.0.0.1", 0), CameraHandler)
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()
        camera_dashboard = DashboardServer(
            self.listener,
            self.store,
            host="127.0.0.1",
            port=0,
            camera_stream_url=f"http://127.0.0.1:{upstream.server_port}/video.mjpg",
            camera_stream_token="test-camera-token-123",
        )
        camera_dashboard.start()
        try:
            response = urlopen(
                f"http://127.0.0.1:{camera_dashboard.address[1]}/api/camera.mjpg?ts=1",
                timeout=2,
            )
            with response:
                body = response.read()
                self.assertEqual(response.status, 200)
                self.assertIn("multipart/x-mixed-replace", response.headers["Content-Type"])
                self.assertIn(b"--frame", body)
            self.assertEqual(received_tokens, ["test-camera-token-123"])
        finally:
            camera_dashboard.stop()
            upstream.shutdown()
            upstream.server_close()
            upstream_thread.join(timeout=2)

    def test_camera_stream_requires_configuration(self):
        with self.assertRaises(HTTPError) as error:
            self.request("/api/camera.mjpg")
        self.assertEqual(error.exception.code, 503)
        error.exception.close()


if __name__ == "__main__":
    unittest.main()
