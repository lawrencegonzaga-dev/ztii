import unittest

from backend.services.ai_engine import analyze_device


class AiEngineTests(unittest.TestCase):
    def test_normal_condition(self):
        result = analyze_device(40, 0.3)
        self.assertEqual(result["health"], "Normal")
        self.assertIn("Low", result["risk"])

    def test_warning_condition(self):
        result = analyze_device(58, 0.8)
        self.assertEqual(result["health"], "Warning")
        self.assertIn("Medium", result["risk"])

    def test_critical_condition(self):
        result = analyze_device(68, 1.7)
        self.assertEqual(result["health"], "Critical")
        self.assertIn("High", result["risk"])

    def test_numeric_strings_are_supported(self):
        result = analyze_device("42.5", "0.4")
        self.assertEqual(result["health"], "Normal")


if __name__ == "__main__":
    unittest.main()
