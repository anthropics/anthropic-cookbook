"""Unit tests for SensitivityAnalyzer in creating-financial-models skill."""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

# Add skill directory to sys.path
SKILL_DIR = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "custom_skills"
    / "creating-financial-models"
)
sys.path.insert(0, str(SKILL_DIR))

from sensitivity_analysis import SensitivityAnalyzer  # noqa: E402


class TestSensitivityAnalyzer(unittest.TestCase):
    """Test suite for SensitivityAnalyzer."""

    def test_tornado_analysis_zero_baseline(self):
        """Zero baseline output should not raise ZeroDivisionError and should return NaN for impact_pct."""
        model = {"value": 0.0}
        analyzer = SensitivityAnalyzer(model)

        variables = {
            "value": {
                "base": 0.0,
                "low": -10.0,
                "high": 10.0,
                "update_func": lambda v: model.update(value=v),
            }
        }

        df = analyzer.tornado_analysis(variables, lambda: model["value"])

        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertEqual(row["variable"], "value")
        self.assertEqual(row["low_output"], -10.0)
        self.assertEqual(row["high_output"], 10.0)
        self.assertEqual(row["impact"], 20.0)
        self.assertTrue(np.isnan(row["impact_pct"]))
        # Verify model was restored to base value
        self.assertEqual(model["value"], 0.0)

    def test_tornado_analysis_nonzero_baseline(self):
        """Non-zero baseline output calculates impact_pct as percentage of base output."""
        model = {"value": 100.0}
        analyzer = SensitivityAnalyzer(model)

        variables = {
            "value": {
                "base": 100.0,
                "low": 90.0,
                "high": 110.0,
                "update_func": lambda v: model.update(value=v),
            }
        }

        df = analyzer.tornado_analysis(variables, lambda: model["value"])

        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertEqual(row["variable"], "value")
        self.assertEqual(row["impact"], 20.0)
        # 20 / 100 * 100 = 20.0%
        self.assertAlmostEqual(row["impact_pct"], 20.0)
        self.assertEqual(model["value"], 100.0)

    def test_tornado_analysis_multiple_variables_sorting(self):
        """Tornado table sorts variables by impact in descending order."""
        model = {"var_a": 0.0, "var_b": 0.0}
        analyzer = SensitivityAnalyzer(model)

        variables = {
            "small_impact": {
                "base": 0.0,
                "low": -2.0,
                "high": 2.0,
                "update_func": lambda v: model.update(var_a=v),
            },
            "large_impact": {
                "base": 0.0,
                "low": -50.0,
                "high": 50.0,
                "update_func": lambda v: model.update(var_b=v),
            },
        }

        def calculate():
            return model["var_a"] + model["var_b"]

        df = analyzer.tornado_analysis(variables, calculate)

        self.assertEqual(len(df), 2)
        # Should be sorted descending by impact
        self.assertEqual(df.iloc[0]["variable"], "large_impact")
        self.assertEqual(df.iloc[0]["impact"], 100.0)
        self.assertTrue(np.isnan(df.iloc[0]["impact_pct"]))

        self.assertEqual(df.iloc[1]["variable"], "small_impact")
        self.assertEqual(df.iloc[1]["impact"], 4.0)
        self.assertTrue(np.isnan(df.iloc[1]["impact_pct"]))


if __name__ == "__main__":
    unittest.main()
