import os
import tempfile
import unittest

from central.events import EventStore, SystemEvent


class EventStoreTests(unittest.TestCase):
    def test_log_event_and_list_recent_events(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        try:
            store = EventStore(db_path=path)
            store.log_event(
                event_type="SENSOR",
                description="Temperatura elevada",
                state="ALERT",
                details={"temperature_c": 31.5},
            )

            events = store.get_recent_events(limit=10)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["event_type"], "SENSOR")
            self.assertEqual(events[0]["state"], "ALERT")
            self.assertEqual(events[0]["description"], "Temperatura elevada")
        finally:
            os.remove(path)

    def test_system_event_dataclass_from_payload(self):
        event = SystemEvent.from_payload({
            "state": "EMERGENCY",
            "temperature_c": 33.2,
            "humidity_pct": 80.0,
            "gas_ppm": 1.1,
            "smoke_detected": True,
        })

        self.assertEqual(event.event_type, "SENSOR")
        self.assertEqual(event.state, "EMERGENCY")
        self.assertTrue(event.details["smoke_detected"])

    def test_vision_emergency_has_specific_event_description(self):
        event = SystemEvent.from_payload(
            {
                "state": "EMERGENCY",
                "vision": {"lab": {"risk": "EMERGENCY"}},
            }
        )

        self.assertEqual(event.event_type, "VISION")
        self.assertEqual(event.description, "Fumaça ou incêndio detectado pela câmera")

    def test_missing_ppe_has_specific_event_description(self):
        event = SystemEvent.from_payload(
            {
                "state": "ALERT",
                "vision": {"access": {"status": "ALERTA"}},
            }
        )

        self.assertEqual(event.event_type, "EPI")
        self.assertEqual(event.description, "EPI inadequado detectado na entrada")

    def test_safety_and_access_models_use_shared_camera_event_keys(self):
        safety_event = SystemEvent.from_payload(
            {
                "state": "EMERGENCY",
                "vision": {"safety": {"risk": "EMERGENCY"}},
            }
        )
        access_event = SystemEvent.from_payload(
            {
                "state": "ALERT",
                "vision": {"access": {"status": "ALERTA"}},
            }
        )

        self.assertEqual(safety_event.event_type, "VISION")
        self.assertEqual(access_event.event_type, "EPI")


if __name__ == "__main__":
    unittest.main()
