from __future__ import annotations

from typing import Dict, List


class PPEEvaluator:
    """Avalia se a pessoa atende aos requisitos mínimos de segurança."""

    REQUIRED_EQUIPMENT = {
        "lab_coat": "Jaleco ausente",
        "trousers": "Calça ausente",
        "closed_shoes": "Calçado fechado ausente",
    }

    def __init__(self, required_equipment=None, require_tied_hair=True):
        self.required_equipment = (
            self.REQUIRED_EQUIPMENT
            if required_equipment is None
            else required_equipment
        )
        self.require_tied_hair = require_tied_hair

    def evaluate(self, detections: Dict[str, bool]) -> Dict[str, object]:
        reasons: List[str] = []

        for key, message in self.required_equipment.items():
            present = bool(detections.get(key, False))
            if not present:
                reasons.append(message)

        if (
            self.require_tied_hair
            and detections.get("long_hair", False)
            and not detections.get("tied_hair", False)
        ):
            reasons.append("Cabelo comprido não está amarrado")

        status = "PERMITIDO" if not reasons else "ALERTA"

        return {
            "status": status,
            "reasons": reasons,
            "detections": detections,
        }
