import json
import unittest

from raspberry_pi.alerts import AlertManager, SystemState
from raspberry_pi.config import RaspberryConfig
from raspberry_pi.sensors import EnvironmentReading


class DummyMQTT:
    def __init__(self):
        self.messages = []

    def publish(self, topic, payload, qos=1):
        self.messages.append({"topic": topic, "payload": payload, "qos": qos})


class AlertManagerTests(unittest.TestCase):
    def setUp(self):
        self.config = RaspberryConfig(use_mock_hardware=True)

    def test_emergency_when_smoke_detected(self):
        reading = EnvironmentReading(
            temperature_c=24.0,
            humidity_pct=50.0,
            gas_ppm=0.9,
            smoke_detected=True,
        )

        manager = AlertManager(self.config)
        state = manager.evaluate(reading)

        self.assertEqual(state, SystemState.EMERGENCY)

    def test_emergency_when_digital_gas_sensor_triggers(self):
        reading = EnvironmentReading(
            temperature_c=None,
            humidity_pct=None,
            gas_ppm=None,
            smoke_detected=None,
            gas_detected=True,
        )

        manager = AlertManager(self.config)

        self.assertEqual(manager.evaluate(reading), SystemState.EMERGENCY)

    def test_emergency_while_button_is_pressed(self):
        reading = EnvironmentReading(
            temperature_c=None,
            humidity_pct=None,
            gas_ppm=None,
            smoke_detected=None,
            emergency_button_pressed=True,
        )

        manager = AlertManager(self.config)

        self.assertEqual(manager.evaluate(reading), SystemState.EMERGENCY)

    def test_button_emergency_stays_latched_until_safe_reset(self):
        manager = AlertManager(self.config)
        pressed = EnvironmentReading(
            temperature_c=24.0,
            humidity_pct=50.0,
            gas_ppm=None,
            smoke_detected=None,
            emergency_button_pressed=True,
        )
        released = EnvironmentReading(
            temperature_c=24.0,
            humidity_pct=50.0,
            gas_ppm=None,
            smoke_detected=None,
            emergency_button_pressed=False,
        )
        reset = EnvironmentReading(
            temperature_c=24.0,
            humidity_pct=50.0,
            gas_ppm=None,
            smoke_detected=None,
            emergency_button_pressed=False,
            reset_button_pressed=True,
        )

        self.assertEqual(manager.update(pressed), SystemState.EMERGENCY)
        self.assertEqual(manager.update(released), SystemState.EMERGENCY)
        self.assertEqual(manager.update(reset), SystemState.NORMAL)

    def test_reset_does_not_clear_active_critical_risk(self):
        manager = AlertManager(self.config)
        manager.update(
            EnvironmentReading(
                temperature_c=None,
                humidity_pct=None,
                gas_ppm=None,
                smoke_detected=None,
                emergency_button_pressed=True,
            )
        )
        reset_with_gas = EnvironmentReading(
            temperature_c=None,
            humidity_pct=None,
            gas_ppm=None,
            smoke_detected=None,
            gas_detected=True,
            emergency_button_pressed=False,
            reset_button_pressed=True,
        )

        self.assertEqual(manager.update(reset_with_gas), SystemState.EMERGENCY)

    def test_reset_does_not_clear_mechanically_latched_emergency_button(self):
        manager = AlertManager(self.config)
        emergency_still_latched = EnvironmentReading(
            temperature_c=None,
            humidity_pct=None,
            gas_ppm=None,
            smoke_detected=None,
            emergency_button_pressed=True,
            reset_button_pressed=True,
        )

        self.assertEqual(
            manager.update(emergency_still_latched),
            SystemState.EMERGENCY,
        )

    def test_warning_state_for_high_gas(self):
        reading = EnvironmentReading(
            temperature_c=25.0,
            humidity_pct=50.0,
            gas_ppm=0.45,
            smoke_detected=False,
        )

        manager = AlertManager(self.config)
        state = manager.evaluate(reading)

        self.assertEqual(state, SystemState.WARNING)

    def test_status_payload_published(self):
        reading = EnvironmentReading(
            temperature_c=31.0,
            humidity_pct=68.0,
            gas_ppm=0.35,
            smoke_detected=False,
        )

        mqtt = DummyMQTT()
        manager = AlertManager(self.config, mqtt_client=mqtt)
        state = manager.update(reading)

        self.assertEqual(state, SystemState.ALERT)
        self.assertEqual(len(mqtt.messages), 1)
        payload = json.loads(mqtt.messages[0]["payload"])
        self.assertEqual(payload["state"], "ALERT")
        self.assertEqual(payload["temperature_c"], 31.0)

    def test_visual_emergency_overrides_normal_sensor_state(self):
        reading = EnvironmentReading(
            temperature_c=24.0,
            humidity_pct=50.0,
            gas_ppm=0.1,
            smoke_detected=False,
        )
        mqtt = DummyMQTT()
        manager = AlertManager(self.config, mqtt_client=mqtt)
        vision = {"lab": {"risk": "EMERGENCY"}}

        state = manager.update(
            reading,
            vision_state=SystemState.EMERGENCY,
            vision_details=vision,
        )

        self.assertEqual(state, SystemState.EMERGENCY)
        payload = json.loads(mqtt.messages[0]["payload"])
        self.assertEqual(payload["vision"], vision)

    def test_unavailable_sensor_values_do_not_trigger_alerts(self):
        reading = EnvironmentReading(
            temperature_c=None,
            humidity_pct=None,
            gas_ppm=None,
            smoke_detected=None,
        )

        manager = AlertManager(self.config)

        self.assertEqual(manager.evaluate(reading), SystemState.NORMAL)

    def test_unavailable_sensor_values_are_published_as_null(self):
        reading = EnvironmentReading(
            temperature_c=None,
            humidity_pct=None,
            gas_ppm=None,
            smoke_detected=None,
        )
        mqtt = DummyMQTT()
        manager = AlertManager(self.config, mqtt_client=mqtt)

        manager.update(reading)

        payload = json.loads(mqtt.messages[0]["payload"])
        self.assertIsNone(payload["temperature_c"])
        self.assertIsNone(payload["humidity_pct"])
        self.assertIsNone(payload["gas_ppm"])
        self.assertIsNone(payload["smoke_detected"])
        self.assertIsNone(payload["gas_detected"])
        self.assertIsNone(payload["emergency_button_pressed"])


if __name__ == "__main__":
    unittest.main()
