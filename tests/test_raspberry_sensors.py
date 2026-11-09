import unittest
from types import SimpleNamespace
from unittest.mock import patch

from raspberry_pi.config import RaspberryConfig
from raspberry_pi.sensors import EnvironmentMonitor


class FakeGPIOInputs:
    def __init__(self, gas_level=True, button_pressed=False, reset_pressed=False):
        self.gas_level = gas_level
        self.emergency_button_pressed = button_pressed
        self.reset_button_pressed = reset_pressed

    def read_input(self, pin):
        return self.gas_level


class EnvironmentMonitorTests(unittest.TestCase):
    def test_real_mode_does_not_replace_missing_sensor_data_with_mock_values(self):
        with patch("raspberry_pi.sensors.adafruit_dht", None):
            monitor = EnvironmentMonitor(RaspberryConfig(use_mock_hardware=False))

        reading = monitor.read()

        self.assertIsNone(reading.temperature_c)
        self.assertIsNone(reading.humidity_pct)
        self.assertIsNone(reading.gas_ppm)
        self.assertIsNone(reading.smoke_detected)

    def test_real_dht_reading_leaves_analog_gas_value_unavailable(self):
        class FakeDHT:
            temperature = 23.5
            humidity = 48.0

        board_pin = object()
        with (
            patch("raspberry_pi.sensors.board", SimpleNamespace(D17=board_pin)),
            patch("raspberry_pi.sensors.adafruit_dht") as dht_module,
        ):
            dht_module.DHT22.return_value = FakeDHT()
            monitor = EnvironmentMonitor(RaspberryConfig(use_mock_hardware=False))

        reading = monitor.read()

        dht_module.DHT22.assert_called_once_with(board_pin)
        self.assertEqual(reading.temperature_c, 23.5)
        self.assertEqual(reading.humidity_pct, 48.0)
        self.assertIsNone(reading.gas_ppm)
        self.assertIsNone(reading.smoke_detected)
        self.assertIsNone(reading.gas_detected)

    def test_dht_is_not_read_more_frequently_than_every_two_seconds(self):
        class FakeDHT:
            def __init__(self):
                self.read_count = 0

            @property
            def temperature(self):
                self.read_count += 1
                return 23.5

            @property
            def humidity(self):
                return 48.0

        fake_device = FakeDHT()
        clock = [0.0]
        with (
            patch("raspberry_pi.sensors.board", SimpleNamespace(D17=object())),
            patch("raspberry_pi.sensors.adafruit_dht") as dht_module,
        ):
            dht_module.DHT22.return_value = fake_device
            monitor = EnvironmentMonitor(
                RaspberryConfig(use_mock_hardware=False, read_interval_seconds=0.1)
            )

        with patch("raspberry_pi.sensors.time.monotonic", side_effect=lambda: clock[0]):
            first = monitor.read()
            clock[0] = 0.5
            second = monitor.read()
            clock[0] = 2.0
            third = monitor.read()

        self.assertEqual(first.temperature_c, 23.5)
        self.assertEqual(second.temperature_c, 23.5)
        self.assertEqual(third.temperature_c, 23.5)
        self.assertEqual(fake_device.read_count, 2)
        self.assertEqual(first.dht_age_seconds, 0.0)
        self.assertEqual(second.dht_age_seconds, 0.5)
        self.assertEqual(third.dht_age_seconds, 0.0)

    def test_failed_dht_read_keeps_then_expires_last_good_value(self):
        class FakeDHT:
            def __init__(self):
                self.fail = False

            @property
            def temperature(self):
                if self.fail:
                    raise RuntimeError("sensor read failed")
                return 23.5

            @property
            def humidity(self):
                return 48.0

        device = FakeDHT()
        clock = [0.0]
        with (
            patch("raspberry_pi.sensors.board", SimpleNamespace(D17=object())),
            patch("raspberry_pi.sensors.adafruit_dht") as dht_module,
        ):
            dht_module.DHT22.return_value = device
            monitor = EnvironmentMonitor(RaspberryConfig(use_mock_hardware=False))

        with patch("raspberry_pi.sensors.time.monotonic", side_effect=lambda: clock[0]):
            fresh = monitor.read()
            device.fail = True
            clock[0] = 2.0
            stale_but_retained = monitor.read()
            clock[0] = 6.1
            expired = monitor.read()

        self.assertEqual(fresh.temperature_c, 23.5)
        self.assertEqual(stale_but_retained.temperature_c, 23.5)
        self.assertIsNone(expired.temperature_c)
        self.assertGreater(expired.dht_age_seconds, 5.0)

    def test_close_releases_dht_device(self):
        fake_device = SimpleNamespace(temperature=22.0, humidity=45.0, exit=lambda: None)
        fake_device.exit = unittest.mock.Mock()
        with (
            patch("raspberry_pi.sensors.board", SimpleNamespace(D17=object())),
            patch("raspberry_pi.sensors.adafruit_dht") as dht_module,
        ):
            dht_module.DHT22.return_value = fake_device
            monitor = EnvironmentMonitor(RaspberryConfig(use_mock_hardware=False))

        monitor.close()

        fake_device.exit.assert_called_once_with()
        self.assertIsNone(monitor.dht_device)

    def test_active_low_mq2_output_is_detected(self):
        gpio = FakeGPIOInputs(gas_level=False)
        with patch("raspberry_pi.sensors.adafruit_dht", None):
            monitor = EnvironmentMonitor(
                RaspberryConfig(use_mock_hardware=False),
                gpio_controller=gpio,
            )

        reading = monitor.read()

        self.assertTrue(reading.gas_detected)
        self.assertFalse(reading.emergency_button_pressed)

    def test_active_high_mq2_output_is_detected_when_configured(self):
        gpio = FakeGPIOInputs(gas_level=True)
        config = RaspberryConfig(
            use_mock_hardware=False,
            mq2_active_low=False,
        )
        with patch("raspberry_pi.sensors.adafruit_dht", None):
            monitor = EnvironmentMonitor(config, gpio_controller=gpio)

        self.assertTrue(monitor.read().gas_detected)

    def test_emergency_button_state_is_read_from_gpio_controller(self):
        gpio = FakeGPIOInputs(button_pressed=True)
        with patch("raspberry_pi.sensors.adafruit_dht", None):
            monitor = EnvironmentMonitor(
                RaspberryConfig(use_mock_hardware=False),
                gpio_controller=gpio,
            )

        reading = monitor.read()

        self.assertTrue(reading.emergency_button_pressed)

    def test_mock_mode_keeps_simulated_readings(self):
        monitor = EnvironmentMonitor(RaspberryConfig(use_mock_hardware=True))

        reading = monitor.read()

        self.assertIsInstance(reading.temperature_c, float)
        self.assertIsInstance(reading.humidity_pct, float)
        self.assertIsInstance(reading.gas_ppm, float)
        self.assertIsInstance(reading.smoke_detected, bool)
        self.assertIsInstance(reading.gas_detected, bool)
        self.assertFalse(reading.emergency_button_pressed)
        self.assertFalse(reading.reset_button_pressed)


if __name__ == "__main__":
    unittest.main()
