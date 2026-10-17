"""Offline regression tests for the programmatic tool calling mock expense API."""

import json
import os
import random
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from tool_use.utils.team_expense_api import (
    EXPENSE_LINE_ITEMS_PER_PERSON_MAX,
    EXPENSE_LINE_ITEMS_PER_PERSON_MIN,
    get_expenses,
)


def test_expenses_are_reproducible_across_processes():
    script = (
        "from tool_use.utils.team_expense_api import get_expenses; "
        "print(get_expenses('ENG001', 'Q3'))"
    )
    outputs = []
    for hash_seed in ("1", "2"):
        result = subprocess.run(  # noqa: S603 - fixed offline script using this interpreter
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "PYTHONHASHSEED": hash_seed},
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        outputs.append(json.loads(result.stdout))

    assert outputs[0] == outputs[1]


@pytest.mark.parametrize("quarter", ["Q3", "invalid"])
def test_expenses_preserve_global_random_state(quarter):
    state = random.getstate()
    try:
        get_expenses("ENG001", quarter)
        assert random.getstate() == state
    finally:
        random.setstate(state)


@pytest.mark.parametrize("quarter", ["Q3", "q3"])
def test_expenses_are_repeatable_between_other_requests(quarter):
    first = get_expenses("ENG001", "Q3")
    other_employee = get_expenses("ENG002", "Q3")
    other_quarter = get_expenses("ENG001", "Q4")

    assert get_expenses("ENG001", quarter) == first
    amounts = [expense["amount"] for expense in json.loads(first)]
    assert amounts != [expense["amount"] for expense in json.loads(other_employee)]
    assert amounts != [expense["amount"] for expense in json.loads(other_quarter)]


@pytest.mark.parametrize("quarter", ["Q1", "Q2", "Q3", "Q4"])
def test_expenses_respect_quarter_and_record_contract(quarter):
    expenses = json.loads(get_expenses("ENG001", quarter))
    assert EXPENSE_LINE_ITEMS_PER_PERSON_MIN <= len(expenses) <= EXPENSE_LINE_ITEMS_PER_PERSON_MAX
    assert len({expense["expense_id"] for expense in expenses}) == len(expenses)
    dates = [date.fromisoformat(expense["date"]) for expense in expenses]
    assert dates == sorted(dates)
    assert all(day.year == 2024 and (day.month - 1) // 3 + 1 == int(quarter[1]) for day in dates)
    assert all(expense["amount"] > 0 and expense["currency"] == "USD" for expense in expenses)


def test_expenses_reject_invalid_quarter():
    assert json.loads(get_expenses("ENG001", "invalid")) == {
        "error": "Invalid quarter 'invalid'. Must be Q1, Q2, Q3, or Q4"
    }
