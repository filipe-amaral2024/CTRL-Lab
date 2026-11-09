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
    buzzer_pin: int = 23
    mq2_digital_pin: int = 5
    emergency_button_pin: int = 6
    reset_button_pin: int = 13
    mq2_active_low: bool = True

    # Limites ambientais
    max_temperature_c: float = 30.0
    max_humidity_pct: float = 70.0
    max_gas_ppm: float = 0.7
    smoke_threshold: float = 0.8

    # Cadência máxima das leituras ambientais lentas, como o DHT22
    read_interval_seconds: float = 2.0

    @property
    def output_pins(self):
        return (self.buzzer_pin,)

    @property
    def input_pins(self):
        return {
            "mq2": self.mq2_digital_pin,
            "emergency_button": self.emergency_button_pin,
            "reset_button": self.reset_button_pin,
        }
