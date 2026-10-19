"""Sensitivity tables must not change the model's base-case results."""

import importlib.util
from copy import deepcopy
from pathlib import Path

import numpy as np
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
    model.project_cash_flows()
    model.calculate_enterprise_value()
    model.calculate_equity_value(100, shares_outstanding=10)
    return model


def test_sensitivity_preserves_base_case_and_equity_results(model):
    original = deepcopy(model.__dict__)
    original_summary = model.generate_summary()
    original_equity = model.calculate_equity_value(100, shares_outstanding=10)

    table = model.sensitivity_analysis("wacc", [0.08, 0.12], "margin", [0.20, 0.30])

    assert np.allclose(table, [[2422.45370370, 4179.39814815], [1342.88194444, 2316.84027778]])
    assert model.__dict__ == original
    assert model.generate_summary() == original_summary
    assert model.calculate_equity_value(100, shares_outstanding=10) == original_equity


def test_sensitivity_restores_state_after_failed_scenario(model, monkeypatch):
    original = deepcopy(model.__dict__)
    original_summary = model.generate_summary()
    calculate = model.calculate_enterprise_value
    calls = 0

    def fail_second_scenario():
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("scenario failed")
        return calculate()

    monkeypatch.setattr(model, "calculate_enterprise_value", fail_second_scenario)
    with pytest.raises(ValueError, match="scenario failed"):
        model.sensitivity_analysis("wacc", [0.08], "margin", [0.20, 0.30])
    monkeypatch.delattr(model, "calculate_enterprise_value")

    assert model.__dict__ == original
    assert model.generate_summary() == original_summary


def test_empty_sensitivity_table_keeps_existing_results(model):
    original = deepcopy(model.__dict__)
    table = model.sensitivity_analysis("wacc", [], "growth", [0.02, 0.03])
    assert table.shape == (0, 2)
    assert model.__dict__ == original
