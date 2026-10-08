import unittest

from app.vision.fire_detector import FireDetector


class FireDetectorTests(unittest.TestCase):
    def test_detector_initializes_with_default_thresholds(self):
        detector = FireDetector()
        self.assertEqual(detector.smoke_threshold, 0.45)
        self.assertEqual(detector.fire_threshold, 0.35)

    def test_detects_risk_from_alarm_signal(self):
        detector = FireDetector()
        result = detector.classify({"smoke": 0.8, "fire": 0.2})
        self.assertEqual(result["risk"], "EMERGENCY")
        self.assertIn("fumaça", result["reasons"]) 

    def test_detects_normal_when_no_risk(self):
        detector = FireDetector()
        result = detector.classify({"smoke": 0.1, "fire": 0.1})
        self.assertEqual(result["risk"], "NORMAL")
        self.assertEqual(result["reasons"], [])


if __name__ == "__main__":
    unittest.main()
