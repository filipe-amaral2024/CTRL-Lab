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
        self._emergency_latched = False
        self._reset_requested = False
        self._buzzer_on = None

    @property
    def emergency_latched(self):
        return self._emergency_latched

    @property
    def reset_requested(self):
        return self._reset_requested

    def evaluate(self, reading):
        if (
            reading.emergency_button_pressed is True
            or reading.smoke_detected is True
            or reading.gas_detected is True
            or (
                reading.gas_ppm is not None
                and reading.gas_ppm >= self.config.max_gas_ppm
            )
        ):
            return SystemState.EMERGENCY

        if (
            (
                reading.temperature_c is not None
                and reading.temperature_c >= self.config.max_temperature_c
            )
            or (
                reading.humidity_pct is not None
                and reading.humidity_pct >= self.config.max_humidity_pct
            )
        ):
            return SystemState.ALERT

        if (
            reading.gas_ppm is not None
            and reading.gas_ppm > self.config.max_gas_ppm * 0.5
        ):
            return SystemState.WARNING

        return SystemState.NORMAL

    def update(
        self,
        reading,
        vision_state=None,
        vision_details=None,
        vision_ready=True,
        publish_status=True,
    ):
        previous_state = self.state
        live_state = self.evaluate(reading)
        if vision_state is not None:
            priorities = {
                SystemState.NORMAL: 0,
                SystemState.WARNING: 1,
                SystemState.ALERT: 2,
                SystemState.EMERGENCY: 3,
            }
            if priorities[vision_state] > priorities[live_state]:
                live_state = vision_state

        if live_state == SystemState.EMERGENCY:
            self._emergency_latched = True

        if (
            self._emergency_latched
            and reading.reset_button_pressed is True
            and reading.emergency_button_pressed is not True
        ):
            self._reset_requested = True

        if (
            self._reset_requested
            and reading.emergency_button_pressed is not True
            and live_state != SystemState.EMERGENCY
            and vision_ready
        ):
            self._emergency_latched = False
            self._reset_requested = False

        new_state = (
            SystemState.EMERGENCY
            if self._emergency_latched
            else live_state
        )

        self.state = new_state
        self._apply_hardware(new_state)
        if publish_status or new_state != previous_state:
            self._publish_status(reading, new_state, vision_details)
        return new_state

    def _apply_hardware(self, state):
        if self.gpio is None:
            return

        buzzer_on = state in (SystemState.WARNING, SystemState.ALERT)
        if buzzer_on != self._buzzer_on:
            self.gpio.set_buzzer(buzzer_on)
            self._buzzer_on = buzzer_on

    def _publish_status(self, reading, state, vision_details=None):
        if self.mqtt_client is None:
            return

        payload = {
            "state": state.value,
            "temperature_c": reading.temperature_c,
            "humidity_pct": reading.humidity_pct,
            "gas_ppm": reading.gas_ppm,
            "smoke_detected": reading.smoke_detected,
            "gas_detected": reading.gas_detected,
            "emergency_button_pressed": reading.emergency_button_pressed,
            "reset_button_pressed": reading.reset_button_pressed,
            "dht_age_seconds": reading.dht_age_seconds,
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
