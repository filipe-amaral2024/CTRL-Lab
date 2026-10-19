"""Módulos de visão computacional do projeto CTRL-Lab."""

from .yolo_base import DetectionResult, YOLODetector
from .yolo_onnx import OpenCVDNNYOLODetector

__all__ = ["DetectionResult", "YOLODetector", "OpenCVDNNYOLODetector"]
