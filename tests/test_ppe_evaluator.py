import unittest

from app.safety.ppe_evaluator import PPEEvaluator


class PPEEvaluatorTests(unittest.TestCase):
    def test_allow_access_when_required_gear_present(self):
        evaluator = PPEEvaluator()
        detections = {
            "person": True,
            "lab_coat": True,
            "trousers": True,
            "closed_shoes": True,
            "long_hair": True,
            "tied_hair": True,
        }

        result = evaluator.evaluate(detections)
        self.assertEqual(result["status"], "PERMITIDO")
        self.assertEqual(result["reasons"], [])

    def test_block_access_when_closed_shoes_missing(self):
        evaluator = PPEEvaluator()
        detections = {
            "person": True,
            "lab_coat": True,
            "trousers": True,
            "closed_shoes": False,
            "tied_hair": True,
        }

        result = evaluator.evaluate(detections)
        self.assertEqual(result["status"], "ALERTA")
        self.assertIn("Calçado fechado ausente", result["reasons"])

    def test_mark_missing_lab_coat_as_reason(self):
        evaluator = PPEEvaluator()
        detections = {
            "person": True,
            "lab_coat": False,
            "trousers": True,
            "closed_shoes": True,
            "tied_hair": True,
        }

        result = evaluator.evaluate(detections)
        self.assertEqual(result["status"], "ALERTA")
        self.assertIn("Jaleco ausente", result["reasons"])

    def test_trousers_are_required(self):
        result = PPEEvaluator().evaluate(
            {
                "person": True,
                "lab_coat": True,
                "trousers": False,
                "closed_shoes": True,
            }
        )

        self.assertEqual(result["status"], "ALERTA")
        self.assertIn("Calça ausente", result["reasons"])

    def test_glasses_are_not_required(self):
        result = PPEEvaluator().evaluate(
            {
                "person": True,
                "lab_coat": True,
                "trousers": True,
                "closed_shoes": True,
            }
        )

        self.assertEqual(result["status"], "PERMITIDO")
        self.assertEqual(result["reasons"], [])

    def test_long_hair_must_be_tied(self):
        result = PPEEvaluator().evaluate(
            {
                "person": True,
                "lab_coat": True,
                "trousers": True,
                "closed_shoes": True,
                "long_hair": True,
                "tied_hair": False,
            }
        )

        self.assertEqual(result["status"], "ALERTA")
        self.assertIn("Cabelo comprido não está amarrado", result["reasons"])

    def test_short_or_undetected_hair_does_not_require_tying(self):
        result = PPEEvaluator().evaluate(
            {
                "person": True,
                "lab_coat": True,
                "trousers": True,
                "closed_shoes": True,
                "long_hair": False,
                "tied_hair": False,
            }
        )

        self.assertEqual(result["status"], "PERMITIDO")


if __name__ == "__main__":
    unittest.main()
