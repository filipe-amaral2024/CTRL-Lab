#!/usr/bin/env python3
import argparse
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from raspberry_pi.alerts import AlertManager
from raspberry_pi.config import RaspberryConfig
from raspberry_pi.hardware import GPIOController
from raspberry_pi.mqtt_client import MQTTClientWrapper
from raspberry_pi.sensors import EnvironmentMonitor
from raspberry_pi.vision import RaspberryVisionService


logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Servidor Raspberry do projeto CTRL-Lab")
    parser.add_argument("--mock", action="store_true", help="Força uso de GPIO em modo mock")
    parser.add_argument("--broker", default="localhost", help="Endereço do broker MQTT")
    parser.add_argument("--interval", type=float, default=2.0, help="Intervalo entre leituras em segundos")
    parser.add_argument("--cycles", type=int, default=0, help="Número de ciclos antes encerrar. 0 = loop infinito")
    parser.add_argument("--entry-camera", help="URL IP da câmera de entrada")
    parser.add_argument("--lab-camera", help="URL IP da câmera do laboratório")
    parser.add_argument("--ai-model", help="Caminho para modelo YOLOv8 exportado para ONNX")
    parser.add_argument(
        "--ai-classes",
        default="person,lab_coat,safety_glasses,closed_shoes,tied_hair,smoke,fire",
        help="Classes do ONNX, separadas por vírgula e na ordem do modelo",
    )
    parser.add_argument("--inference-interval", type=float, default=3.0, help="Intervalo entre inferências em segundos")
    parser.add_argument("--image-size", type=int, default=320, help="Lado da imagem de entrada do modelo ONNX")
    return parser.parse_args()


def create_mqtt_client(config):
    client = MQTTClientWrapper(config)
    if client.connect():
        return client
    return None


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    camera_configured = bool(args.entry_camera or args.lab_camera)
    if camera_configured != bool(args.ai_model):
        raise SystemExit("Informe --ai-model junto com ao menos uma URL de câmera, ou não informe nenhum deles.")
    if args.inference_interval <= 0:
        raise SystemExit("--inference-interval deve ser maior que zero.")
    if args.image_size <= 0:
        raise SystemExit("--image-size deve ser maior que zero.")
    if args.interval <= 0:
        raise SystemExit("--interval deve ser maior que zero.")

    config = RaspberryConfig(
        use_mock_hardware=args.mock,
        mqtt_broker=args.broker,
        read_interval_seconds=args.interval,
    )

    vision_service = None
    if args.ai_model:
        from app.cameras.entry_camera import CameraConfig, StreamCamera
        from app.cameras.lab_camera import LabCamera, LabCameraConfig
        from app.vision.yolo_onnx import OpenCVDNNYOLODetector

        class_names = [name.strip() for name in args.ai_classes.split(",") if name.strip()]
        detector = OpenCVDNNYOLODetector(
            args.ai_model,
            class_names=class_names,
            input_size=args.image_size,
        )
        entry_camera = (
            StreamCamera(CameraConfig(name="entry", url=args.entry_camera))
            if args.entry_camera
            else None
        )
        lab_camera = (
            LabCamera(LabCameraConfig(name="lab", url=args.lab_camera))
            if args.lab_camera
            else None
        )
        vision_service = RaspberryVisionService(
            entry_camera=entry_camera,
            lab_camera=lab_camera,
            detector=detector,
            inference_interval_seconds=args.inference_interval,
        )

    gpio = GPIOController(config)
    mqtt_client = create_mqtt_client(config)
    monitor = EnvironmentMonitor(config)
    manager = AlertManager(config, mqtt_client=mqtt_client, gpio_controller=gpio)

    cycles = 0
    try:
        manager.startup()
        if vision_service is not None:
            vision_service.start()

        while True:
            reading = monitor.read()
            vision_snapshot = vision_service.snapshot() if vision_service is not None else None
            state = manager.update(
                reading,
                vision_state=vision_snapshot["state"] if vision_snapshot else None,
                vision_details=vision_snapshot["details"] if vision_snapshot else None,
            )
            logger.info(
                "Leitura -> temp=%.2fC umid=%.2f%% gas=%.3f smoke=%s => %s",
                reading.temperature_c,
                reading.humidity_pct,
                reading.gas_ppm,
                reading.smoke_detected,
                state.value,
            )

            cycles += 1
            if args.cycles > 0 and cycles >= args.cycles:
                break

            time.sleep(config.read_interval_seconds)
    finally:
        if vision_service is not None:
            vision_service.stop()
        manager.shutdown()
        if mqtt_client is not None:
            mqtt_client.disconnect()


if __name__ == "__main__":
    main()
