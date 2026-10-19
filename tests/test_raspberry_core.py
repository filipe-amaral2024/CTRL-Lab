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


if __name__ == "__main__":
    unittest.main()
