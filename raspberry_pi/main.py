#!/usr/bin/env python3
import argparse
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from raspberry_pi.alerts import AlertManager
from raspberry_pi.camera_preview import RaspberryCameraPreview
from raspberry_pi.camera_stream import CameraStreamServer
from raspberry_pi.config import RaspberryConfig
from raspberry_pi.hardware import GPIOController
from raspberry_pi.keyboard import KeyboardShortcutListener
from raspberry_pi.mqtt_client import MQTTClientWrapper
from raspberry_pi.sensors import EnvironmentMonitor
from raspberry_pi.vision import RaspberryVisionService


logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Servidor Raspberry do projeto CTRL-Lab")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Força leituras simuladas e saídas GPIO sem hardware",
    )
    parser.add_argument("--broker", default="localhost", help="Endereço do broker MQTT")
    parser.add_argument("--interval", type=float, default=2.0, help="Intervalo entre leituras em segundos")
    parser.add_argument("--cycles", type=int, default=0, help="Número de ciclos antes encerrar. 0 = loop infinito")
    parser.add_argument(
        "--mq2-active-high",
        action="store_true",
        help="Use se a saída DO do módulo MQ-2 ficar HIGH quando detectar gás",
    )
    parser.add_argument(
        "--camera-device",
        type=int,
        default=0,
        help="Índice da câmera USB PS3 Eye (padrão: 0)",
    )
    parser.add_argument(
        "--camera-test",
        action="store_true",
        help="Testa a captura da câmera sem exigir modelos ONNX",
    )
    parser.add_argument(
        "--camera-test-frames",
        type=int,
        default=30,
        help="Quantidade de frames capturados em --camera-test",
    )
    parser.add_argument("--safety-model", help="ONNX do modelo contínuo de fumaça/incêndio")
    parser.add_argument("--access-model", help="ONNX opcional do modelo de verificação de EPI/acesso")
    parser.add_argument(
        "--safety-classes",
        default="smoke,fire",
        help="Classes do modelo de segurança, separadas por vírgula e na ordem do modelo",
    )
    parser.add_argument(
        "--access-classes",
        default="person,lab_coat,trousers,closed_shoes,long_hair,tied_hair",
        help="Classes do modelo de acesso, separadas por vírgula e na ordem do modelo",
    )
    parser.add_argument("--inference-interval", type=float, default=3.0, help="Intervalo entre inferências em segundos")
    parser.add_argument("--image-size", type=int, default=320, help="Lado da imagem de entrada do modelo ONNX")
    parser.add_argument(
        "--camera-stream-token",
        default=os.environ.get("CTRL_LAB_CAMERA_TOKEN")
        or os.environ.get("CTRL_LAB_DASHBOARD_TOKEN"),
        help="Token da pré-visualização HTTP (ou CTRL_LAB_CAMERA_TOKEN)",
    )
    parser.add_argument("--camera-stream-host", default="0.0.0.0", help="Interface HTTP da câmera")
    parser.add_argument("--camera-stream-port", type=int, default=8081, help="Porta HTTP da câmera")
    return parser.parse_args()


def create_mqtt_client(config):
    client = MQTTClientWrapper(config)
    if client.connect():
        return client
    return None


def _parse_classes(class_names):
    return [name.strip() for name in class_names.split(",") if name.strip()]


def _run_camera_test(camera, frame_count):
    started_at = time.monotonic()
    frames = 0
    frame_shape = None
    try:
        camera.open()
        for _ in range(frame_count):
            frame = camera.read_frame()
            if frame is None:
                raise RuntimeError(
                    camera.last_error or "Não foi possível capturar um frame."
                )
            frame_shape = getattr(frame, "shape", None)
            frames += 1
    finally:
        camera.close()

    elapsed = time.monotonic() - started_at
    logger.info(
        "Teste de câmera concluído: %d frames em %.2fs (%.2f FPS), resolução=%s",
        frames,
        elapsed,
        frames / elapsed if elapsed > 0 else 0.0,
        frame_shape,
    )


