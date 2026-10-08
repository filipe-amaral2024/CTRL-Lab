import unittest

from app.vision.yolo_base import DetectionResult, YOLODetector


class YOLODetectorTests(unittest.TestCase):
    def test_detection_result_format(self):
        result = DetectionResult(class_name="person", confidence=0.92)
        self.assertEqual(result.class_name, "person")
        self.assertEqual(result.confidence, 0.92)

    def test_detector_accepts_model_name(self):
        detector = YOLODetector(model_name="yolov8n.pt")
        self.assertEqual(detector.model_name, "yolov8n.pt")
        self.assertEqual(detector.threshold, 0.25)


if __name__ == "__main__":
    unittest.main()
