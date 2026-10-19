import json
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class SystemState(Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    ALERT = "ALERT"
    EMERGENCY = "EMERGENCY"


class AlertManager:
    """Gerencia estados do sistema e acionamento dos alertas físicos."""

    def __init__(self, config, mqtt_client=None, gpio_controller=None):
        self.config = config
        self.mqtt_client = mqtt_client
        self.gpio = gpio_controller
        self.state = SystemState.NORMAL

    def evaluate(self, reading):
        if reading.smoke_detected or reading.gas_ppm >= self.config.max_gas_ppm:
            return SystemState.EMERGENCY

        if (
            reading.temperature_c >= self.config.max_temperature_c
            or reading.humidity_pct >= self.config.max_humidity_pct
        ):
            return SystemState.ALERT

        if reading.gas_ppm > self.config.max_gas_ppm * 0.5:
            return SystemState.WARNING

        return SystemState.NORMAL

    def update(self, reading, vision_state=None, vision_details=None):
        new_state = self.evaluate(reading)
        if vision_state is not None:
            priorities = {
                SystemState.NORMAL: 0,
                SystemState.WARNING: 1,
                SystemState.ALERT: 2,
                SystemState.EMERGENCY: 3,
            }
            if priorities[vision_state] > priorities[new_state]:
                new_state = vision_state

        self.state = new_state
        self._apply_hardware(new_state)
        self._publish_status(reading, new_state, vision_details)
        return new_state

    def _apply_hardware(self, state):
        if self.gpio is None:
            return

        if state == SystemState.NORMAL:
            self.gpio.set_led("green", True)
            self.gpio.set_led("yellow", False)
            self.gpio.set_led("red", False)
            self.gpio.set_buzzer(False)
            self.gpio.set_siren(False)
        elif state == SystemState.WARNING:
            self.gpio.set_led("green", False)
            self.gpio.set_led("yellow", True)
            self.gpio.set_led("red", False)
            self.gpio.set_buzzer(True)
            self.gpio.set_siren(False)
        elif state == SystemState.ALERT:
            self.gpio.set_led("green", False)
            self.gpio.set_led("yellow", True)
            self.gpio.set_led("red", True)
            self.gpio.set_buzzer(True)
            self.gpio.set_siren(False)
        elif state == SystemState.EMERGENCY:
            self.gpio.set_led("green", False)
            self.gpio.set_led("yellow", False)
            self.gpio.set_led("red", True)
            self.gpio.set_buzzer(True)
            self.gpio.set_siren(True)

    def _publish_status(self, reading, state, vision_details=None):
        if self.mqtt_client is None:
            return

        payload = {
            "state": state.value,
            "temperature_c": reading.temperature_c,
            "humidity_pct": reading.humidity_pct,
            "gas_ppm": reading.gas_ppm,
            "smoke_detected": reading.smoke_detected,
        }
        if vision_details is not None:
            payload["vision"] = vision_details

        try:
            self.mqtt_client.publish(self.config.status_topic, json.dumps(payload), qos=1)
        except Exception as exc:  # pragma: no cover - comunicação externa
            logger.warning("Falha ao publicar status no MQTT: %s", exc)

    def startup(self):
        if self.gpio is not None:
            self.gpio.setup()
        self._apply_hardware(self.state)

    def shutdown(self):
        if self.gpio is not None:
            self.gpio.cleanup()