def _handle_access_command(payload, vision_service):
    if not isinstance(payload, dict):
        logger.warning("Comando MQTT inválido: era esperado um objeto JSON.")
        return
    if payload.get("command") != "set_access_model":
        logger.warning("Comando MQTT não reconhecido: %s", payload.get("command"))
        return

    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        logger.warning("Comando set_access_model inválido: 'enabled' deve ser booleano.")
        return

    try:
        vision_service.set_access_enabled(enabled)
    except ValueError as exc:
        logger.warning("Não foi possível aplicar o comando de acesso: %s", exc)


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.access_model and not args.safety_model:
        raise SystemExit("--access-model exige --safety-model para manter a checagem de segurança ativa.")
    if args.camera_device < 0:
        raise SystemExit("--camera-device deve ser zero ou maior.")
    if args.camera_test_frames <= 0:
        raise SystemExit("--camera-test-frames deve ser maior que zero.")
    if args.inference_interval <= 0:
        raise SystemExit("--inference-interval deve ser maior que zero.")
    if args.image_size <= 0:
        raise SystemExit("--image-size deve ser maior que zero.")
    if args.interval <= 0:
        raise SystemExit("--interval deve ser maior que zero.")
    if not 0 < args.camera_stream_port < 65536:
        raise SystemExit("--camera-stream-port deve estar entre 1 e 65535.")
    if args.camera_stream_token is not None and len(args.camera_stream_token) < 16:
        raise SystemExit("O token da câmera deve ter pelo menos 16 caracteres.")
    if args.camera_test:
        from app.cameras.entry_camera import CameraConfig, StreamCamera

        camera = StreamCamera(
            CameraConfig(name="ps3_eye", width=640, height=480),
            fallback_device=args.camera_device,
        )
        _run_camera_test(camera, args.camera_test_frames)
        return

    config = RaspberryConfig(
        use_mock_hardware=args.mock,
        mqtt_broker=args.broker,
        read_interval_seconds=args.interval,
        mq2_active_low=not args.mq2_active_high,
    )

    vision_service = None
    camera_preview = None
    camera = None
    if args.safety_model or args.camera_stream_token:
        from app.cameras.entry_camera import CameraConfig, StreamCamera

        camera = StreamCamera(
            CameraConfig(name="ps3_eye", width=640, height=480),
            fallback_device=args.camera_device,
        )

    if args.safety_model:
        from app.vision.yolo_onnx import OpenCVDNNYOLODetector

        safety_detector = OpenCVDNNYOLODetector(
            args.safety_model,
            class_names=_parse_classes(args.safety_classes),
            input_size=args.image_size,
        )
        access_detector_factory = None
        if args.access_model:
            access_model_path = args.access_model
            access_classes = _parse_classes(args.access_classes)
            access_detector_factory = lambda: OpenCVDNNYOLODetector(
                access_model_path,
                class_names=access_classes,
                input_size=args.image_size,
            )
        vision_service = RaspberryVisionService(
            camera=camera,
            safety_detector=safety_detector,
            access_detector_factory=access_detector_factory,
            inference_interval_seconds=args.inference_interval,
            preview_enabled=bool(args.camera_stream_token),
        )
    elif args.camera_stream_token:
        camera_preview = RaspberryCameraPreview(camera)

    camera_stream_server = None
    if args.camera_stream_token:
        preview_provider = (
            vision_service.latest_preview
            if vision_service is not None
            else camera_preview.latest_preview
        )
        camera_stream_server = CameraStreamServer(
            preview_provider,
            token=args.camera_stream_token,
            host=args.camera_stream_host,
            port=args.camera_stream_port,
        )
    elif vision_service is not None:
        logger.info(
            "Pré-visualização HTTP desativada; configure CTRL_LAB_CAMERA_TOKEN para habilitá-la."
        )

    gpio = GPIOController(config)
    mqtt_client = create_mqtt_client(config)
    if mqtt_client is not None and vision_service is not None:
        active_vision_service = vision_service
        mqtt_client.add_callback(
            lambda payload: _handle_access_command(payload, active_vision_service)
        )

    monitor = EnvironmentMonitor(config, gpio_controller=gpio)
    manager = AlertManager(config, mqtt_client=mqtt_client, gpio_controller=gpio)
    keyboard_listener = (
        KeyboardShortcutListener(vision_service.toggle_access)
        if vision_service is not None and vision_service.access_available
        else None
    )

    cycles = 0
    try:
        manager.startup()
        reading = monitor.read()
        if (
            vision_service is not None
            and manager.evaluate(reading) != SystemState.EMERGENCY
        ):
            vision_service.start()
        if (
            camera_preview is not None
            and manager.evaluate(reading) != SystemState.EMERGENCY
        ):
            camera_preview.start()
        if camera_stream_server is not None:
            camera_stream_server.start()
        if keyboard_listener is not None:
            keyboard_listener.start()

        while True:
            if cycles:
                reading = monitor.read()
            sensor_state = manager.evaluate(reading)
            if (
                vision_service is not None
                and manager.emergency_latched
                and (
                    reading.reset_button_pressed is True
                    or manager.reset_requested
                )
                and reading.emergency_button_pressed is not True
                and sensor_state != SystemState.EMERGENCY
                and not vision_service.running
            ):
                try:
                    vision_service.start()
                    logger.info(
                        "Reset solicitado; visão reativada para confirmar condição segura."
                    )
                except RuntimeError:
                    logger.exception(
                        "Não foi possível reativar a visão; a emergência permanece travada."
                    )

            vision_snapshot = (
                vision_service.snapshot() if vision_service is not None else None
            )
            vision_ready = (
                vision_snapshot["safety_ready"] if vision_snapshot else True
            )
            state = manager.update(
                reading,
                vision_state=(
                    vision_snapshot["state"]
                    if vision_snapshot and vision_ready
                    else None
                ),
                vision_details=vision_snapshot["details"] if vision_snapshot else None,
                vision_ready=vision_ready,
            )
            logger.info(
                "Leitura -> temp=%sC umid=%s%% gas_ppm=%s gas_detected=%s "
                "smoke=%s emergency_button=%s => %s",
                reading.temperature_c,
                reading.humidity_pct,
                reading.gas_ppm,
                reading.gas_detected,
                reading.smoke_detected,
                reading.emergency_button_pressed,
                state.value,
            )
            if (
                state == SystemState.EMERGENCY
                and vision_service is not None
                and vision_service.running
                and (
                    vision_ready
                    or sensor_state == SystemState.EMERGENCY
                )
            ):
                if vision_service.stop():
                    logger.info(
                        "Emergência: câmera/visão pausadas; Raspberry, botões e MQTT permanecem ativos."
                    )
            if camera_preview is not None:
                if state == SystemState.EMERGENCY and camera_preview.running:
                    if camera_preview.stop():
                        logger.info(
                            "Emergência: pré-visualização pausada; Raspberry, botões e MQTT permanecem ativos."
                        )
                elif state != SystemState.EMERGENCY and not camera_preview.running:
                    camera_preview.start()

            cycles += 1
            if args.cycles > 0 and cycles >= args.cycles:
                break

            time.sleep(config.read_interval_seconds)
    finally:
        if keyboard_listener is not None:
            keyboard_listener.stop()
        if camera_stream_server is not None:
            camera_stream_server.stop()
        if vision_service is not None:
            vision_service.stop()
        if camera_preview is not None:
            camera_preview.stop()
        try:
            monitor.close()
        finally:
            try:
                manager.shutdown()
            finally:
                if mqtt_client is not None:
                    mqtt_client.disconnect()


if __name__ == "__main__":
    main()
