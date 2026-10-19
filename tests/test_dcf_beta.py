"""Known linear return series have exact beta coefficients."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def calculate_beta():
    path = (
        Path(__file__).resolve().parents[1]
        / "skills/custom_skills/creating-financial-models/dcf_model.py"
    )
    spec = importlib.util.spec_from_file_location("dcf_model", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.calculate_beta


@pytest.mark.parametrize("scale", [1.0, 2.0, -0.5])
@pytest.mark.parametrize("market", [[-0.03, 0.02], [-0.03, 0.02, 0.01, 0.04, -0.02]])
def test_linear_returns_have_expected_beta(calculate_beta, market, scale):
    stock = [scale * value + 0.01 for value in market]
    assert calculate_beta(stock, market) == pytest.approx(scale)


@pytest.mark.parametrize(
    ("stock", "market"), [([0.01, 0.03, 0.05], [0.02, 0.02, 0.02]), ([0.01], [0.02])]
)
def test_zero_market_variance_retains_fallback(calculate_beta, stock, market):
    assert calculate_beta(stock, market) == 1.0
