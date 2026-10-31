#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hmac
import json
import logging
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from central.events import EventStore
from central.mqtt_listener import CentralMQTTListener

logger = logging.getLogger(__name__)
DASHBOARD_HTML = Path(__file__).with_name("dashboard.html")
MAX_COMMAND_BYTES = 1024


class DashboardServer:
    """Dashboard HTTP para status MQTT, eventos e controle do modelo de acesso."""

    def __init__(
        self,
        listener: CentralMQTTListener,
        event_store: EventStore,
        host: str = "0.0.0.0",
        port: int = 8000,
        control_token: Optional[str] = None,
        camera_stream_url: Optional[str] = None,
        camera_stream_token: Optional[str] = None,
    ):
        if camera_stream_url is not None:
            parsed_url = urlsplit(camera_stream_url)
            if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
                raise ValueError("A URL da câmera deve usar HTTP ou HTTPS.")
            if not camera_stream_token or len(camera_stream_token) < 16:
                raise ValueError("Configure um token de câmera com pelo menos 16 caracteres.")
        self.listener = listener
        self.event_store = event_store
        self.control_token = control_token
        self.camera_stream_url = camera_stream_url
        self.camera_stream_token = camera_stream_token
        self._status_lock = threading.Lock()
        self._latest_status = None
        self._status_received_at = None
        self._server = ThreadingHTTPServer(
            (host, port),
            self._make_handler(),
        )
        self._server.daemon_threads = True
        self._worker = None
        self._started = False
        self._closed = False
        self.listener.set_handler(self.update_status)

    @property
    def address(self):
        return self._server.server_address

    def update_status(self, payload: dict):
        if not isinstance(payload, dict):
            logger.warning("Ignorando status MQTT que não é um objeto JSON.")
            return
        with self._status_lock:
            self._latest_status = dict(payload)
            self._status_received_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def snapshot(self):
        with self._status_lock:
            status = dict(self._latest_status) if self._latest_status is not None else None
            received_at = self._status_received_at
        return {
            "mqtt_connected": self.listener.connected,
            "status": status,
            "status_received_at": received_at,
            "events": self.event_store.get_recent_events(limit=20),
            "control_available": self.listener.connected,
            "control_requires_token": self.control_token is not None,
        }

    def start(self):
        if self._closed:
            raise RuntimeError("O dashboard já foi encerrado.")
        if self._worker is not None and self._worker.is_alive():
            raise RuntimeError("O dashboard já está em execução.")
        self._worker = threading.Thread(
            target=self._server.serve_forever,
            name="ctrlab-dashboard",
            daemon=True,
        )
        self._worker.start()
        self._started = True
        logger.info(
            "Dashboard disponível em http://%s:%s",
            self.address[0],
            self.address[1],
        )

    def wait(self):
        if self._worker is not None:
            self._worker.join()

    def stop(self):
        if self._closed:
            return
        if self._started:
            self._server.shutdown()
        self._server.server_close()
        if self._worker is not None:
            self._worker.join(timeout=2.0)
            self._worker = None
        self._closed = True

    def _make_handler(self):
        dashboard = self

        class DashboardRequestHandler(BaseHTTPRequestHandler):
            server_version = "CTRL-Lab-Dashboard"

            def do_GET(self):
                if self.path == "/":
                    self._send_file()
                    return
                if self.path == "/api/state":
                    self._send_json(200, dashboard.snapshot())
                    return
                if self.path.split("?", 1)[0] == "/api/camera.mjpg":
                    self._proxy_camera_stream()
                    return
                self._send_json(404, {"error": "Endpoint não encontrado."})

            def do_POST(self):
                if self.path != "/api/access-model":
                    self._send_json(404, {"error": "Endpoint não encontrado."})
                    return
                if not self._authorized():
                    self._send_json(
                        403,
                        {"error": "Token inválido ou não configurado para controle remoto."},
                    )
                    return
                if not dashboard.listener.connected:
                    self._send_json(
                        503,
                        {"error": "Sem conexão MQTT com o Raspberry Pi."},
                    )
                    return

                content_length = self.headers.get("Content-Length")
                try:
                    body_size = int(content_length or "0")
                except ValueError:
                    self._send_json(400, {"error": "Content-Length inválido."})
                    return
                if body_size <= 0 or body_size > MAX_COMMAND_BYTES:
                    self._send_json(413, {"error": "Tamanho de comando inválido."})
                    return
                if self.headers.get_content_type() != "application/json":
                    self._send_json(415, {"error": "Envie o comando como application/json."})
                    return

                try:
                    payload = json.loads(self.rfile.read(body_size))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._send_json(400, {"error": "JSON inválido."})
                    return
                if not isinstance(payload, dict) or not isinstance(payload.get("enabled"), bool):
                    self._send_json(
                        400,
                        {"error": "O campo 'enabled' deve ser booleano."},
                    )
                    return

                enabled = payload["enabled"]
                if not dashboard.listener.set_access_model_enabled(enabled):
                    self._send_json(
                        502,
                        {"error": "O broker não aceitou o comando de acesso."},
                    )
                    return
                self._send_json(
                    202,
                    {
                        "accepted": True,
                        "requested_enabled": enabled,
                        "message": "Comando enviado; aguardando confirmação no próximo status MQTT.",
                    },
                )

            def _authorized(self):
                if dashboard.control_token is None:
                    return False
                supplied_token = self.headers.get("X-CTRL-Lab-Token", "")
                return hmac.compare_digest(supplied_token, dashboard.control_token)

            def _send_file(self):
                try:
                    content = DASHBOARD_HTML.read_bytes()
                except OSError:
                    logger.exception("Não foi possível ler o arquivo do dashboard.")
                    self._send_json(500, {"error": "Interface gráfica indisponível."})
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'none'; script-src 'unsafe-inline'; "
                    "style-src 'unsafe-inline'; connect-src 'self'; img-src 'self'; "
                    "base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
                )
                self.end_headers()
                self.wfile.write(content)

            def _proxy_camera_stream(self):
                if dashboard.camera_stream_url is None:
                    self._send_json(
                        503,
                        {"error": "A pré-visualização da câmera não está configurada."},
                    )
                    return

                upstream_request = Request(
                    dashboard.camera_stream_url,
                    headers={
                        "X-CTRL-Lab-Token": dashboard.camera_stream_token or "",
                        "Accept": "multipart/x-mixed-replace",
                    },
                )
                try:
                    upstream = urlopen(upstream_request, timeout=10)
                except (HTTPError, URLError, TimeoutError, OSError) as exc:
                    logger.warning("Não foi possível conectar à câmera do Raspberry Pi: %s", exc)
                    self._send_json(
                        503,
                        {"error": "Câmera indisponível. Verifique o Raspberry Pi e o token."},
                    )
                    return

                content_type = upstream.headers.get("Content-Type", "")
                if not content_type.lower().startswith("multipart/x-mixed-replace"):
                    upstream.close()
                    self._send_json(
                        502,
                        {"error": "O Raspberry Pi não retornou um stream de câmera válido."},
                    )
                    return

                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Accel-Buffering", "no")
                self.end_headers()
                try:
                    while True:
                        chunk = upstream.read1(8192)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    return
                except (HTTPError, URLError, TimeoutError, OSError) as exc:
                    logger.warning("A conexão com o stream da câmera foi interrompida: %s", exc)
                finally:
                    upstream.close()

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

        return DashboardRequestHandler


