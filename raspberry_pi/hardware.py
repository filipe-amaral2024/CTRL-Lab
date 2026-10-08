import logging
from typing import Optional

logger = logging.getLogger(__name__)


class GPIOController:
    """Abstração para GPIO do Raspberry Pi com fallback para modo mock."""

    def __init__(self, config, use_mock: Optional[bool] = None):
        self.config = config
        self.use_mock = config.use_mock_hardware if use_mock is None else use_mock
        self.gpio = None
        self._initialized = False

        if self.use_mock:
            logger.info("GPIO em modo mock ativado.")
            return

        try:
            import RPi.GPIO as GPIO
        except ImportError:
            logger.warning("RPi.GPIO não encontrado. Usando modo mock.")
            self.use_mock = True
            return

        self.gpio = GPIO
        self._initialized = True
        self.gpio.setmode(self.gpio.BCM)

    def setup(self):
        if self.use_mock:
            return

        if not self._initialized:
            self.__init__(self.config, use_mock=self.use_mock)

        if self.gpio is None:
            return

        for pin in self.config.pins.values():
            self.gpio.setup(pin, self.gpio.OUT, initial=self.gpio.LOW)

    def set_output(self, pin: int, value: bool):
        if self.use_mock:
            return

        if self.gpio is None:
            return

        self.gpio.output(pin, self.gpio.HIGH if value else self.gpio.LOW)

    def set_led(self, name: str, on: bool):
        if name not in self.config.pins:
            raise ValueError(f"LED inválido: {name}")
        self.set_output(self.config.pins[name], on)

    def set_buzzer(self, on: bool):
        self.set_output(self.config.buzzer_pin, on)

    def set_siren(self, on: bool):
        self.set_output(self.config.siren_pin, on)

    def cleanup(self):
        if self.gpio is None:
            return

        try:
            for pin in self.config.pins.values():
                self.gpio.output(pin, self.gpio.LOW)
            self.gpio.cleanup()
        finally:
            self.gpio = None
