from __future__ import annotations

from pathlib import Path
from typing import List, Sequence

try:
    import cv2
except ImportError:  # pragma: no cover - depende do ambiente
    cv2 = None

from .yolo_base import DetectionResult


class OpenCVDNNYOLODetector:
    """Executa modelos YOLOv8 ONNX com o backend CPU do OpenCV."""

    def __init__(
        self,
        model_path: str,
        class_names: Sequence[str],
        threshold: float = 0.25,
        input_size: int = 320,
        nms_threshold: float = 0.45,
    ):
        if cv2 is None:
            raise RuntimeError("OpenCV não está instalado para executar o modelo ONNX.")
        if not Path(model_path).is_file():
            raise FileNotFoundError(f"Modelo ONNX não encontrado: {model_path}")
        if not class_names:
            raise ValueError("Informe os nomes das classes do modelo na ordem usada no treinamento.")
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("O limiar de confiança deve estar entre 0 e 1.")
        if input_size <= 0:
            raise ValueError("O tamanho da imagem de entrada deve ser positivo.")

        self.model_path = model_path
        self.class_names = tuple(name.strip() for name in class_names)
        if any(not name for name in self.class_names):
            raise ValueError("Os nomes das classes não podem estar vazios.")
        self.threshold = threshold
        self.input_size = input_size
        self.nms_threshold = nms_threshold
        self.net = cv2.dnn.readNetFromONNX(model_path)
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

    def predict(self, image) -> List[DetectionResult]:
        if image is None or image.ndim < 2:
            raise ValueError("A imagem de entrada está vazia ou inválida.")

        height, width = image.shape[:2]
        scale = min(self.input_size / width, self.input_size / height)
        resized_width = round(width * scale)
        resized_height = round(height * scale)
        pad_x = (self.input_size - resized_width) // 2
        pad_y = (self.input_size - resized_height) // 2
        resized = cv2.resize(image, (resized_width, resized_height))
        letterboxed = cv2.copyMakeBorder(
            resized,
            pad_y,
            self.input_size - resized_height - pad_y,
            pad_x,
            self.input_size - resized_width - pad_x,
            cv2.BORDER_CONSTANT,
            value=(114, 114, 114),
        )
        blob = cv2.dnn.blobFromImage(
            letterboxed,
            scalefactor=1.0 / 255.0,
            size=(self.input_size, self.input_size),
            swapRB=True,
            crop=False,
        )
        self.net.setInput(blob)
        output = self.net.forward()
        shape = output.shape
        if len(shape) == 3 and shape[0] == 1:
            output = output[0]
            shape = output.shape

        expected_channels = 4 + len(self.class_names)
        if len(shape) != 2:
            raise RuntimeError(f"Formato de saída YOLOv8 ONNX não suportado: {shape}")
        if shape[0] == expected_channels:
            candidates = [
                [output[channel][candidate_index] for channel in range(expected_channels)]
                for candidate_index in range(shape[1])
            ]
        elif shape[1] == expected_channels:
            candidates = [
                [output[candidate_index][channel] for channel in range(expected_channels)]
                for candidate_index in range(shape[0])
            ]
        else:
            raise RuntimeError(
                "A saída ONNX não corresponde às classes informadas: "
                f"esperados {expected_channels} canais, recebido {shape}."
            )

        boxes = []
        scores = []
        class_ids = []
        for candidate in candidates:
            class_scores = candidate[4:]
            class_id = max(
                range(len(class_scores)),
                key=lambda index: float(class_scores[index]),
            )
            confidence = float(class_scores[class_id])
            if confidence < self.threshold:
                continue

            center_x, center_y, box_width, box_height = candidate[:4]
            x1 = int((center_x - box_width / 2 - pad_x) / scale)
            y1 = int((center_y - box_height / 2 - pad_y) / scale)
            x2 = int((center_x + box_width / 2 - pad_x) / scale)
            y2 = int((center_y + box_height / 2 - pad_y) / scale)
            left = max(0, min(width, x1))
            top = max(0, min(height, y1))
            right = max(0, min(width, x2))
            bottom = max(0, min(height, y2))
            if right <= left or bottom <= top:
                continue

            boxes.append([left, top, right - left, bottom - top])
            scores.append(confidence)
            class_ids.append(class_id)

        if not boxes:
            return []

        kept_indices = cv2.dnn.NMSBoxes(
            boxes,
            scores,
            self.threshold,
            self.nms_threshold,
        )
        detections = []
        for box_index in self._flatten_indices(kept_indices):
            left, top, box_width, box_height = boxes[box_index]
            class_id = class_ids[box_index]
            detections.append(
                DetectionResult(
                    class_name=self.class_names[class_id],
                    confidence=scores[box_index],
                    x1=left,
                    y1=top,
                    x2=left + box_width,
                    y2=top + box_height,
                )
            )
        return detections

    @classmethod
    def _flatten_indices(cls, indices):
        if indices is None:
            return []
        try:
            iterator = iter(indices)
        except TypeError:
            return [int(indices)]

        flattened = []
        for index in iterator:
            flattened.extend(cls._flatten_indices(index))
        return flattened
