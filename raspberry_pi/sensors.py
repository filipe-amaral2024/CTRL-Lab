import logging
import random
from dataclasses import dataclass, asdict

try:
    import adafruit_dht
except ImportError:  # pragma: no cover - depende do ambiente Raspberry
    adafruit_dht = None

logger = logging.getLogger(__name__)


@dataclass
class EnvironmentReading:
    temperature_c: float
    humidity_pct: float
    gas_ppm: float
    smoke_detected: bool = False

    def to_dict(self):
        return asdict(self)


class EnvironmentMonitor:
    """Leitura de sensores ambientais para o laboratório."""

    def __init__(self, config):
        self.config = config
        self.dht_device = None

        if not config.use_mock_hardware and adafruit_dht is not None:
            try:
                self.dht_device = adafruit_dht.DHT22(config.dht_pin)
            except Exception as exc:  # pragma: no cover
                logger.warning("Falha ao inicializar DHT22: %s", exc)
                self.dht_device = None

    def _read_mock(self):
        temperature = 22.0 + random.uniform(-3.0, 6.0)
        humidity = 45.0 + random.uniform(-10.0, 25.0)
        gas = random.uniform(0.0, 1.3)
        smoke = gas > self.config.smoke_threshold
        return EnvironmentReading(
            temperature_c=round(temperature, 2),
            humidity_pct=round(max(0.0, min(100.0, humidity)), 2),
            gas_ppm=round(gas, 3),
            smoke_detected=smoke,
        )

    def read(self):
        if self.dht_device is not None:
            try:
                temperature = self.dht_device.temperature
                humidity = self.dht_device.humidity
                if temperature is not None and humidity is not None:
                    return EnvironmentReading(
                        temperature_c=round(float(temperature), 2),
                        humidity_pct=round(float(humidity), 2),
                        gas_ppm=0.0,
                        smoke_detected=False,
                    )
            except RuntimeError as exc:
                logger.warning("Falha de leitura do DHT22: %s", exc)

        return self._read_mock()

    def summary(self, reading):
        return {
            "temperature_c": reading.temperature_c,
            "humidity_pct": reading.humidity_pct,
            "gas_ppm": reading.gas_ppm,
            "smoke_detected": reading.smoke_detected,
        }
