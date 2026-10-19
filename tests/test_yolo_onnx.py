import tempfile
import unittest
from unittest.mock import patch

from app.vision.yolo_onnx import OpenCVDNNYOLODetector


class FakeTensor:
    def __init__(self, values):
        self.values = values
        self.shape = self._shape(values)

    def __getitem__(self, index):
        value = self.values[index]
        return FakeTensor(value) if isinstance(value, list) else value

    @staticmethod
    def _shape(values):
        shape = []
        while isinstance(values, list):
            shape.append(len(values))
            values = values[0] if values else []
        return tuple(shape)


class FakeNetwork:
    def __init__(self):
        self.output = FakeTensor(
            [[
                [160.0, 170.0],
                [160.0, 170.0],
                [80.0, 40.0],
                [100.0, 60.0],
                [0.9, 0.1],
                [0.1, 0.8],
                [0.0, 0.1],
            ]]
        )

    def setPreferableBackend(self, backend):
        self.backend = backend

    def setPreferableTarget(self, target):
        self.target = target

    def setInput(self, blob):
        self.blob = blob

    def forward(self):
        return self.output


class FakeDNN:
    DNN_BACKEND_OPENCV = 0
    DNN_TARGET_CPU = 0

    def __init__(self):
        self.network = FakeNetwork()

    def readNetFromONNX(self, model_path):
        return self.network

    @staticmethod
    def blobFromImage(image, **kwargs):
        return image

    @staticmethod
    def NMSBoxes(boxes, scores, threshold, nms_threshold):
        return list(range(len(boxes)))


class FakeOpenCV:
    BORDER_CONSTANT = 0

    def __init__(self):
        self.dnn = FakeDNN()

    @staticmethod
    def resize(image, size):
        return image

    @staticmethod
    def copyMakeBorder(image, *args, **kwargs):
        return image


class OpenCVDNNYOLODetectorTests(unittest.TestCase):
    def test_predict_decodes_yolov8_onnx_detections_on_cpu(self):
        with tempfile.NamedTemporaryFile(suffix=".onnx") as model_file:
            fake_cv2 = FakeOpenCV()
            with patch("app.vision.yolo_onnx.cv2", fake_cv2):
                detector = OpenCVDNNYOLODetector(
                    model_file.name,
                    class_names=("person", "smoke", "fire"),
                    input_size=320,
                )
                image = type("FakeImage", (), {"shape": (320, 640, 3), "ndim": 3})()

                detections = detector.predict(image)

        self.assertEqual(
            [detection.class_name for detection in detections],
            ["person", "smoke"],
        )
        self.assertEqual(
            (detections[0].x1, detections[0].y1, detections[0].x2, detections[0].y2),
            (240, 60, 400, 260),
        )
        self.assertEqual(fake_cv2.dnn.network.target, fake_cv2.dnn.DNN_TARGET_CPU)

    def test_rejects_class_count_that_does_not_match_model_output(self):
        with tempfile.NamedTemporaryFile(suffix=".onnx") as model_file:
            fake_cv2 = FakeOpenCV()
            with patch("app.vision.yolo_onnx.cv2", fake_cv2):
                detector = OpenCVDNNYOLODetector(
                    model_file.name,
                    class_names=("person",),
                )

                with self.assertRaisesRegex(RuntimeError, "não corresponde"):
                    detector.predict(
                        type("FakeImage", (), {"shape": (320, 320, 3), "ndim": 3})()
                    )


if __name__ == "__main__":
    unittest.main()
