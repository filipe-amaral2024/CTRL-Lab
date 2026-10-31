from __future__ import annotations

import hmac
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional, Tuple

logger = logging.getLogger(__name__)
Preview = Tuple[int, bytes]


class CameraStreamServer:
    """Publica frames JPEG recentes da câmera sem capturar outro stream."""

    def __init__(
        self,
        preview_provider: Callable[[], Optional[Preview]],
        token: str,
        host: str = "0.0.0.0",
        port: int = 8081,
    ):
        if len(token) < 16:
            raise ValueError("O token da câmera deve ter pelo menos 16 caracteres.")
        self.preview_provider = preview_provider
        self.token = token
        self._server = ThreadingHTTPServer(
            (host, port),
            self._make_handler(),
        )
        self._server.daemon_threads = True
        self._worker = None
        self._started = False
        self._closed = False
        self._stop_event = threading.Event()

    @property
    def address(self):
        return self._server.server_address

    def start(self):
        if self._closed:
            raise RuntimeError("O servidor de câmera já foi encerrado.")
        if self._worker is not None and self._worker.is_alive():
            raise RuntimeError("O servidor de câmera já está em execução.")
        self._worker = threading.Thread(
            target=self._server.serve_forever,
            name="ctrlab-camera-stream",
            daemon=True,
        )
        self._worker.start()
        self._started = True
        logger.info(
            "Pré-visualização da câmera disponível em http://%s:%s/video.mjpg",
            self.address[0],
            self.address[1],
        )

    def stop(self):
        if self._closed:
            return
        self._stop_event.set()
        if self._started:
            self._server.shutdown()
        self._server.server_close()
        if self._worker is not None:
            self._worker.join(timeout=2.0)
            self._worker = None
        self._closed = True

    def _make_handler(self):
        stream = self

        class CameraStreamRequestHandler(BaseHTTPRequestHandler):
            server_version = "CTRL-Lab-Camera"

            def do_GET(self):
                if self.path != "/video.mjpg":
                    self._send_json(404, {"error": "Endpoint não encontrado."})
                    return
                supplied_token = self.headers.get("X-CTRL-Lab-Token", "")
                if not hmac.compare_digest(supplied_token, stream.token):
                    self._send_json(403, {"error": "Token de câmera inválido."})
                    return

                first_frame = stream.preview_provider()
                if first_frame is None:
                    self._send_json(503, {"error": "A câmera ainda não forneceu um frame."})
                    return

                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "multipart/x-mixed-replace; boundary=frame",
                )
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Accel-Buffering", "no")
                self.end_headers()

                last_sequence = 0
                try:
                    while not stream._stop_event.is_set():
                        current = stream.preview_provider()
                        if current is not None and current[0] != last_sequence:
                            last_sequence, jpeg = current
                            self.wfile.write(
                                b"--frame\r\n"
                                b"Content-Type: image/jpeg\r\n"
                                + f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii")
                                + jpeg
                                + b"\r\n"
                            )
                            self.wfile.flush()
                        stream._stop_event.wait(0.05)
                except (BrokenPipeError, ConnectionResetError):
                    return

            def _send_json(self, status_code: int, payload: dict):
                content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(content)

            def log_message(self, format_string, *args):
                logger.info("%s - %s", self.address_string(), format_string % args)

        return CameraStreamRequestHandler
