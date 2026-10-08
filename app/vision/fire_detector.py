from __future__ import annotations

from typing import Dict, List


class FireDetector:
    """Avalia riscos visuais de fumaça e incêndio baseados em scores de detecção."""

    def __init__(self, smoke_threshold: float = 0.45, fire_threshold: float = 0.35):
        self.smoke_threshold = smoke_threshold
        self.fire_threshold = fire_threshold

    def classify(self, scores: Dict[str, float]) -> Dict[str, object]:
        smoke_score = float(scores.get("smoke", 0.0) or 0.0)
        fire_score = float(scores.get("fire", 0.0) or 0.0)

        reasons: List[str] = []
        if smoke_score >= self.smoke_threshold:
            reasons.append("fumaça")
        if fire_score >= self.fire_threshold:
            reasons.append("incêndio")

        if reasons:
            risk = "EMERGENCY"
        else:
            risk = "NORMAL"
            reasons = []

        return {
            "risk": risk,
            "reasons": reasons,
            "smoke_score": smoke_score,
            "fire_score": fire_score,
        }
