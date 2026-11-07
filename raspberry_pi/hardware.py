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
        self._emergency_button_pressed = False
        self._reset_button_pressed = False
        self._button_event_registered = False

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

        for pin in self.config.output_pins:
            self.gpio.setup(pin, self.gpio.OUT, initial=self.gpio.LOW)
        for pin in self.config.input_pins.values():
            self.gpio.setup(
                pin,
                self.gpio.IN,
                pull_up_down=self.gpio.PUD_UP,
            )

        self._emergency_button_pressed = self._button_is_pressed(
            self.config.emergency_button_pin
        )
        self._reset_button_pressed = self._button_is_pressed(
            self.config.reset_button_pin
        )
        for pin in (
            self.config.emergency_button_pin,
            self.config.reset_button_pin,
        ):
            self.gpio.add_event_detect(
                pin,
                self.gpio.BOTH,
                callback=self._update_button,
                bouncetime=200,
            )
        self._button_event_registered = True

    def _button_is_pressed(self, pin):
        return not bool(self.gpio.input(pin))

    def _update_button(self, channel):
        pressed = self._button_is_pressed(channel)
        if channel == self.config.emergency_button_pin:
            self._emergency_button_pressed = pressed
        elif channel == self.config.reset_button_pin:
            self._reset_button_pressed = pressed

    def read_input(self, pin: int) -> Optional[bool]:
        if self.use_mock or self.gpio is None:
            return None
        return bool(self.gpio.input(pin))

    @property
    def emergency_button_pressed(self) -> Optional[bool]:
        if self.use_mock or self.gpio is None:
            return None
        return self._emergency_button_pressed

    @property
    def reset_button_pressed(self) -> Optional[bool]:
        if self.use_mock or self.gpio is None:
            return None
        return self._reset_button_pressed

    def set_output(self, pin: int, value: bool):
        if self.use_mock:
            return

        if self.gpio is None:
            return

        self.gpio.output(pin, self.gpio.HIGH if value else self.gpio.LOW)

    def set_buzzer(self, on: bool):
        self.set_output(self.config.buzzer_pin, on)

    def cleanup(self):
        if self.gpio is None:
            return

        try:
            if self._button_event_registered:
                for pin in (
                    self.config.emergency_button_pin,
                    self.config.reset_button_pin,
                ):
                    self.gpio.remove_event_detect(pin)
                self._button_event_registered = False
            for pin in self.config.output_pins:
                self.gpio.output(pin, self.gpio.LOW)
            self.gpio.cleanup()
        finally:
            self.gpio = None
