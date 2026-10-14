"""Cash flow projections must start from the latest historical working capital."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def model():
    path = (
        Path(__file__).resolve().parents[1]
        / "skills/custom_skills/creating-financial-models/dcf_model.py"
    )
    spec = importlib.util.spec_from_file_location("dcf_model", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    model = module.DCFModel("Synthetic Company")
    model.set_assumptions(projection_years=2)
    model.calculate_wacc(0.03, 1, 0.07, 0.05, 0)
    return model


@pytest.mark.parametrize("latest_nwc", [200, 0, 100])
def test_cash_flows_use_latest_historical_working_capital(model, latest_nwc):
    model.set_historical_financials(
        revenue=[800, 1000],
        ebitda=[160, 200],
        capex=[40, 50],
        nwc=[80, latest_nwc],
        years=[2023, 2024],
    )

    projections = model.project_cash_flows()

    # Year-one revenue is 1100, NWC is 110, and NOPAT is 123.75.
    assert projections["nwc_change"] == pytest.approx([110 - latest_nwc, 11])
    assert projections["fcf"] == pytest.approx([123.75 - (110 - latest_nwc), 125.125])

    valuation = model.calculate_enterprise_value()
    assert valuation["pv_fcf"] == pytest.approx(
        (123.75 - (110 - latest_nwc)) / 1.1 + 125.125 / 1.1**2
    )


def test_cash_flows_keep_default_working_capital_without_history(model):
    projections = model.project_cash_flows()

    assert projections["nwc_change"] == pytest.approx([10, 11])
    assert projections["fcf"] == pytest.approx([113.75, 125.125])
