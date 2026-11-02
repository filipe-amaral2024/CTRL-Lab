from dataclasses import dataclass


@dataclass(frozen=True)
class RaspberryConfig:
    """Configurações base da unidade Raspberry Pi do CTRL-Lab."""

    use_mock_hardware: bool = True

    # MQTT / comunicação com o computador central
    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    status_topic: str = "ctrlab/raspberry/status"
    alert_topic: str = "ctrlab/raspberry/alerts"
    command_topic: str = "ctrlab/central/commands"

    # GPIO BCM (Raspberry Pi)
    dht_pin: int = 17
    red_led_pin: int = 22
    yellow_led_pin: int = 27
    green_led_pin: int = 24
    buzzer_pin: int = 23
    siren_pin: int = 18
    mq2_digital_pin: int = 5
    emergency_button_pin: int = 6
    reset_button_pin: int = 13
    mq2_active_low: bool = True

    # Limites ambientais
    max_temperature_c: float = 30.0
    max_humidity_pct: float = 70.0
    max_gas_ppm: float = 0.7
    smoke_threshold: float = 0.8

    # Loop principal
    read_interval_seconds: float = 2.0

    @property
    def pins(self):
        return {
            "red": self.red_led_pin,
            "yellow": self.yellow_led_pin,
            "green": self.green_led_pin,
            "buzzer": self.buzzer_pin,
            "siren": self.siren_pin,
        }

    @property
    def input_pins(self):
        return {
            "mq2": self.mq2_digital_pin,
            "emergency_button": self.emergency_button_pin,
            "reset_button": self.reset_button_pin,
        }
