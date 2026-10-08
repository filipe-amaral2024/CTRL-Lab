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


logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Servidor Raspberry do projeto CTRL-Lab")
    parser.add_argument("--mock", action="store_true", help="Força uso de GPIO em modo mock")
    parser.add_argument("--broker", default="localhost", help="Endereço do broker MQTT")
    parser.add_argument("--interval", type=float, default=2.0, help="Intervalo entre leituras em segundos")
    parser.add_argument("--cycles", type=int, default=0, help="Número de ciclos antes encerrar. 0 = loop infinito")
    return parser.parse_args()


def create_mqtt_client(config):
    client = MQTTClientWrapper(config)
    if client.connect():
        return client
    return None


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    config = RaspberryConfig(
        use_mock_hardware=args.mock,
        mqtt_broker=args.broker,
        read_interval_seconds=args.interval,
    )

    gpio = GPIOController(config)
    mqtt_client = create_mqtt_client(config)
    monitor = EnvironmentMonitor(config)
    manager = AlertManager(config, mqtt_client=mqtt_client, gpio_controller=gpio)

    manager.startup()

    cycles = 0
    try:
        while True:
            reading = monitor.read()
            state = manager.update(reading)
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
        manager.shutdown()
        if mqtt_client is not None:
            mqtt_client.disconnect()


if __name__ == "__main__":
    main()
