import logging
import random
import time
from dataclasses import dataclass, asdict
from typing import Optional

try:
    import adafruit_dht
    import board
except ImportError:  # pragma: no cover - depende do ambiente Raspberry
    adafruit_dht = None
    board = None

logger = logging.getLogger(__name__)
DHT22_MIN_INTERVAL_SECONDS = 2.0
SENSOR_STALE_AFTER_SECONDS = 5.0


@dataclass
class EnvironmentReading:
    temperature_c: Optional[float]
    humidity_pct: Optional[float]
    gas_ppm: Optional[float]
    smoke_detected: Optional[bool]
    gas_detected: Optional[bool] = None
    emergency_button_pressed: Optional[bool] = None
    reset_button_pressed: Optional[bool] = None
    dht_age_seconds: Optional[float] = None

    def to_dict(self):
        return asdict(self)


class EnvironmentMonitor:
    """Leitura de sensores ambientais para o laboratório."""

    def __init__(self, config, gpio_controller=None):
        self.config = config
        self.gpio = gpio_controller
        self.dht_device = None
        self._last_sample_at: Optional[float] = None
        self._last_dht_success_at: Optional[float] = None
        self._temperature_c: Optional[float] = None
        self._humidity_pct: Optional[float] = None
        self._gas_ppm: Optional[float] = None
        self._smoke_detected: Optional[bool] = None
        self._mock_gas_detected: Optional[bool] = None

        if not config.use_mock_hardware and adafruit_dht is not None and board is not None:
            try:
                pin = getattr(board, f"D{config.dht_pin}", None)
                if pin is None:
                    raise ValueError(f"O pino D{config.dht_pin} não existe no módulo board.")
                self.dht_device = adafruit_dht.DHT22(pin)
            except Exception as exc:  # pragma: no cover
                logger.warning("Falha ao inicializar DHT22: %s", exc)
                self.dht_device = None
        elif not config.use_mock_hardware:
            logger.warning(
                "Leitura real do DHT22 indisponível: instale adafruit-circuitpython-dht."
            )

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
            gas_detected=gas >= self.config.max_gas_ppm,
            emergency_button_pressed=False,
            reset_button_pressed=False,
        )

    def read(self):
        now = time.monotonic()
        sample_interval = max(
            self.config.read_interval_seconds,
            DHT22_MIN_INTERVAL_SECONDS,
        )
        if (
            self._last_sample_at is None
            or now - self._last_sample_at >= sample_interval
        ):
            if self.config.use_mock_hardware:
                mock_reading = self._read_mock()
                self._temperature_c = mock_reading.temperature_c
                self._humidity_pct = mock_reading.humidity_pct
                self._gas_ppm = mock_reading.gas_ppm
                self._smoke_detected = mock_reading.smoke_detected
                self._mock_gas_detected = mock_reading.gas_detected
                self._last_dht_success_at = now
            elif self.dht_device is not None:
                self._read_dht()
            self._last_sample_at = time.monotonic()

        now = time.monotonic()
        dht_age = (
            now - self._last_dht_success_at
            if self._last_dht_success_at is not None
            else None
        )
        if dht_age is not None and dht_age > SENSOR_STALE_AFTER_SECONDS:
            temperature_c = None
            humidity_pct = None
            dht_age_seconds = round(dht_age, 1)
        else:
            temperature_c = self._temperature_c
            humidity_pct = self._humidity_pct
            dht_age_seconds = round(dht_age, 1) if dht_age is not None else None

        if self.config.use_mock_hardware:
            return EnvironmentReading(
                temperature_c=temperature_c,
                humidity_pct=humidity_pct,
                gas_ppm=self._gas_ppm,
                smoke_detected=self._smoke_detected,
                gas_detected=self._mock_gas_detected,
                emergency_button_pressed=False,
                reset_button_pressed=False,
                dht_age_seconds=dht_age_seconds,
            )

        gas_detected = None
        button_pressed = None
        reset_pressed = None
        if self.gpio is not None:
            gas_level = self.gpio.read_input(self.config.mq2_digital_pin)
            if gas_level is not None:
                gas_detected = (
                    not gas_level if self.config.mq2_active_low else gas_level
                )
            button_pressed = self.gpio.emergency_button_pressed
            reset_pressed = self.gpio.reset_button_pressed

        return EnvironmentReading(
            temperature_c=temperature_c,
            humidity_pct=humidity_pct,
            gas_ppm=None,
            smoke_detected=None,
            gas_detected=gas_detected,
            emergency_button_pressed=button_pressed,
            reset_button_pressed=reset_pressed,
            dht_age_seconds=dht_age_seconds,
        )

    def _read_dht(self):
        try:
            temperature = self.dht_device.temperature
            humidity = self.dht_device.humidity
            if temperature is None or humidity is None:
                logger.warning("Leitura incompleta do DHT22; mantendo o último valor válido.")
                return
            self._temperature_c = round(float(temperature), 2)
            self._humidity_pct = round(float(humidity), 2)
            self._last_dht_success_at = time.monotonic()
        except RuntimeError as exc:
            logger.warning("Falha de leitura do DHT22: %s", exc)

    def summary(self, reading):
        return {
            "temperature_c": reading.temperature_c,
            "humidity_pct": reading.humidity_pct,
            "gas_ppm": reading.gas_ppm,
            "smoke_detected": reading.smoke_detected,
            "gas_detected": reading.gas_detected,
            "emergency_button_pressed": reading.emergency_button_pressed,
            "reset_button_pressed": reading.reset_button_pressed,
            "dht_age_seconds": reading.dht_age_seconds,
        }

    def close(self):
        if self.dht_device is not None:
            self.dht_device.exit()
            self.dht_device = None
