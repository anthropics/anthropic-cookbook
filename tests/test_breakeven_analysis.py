"""Offline regression tests for the financial-model breakeven solver."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills/custom_skills/creating-financial-models/sensitivity_analysis.py"
)
spec = importlib.util.spec_from_file_location("sensitivity_analysis", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SensitivityAnalyzer = module.SensitivityAnalyzer


@pytest.mark.parametrize(
    "output, bounds, target, expected",
    [
        pytest.param(lambda x: 100 - 10 * x, (0, 10), 40, 6, id="decreasing-profit"),
        pytest.param(lambda x: 100 - x**2, (0, 10), 64, 6, id="decreasing-quadratic"),
        pytest.param(lambda x: 100 / x, (1, 10), 20, 5, id="decreasing-reciprocal"),
        pytest.param(lambda x: 100 / (1 + x) ** 2, (0, 3), 25, 1, id="discount-rate"),
        pytest.param(lambda x: 2 - 3 * x, (-10, 0), 11, -3, id="negative-input"),
        pytest.param(lambda x: -10 * x, (0, 10), -60, 6, id="negative-output"),
        pytest.param(lambda x: 10 * x - 20, (0, 10), 40, 6, id="increasing-linear"),
        pytest.param(lambda x: x**2, (0, 10), 36, 6, id="increasing-quadratic"),
        pytest.param(lambda x: 2 * x, (-10, 0), -6, -3, id="increasing-negative"),
        pytest.param(lambda x: 10 - x, (0, 10), 5, 5, id="exact-midpoint"),
    ],
)
def test_breakeven_monotonic_outputs(output, bounds, target, expected):
    model = SimpleNamespace(value=0.0)
    analyzer = SensitivityAnalyzer(model)

    result = analyzer.breakeven_analysis(
        "value",
        lambda value: setattr(model, "value", value),
        lambda: output(model.value),
        target,
        *bounds,
        tolerance=1e-8,
    )

    # Expected roots come from the formulas above, not another numerical solver.
    assert result == pytest.approx(expected, abs=1e-6)
    assert output(result) == pytest.approx(target, abs=1e-6)


@pytest.mark.parametrize("bounds", [(1.0, 1.005), (1.0, 1.0)])
def test_breakeven_without_iteration_does_not_call_model(bounds):
    update = Mock()
    output = Mock()

    result = SensitivityAnalyzer(object()).breakeven_analysis("value", update, output, 0, *bounds)

    assert result == sum(bounds) / 2
    update.assert_not_called()
    output.assert_not_called()


@pytest.mark.parametrize("failing_callback", ["update", "output"])
def test_breakeven_propagates_model_errors(failing_callback):
    error = RuntimeError("model calculation failed")
    update = Mock(side_effect=error if failing_callback == "update" else None)
    output = Mock(side_effect=error if failing_callback == "output" else None)

    with pytest.raises(RuntimeError, match="model calculation failed") as caught:
        SensitivityAnalyzer(object()).breakeven_analysis("value", update, output, 40, 0, 10)

    assert caught.value is error
