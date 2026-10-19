"""One-way analysis computes changes from the current supplied base case."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def analyzer():
    path = (
        Path(__file__).resolve().parents[1]
        / "skills/custom_skills/creating-financial-models/sensitivity_analysis.py"
    )
    spec = importlib.util.spec_from_file_location("sensitivity_analysis", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Model:
        revenue = 1000
        offset = 0

        def output(self):
            return 2 * self.revenue - self.offset

    return module.SensitivityAnalyzer(Model())


def run_analysis(analyzer):
    model = analyzer.base_model
    return analyzer.one_way_sensitivity(
        "Revenue", 1000, 0.2, 3, model.output, lambda value: setattr(model, "revenue", value)
    )


def test_fresh_analysis_reports_output_changes(analyzer):
    result = run_analysis(analyzer)
    assert result["output"].tolist() == [1600, 2000, 2400]
    assert result["output_change"].tolist() == [-400, 0, 400]
    assert analyzer.base_model.revenue == 1000


def test_zero_baseline_is_not_treated_as_missing(analyzer):
    analyzer.base_model.offset = 2000
    result = run_analysis(analyzer)
    assert result["output_change"].tolist() == [-400, 0, 400]
    assert analyzer.base_output == 0


def test_each_analysis_refreshes_baseline_at_supplied_base_value(analyzer):
    run_analysis(analyzer)
    analyzer.base_output = -100  # A previous analysis must not supply this run's baseline.
    analyzer.base_model.revenue = 1200
    analyzer.base_model.offset = 500

    result = run_analysis(analyzer)

    assert result["output_change"].tolist() == [-400, 0, 400]
    assert analyzer.base_output == 1500
    assert analyzer.base_model.revenue == 1000
