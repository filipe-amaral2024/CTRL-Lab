import unittest

from app.safety.ppe_evaluator import PPEEvaluator


class PPEEvaluatorTests(unittest.TestCase):
    def test_allow_access_when_required_gear_present(self):
        evaluator = PPEEvaluator()
        detections = {
            "person": True,
            "lab_coat": True,
            "safety_glasses": True,
            "closed_shoes": True,
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
            "safety_glasses": True,
            "closed_shoes": False,
            "tied_hair": True,
        }

        result = evaluator.evaluate(detections)
        self.assertEqual(result["status"], "ALERTA")
        self.assertIn("Calçado inadequado", result["reasons"])

    def test_mark_missing_lab_coat_as_reason(self):
        evaluator = PPEEvaluator()
        detections = {
            "person": True,
            "lab_coat": False,
            "safety_glasses": True,
            "closed_shoes": True,
            "tied_hair": True,
        }

        result = evaluator.evaluate(detections)
        self.assertEqual(result["status"], "ALERTA")
        self.assertIn("Jaleco ausente", result["reasons"])


if __name__ == "__main__":
    unittest.main()
