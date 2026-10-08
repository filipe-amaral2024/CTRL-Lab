from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

try:
    from ultralytics import YOLO
except ImportError:  # pragma: no cover - depende do ambiente
    YOLO = None


@dataclass
class DetectionResult:
    class_name: str
    confidence: float
    x1: Optional[int] = None
    y1: Optional[int] = None
    x2: Optional[int] = None
    y2: Optional[int] = None


class YOLODetector:
    """Wrapper simples para inferência com YOLOv8."""

    def __init__(self, model_name: str = "yolov8n.pt", threshold: float = 0.25):
        self.model_name = model_name
        self.threshold = threshold
        self.model = None

        if YOLO is not None:
            self.model = YOLO(model_name)

    def is_available(self) -> bool:
        return self.model is not None

    def predict(self, image):
        if self.model is None:
            raise RuntimeError("YOLO não está disponível. Instale ultralytics para executar a inferência.")

        results = self.model(image, conf=self.threshold, verbose=False)
        detections: List[DetectionResult] = []

        for result in results:
            boxes = result.boxes
            for box in boxes:
                cls_id = int(box.cls[0])
                name = result.names.get(cls_id, "unknown")
                conf = float(box.conf[0])

                if conf < self.threshold:
                    continue

                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                detections.append(
                    DetectionResult(
                        class_name=name,
                        confidence=conf,
                        x1=x1,
                        y1=y1,
                        x2=x2,
                        y2=y2,
                    )
                )

        return detections
