from __future__ import annotations

from typing import Dict, List


class PPEEvaluator:
    """Avalia se a pessoa atende aos requisitos mínimos de segurança."""

    REQUIRED_EQUIPMENT = {
        "lab_coat": "Jaleco ausente",
        "safety_glasses": "Óculos ausentes",
        "closed_shoes": "Calçado inadequado",
        "tied_hair": "Cabelo não preso",
    }

    def evaluate(self, detections: Dict[str, bool]) -> Dict[str, object]:
        reasons: List[str] = []

        for key, message in self.REQUIRED_EQUIPMENT.items():
            present = bool(detections.get(key, False))
            if not present:
                reasons.append(message)

        status = "PERMITIDO" if not reasons else "ALERTA"

        return {
            "status": status,
            "reasons": reasons,
            "detections": detections,
        }
