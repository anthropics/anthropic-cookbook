"""Regression tests for BrandValidator.validate_colors() color normalisation."""

import sys
from pathlib import Path

import pytest

SKILL_DIR = (
    Path(__file__).resolve().parent.parent / "skills/custom_skills/applying-brand-guidelines"
)
sys.path.insert(0, str(SKILL_DIR))

from validate_brand import BrandValidator, get_acme_corporation_guidelines  # noqa: E402


def _check(color: str):
    validator = BrandValidator(get_acme_corporation_guidelines())
    return validator.validate_colors(f'<p style="color: {color}">Professional solutions</p>')


@pytest.mark.parametrize(
    "color", ["#0066CC", "#0066cc", "rgb(0, 102, 204)", "RGB(0,102,204)", "#FFFFFF", "#fff", "#FFF"]
)
def test_approved_color_notations_pass(color):
    violations, _ = _check(color)
    assert violations == []


@pytest.mark.parametrize("color", ["#FF0000", "#f00", "rgb(255, 0, 0)"])
def test_unapproved_colors_still_fail(color):
    violations, _ = _check(color)
    assert violations == [f"Unapproved color used: {color}"]
