import unittest
from unittest.mock import Mock

from raspberry_pi.config import RaspberryConfig
from raspberry_pi.mqtt_client import MQTTClientWrapper


class MQTTClientWrapperTests(unittest.TestCase):
    def test_publish_sends_status_with_requested_qos(self):
        wrapper = MQTTClientWrapper(RaspberryConfig(use_mock_hardware=True))
        wrapper._client = Mock()

        result = wrapper.publish("ctrlab/raspberry/status", '{"state":"NORMAL"}')

        wrapper._client.publish.assert_called_once_with(
            "ctrlab/raspberry/status",
            '{"state":"NORMAL"}',
            qos=1,
        )
        self.assertEqual(result, wrapper._client.publish.return_value)


if __name__ == "__main__":
    unittest.main()
