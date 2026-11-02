import sys
import types
import unittest
from unittest.mock import patch

from raspberry_pi.config import RaspberryConfig
from raspberry_pi.hardware import GPIOController


class FakeGPIO:
    BCM = "BCM"
    OUT = "OUT"
    IN = "IN"
    LOW = 0
    HIGH = 1
    PUD_UP = "PUD_UP"
    BOTH = "BOTH"

    def __init__(self):
        self.inputs = {}
        self.input_setup = {}
        self.event_callbacks = {}
        self.removed_events = []

    def setmode(self, mode):
        self.mode = mode

    def setup(self, pin, direction, initial=None, pull_up_down=None):
        if direction == self.IN:
            self.input_setup[pin] = pull_up_down
            self.inputs[pin] = self.HIGH

    def input(self, pin):
        return self.inputs[pin]

    def output(self, pin, value):
        pass

    def add_event_detect(self, pin, edge, callback, bouncetime):
        self.event_callbacks[pin] = callback

    def remove_event_detect(self, pin):
        self.removed_events.append(pin)

    def cleanup(self):
        pass


class GPIOControllerTests(unittest.TestCase):
    def test_inputs_use_pullups_and_button_edges_update_pressed_state(self):
        fake_gpio = FakeGPIO()
        raspberry_module = types.ModuleType("RPi")
        raspberry_module.__path__ = []
        raspberry_module.GPIO = fake_gpio

        with patch.dict(
            sys.modules,
            {"RPi": raspberry_module, "RPi.GPIO": fake_gpio},
        ):
            controller = GPIOController(
                RaspberryConfig(use_mock_hardware=False),
            )
            controller.setup()

            self.assertEqual(
                fake_gpio.input_setup,
                {
                    controller.config.mq2_digital_pin: fake_gpio.PUD_UP,
                    controller.config.emergency_button_pin: fake_gpio.PUD_UP,
                    controller.config.reset_button_pin: fake_gpio.PUD_UP,
                },
            )

            fake_gpio.inputs[controller.config.emergency_button_pin] = fake_gpio.LOW
            fake_gpio.event_callbacks[controller.config.emergency_button_pin](
                controller.config.emergency_button_pin
            )
            self.assertTrue(controller.emergency_button_pressed)

            fake_gpio.inputs[controller.config.emergency_button_pin] = fake_gpio.HIGH
            fake_gpio.event_callbacks[controller.config.emergency_button_pin](
                controller.config.emergency_button_pin
            )
            self.assertFalse(controller.emergency_button_pressed)

            fake_gpio.inputs[controller.config.reset_button_pin] = fake_gpio.LOW
            fake_gpio.event_callbacks[controller.config.reset_button_pin](
                controller.config.reset_button_pin
            )
            self.assertTrue(controller.reset_button_pressed)

            controller.cleanup()
            self.assertEqual(
                fake_gpio.removed_events,
                [
                    controller.config.emergency_button_pin,
                    controller.config.reset_button_pin,
                ],
            )


if __name__ == "__main__":
    unittest.main()
