import json
import unittest

from central.mqtt_listener import CentralMQTTListener


class DummyMQTTClient:
    def __init__(self, result_code=0):
        self.result_code = result_code
        self.messages = []

    def publish(self, topic, payload, qos):
        self.messages.append((topic, payload, qos))
        return type("PublishResult", (), {"rc": self.result_code})()


class CentralMQTTCommandTests(unittest.TestCase):
    def test_publishes_access_model_command(self):
        listener = object.__new__(CentralMQTTListener)
        listener.command_topic = "ctrlab/central/commands"
        listener._client = DummyMQTTClient()
        listener._connected = True

        result = listener.set_access_model_enabled(True)

        self.assertTrue(result)
        topic, payload, qos = listener._client.messages[0]
        self.assertEqual(topic, "ctrlab/central/commands")
        self.assertEqual(
            json.loads(payload),
            {"command": "set_access_model", "enabled": True},
        )
        self.assertEqual(qos, 1)

    def test_rejects_non_boolean_access_model_state(self):
        listener = object.__new__(CentralMQTTListener)
        listener._client = DummyMQTTClient()
        listener._connected = True

        with self.assertRaisesRegex(ValueError, "deve ser booleano"):
            listener.set_access_model_enabled("true")

    def test_returns_false_when_mqtt_client_is_unavailable(self):
        listener = object.__new__(CentralMQTTListener)
        listener._client = None

        self.assertFalse(listener.set_access_model_enabled(False))

    def test_returns_false_when_broker_rejects_command(self):
        listener = object.__new__(CentralMQTTListener)
        listener.command_topic = "ctrlab/central/commands"
        listener._client = DummyMQTTClient(result_code=4)
        listener._connected = True

        self.assertFalse(listener.set_access_model_enabled(True))


if __name__ == "__main__":
    unittest.main()