def parse_args():
    parser = argparse.ArgumentParser(description="Dashboard web do CTRL-Lab")
    parser.add_argument("--host", default="0.0.0.0", help="Interface de rede (padrão: todas)")
    parser.add_argument("--port", type=int, default=8000, help="Porta HTTP (padrão: 8000)")
    parser.add_argument("--broker", default="localhost", help="Endereço do broker MQTT")
    parser.add_argument("--mqtt-port", type=int, default=1883, help="Porta do broker MQTT")
    parser.add_argument("--db", default="ctrlab_events.db", help="Arquivo SQLite para histórico")
    parser.add_argument(
        "--camera-stream-url",
        default=os.environ.get("CTRL_LAB_CAMERA_STREAM_URL"),
        help="URL MJPEG do Raspberry Pi (padrão: http://<broker>:8081/video.mjpg)",
    )
    parser.add_argument(
        "--camera-stream-token",
        default=os.environ.get("CTRL_LAB_CAMERA_TOKEN")
        or os.environ.get("CTRL_LAB_DASHBOARD_TOKEN"),
        help="Token do stream (ou CTRL_LAB_CAMERA_TOKEN)",
    )
    parser.add_argument(
        "--control-token",
        default=os.environ.get("CTRL_LAB_DASHBOARD_TOKEN"),
        help="Token para autorizar comandos remotos (ou variável CTRL_LAB_DASHBOARD_TOKEN)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not 0 < args.port < 65536:
        raise SystemExit("--port deve estar entre 1 e 65535.")
    if not 0 < args.mqtt_port < 65536:
        raise SystemExit("--mqtt-port deve estar entre 1 e 65535.")
    if args.control_token is not None and len(args.control_token) < 16:
        raise SystemExit("O token de controle deve ter pelo menos 16 caracteres.")
    if args.camera_stream_token is not None and len(args.camera_stream_token) < 16:
        raise SystemExit("O token da câmera deve ter pelo menos 16 caracteres.")
    camera_stream_url = args.camera_stream_url
    if camera_stream_url is None and args.camera_stream_token:
        camera_stream_url = f"http://{args.broker}:8081/video.mjpg"
    if camera_stream_url is not None and not args.camera_stream_token:
        raise SystemExit("Configure CTRL_LAB_CAMERA_TOKEN para proteger o stream da câmera.")

    store = EventStore(args.db)
    listener = CentralMQTTListener(
        store,
        broker=args.broker,
        port=args.mqtt_port,
    )
    dashboard = DashboardServer(
        listener,
        store,
        host=args.host,
        port=args.port,
        control_token=args.control_token,
        camera_stream_url=camera_stream_url,
        camera_stream_token=args.camera_stream_token,
    )
    if not listener.connect():
        logger.warning("Dashboard iniciará sem MQTT; estado e controles ficarão indisponíveis.")
    try:
        dashboard.start()
        dashboard.wait()
    except KeyboardInterrupt:
        logger.info("Encerrando dashboard.")
    finally:
        dashboard.stop()
        listener.disconnect()


if __name__ == "__main__":
    main()
