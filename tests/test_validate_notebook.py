"""Tests for the cookbook-audit notebook validator."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR_PATH = REPO_ROOT / ".claude" / "skills" / "cookbook-audit" / "validate_notebook.py"


def load_validator_module() -> Any:
    """Import validate_notebook.py, which lives outside any importable package."""
    spec = importlib.util.spec_from_file_location("validate_notebook", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def validator_module() -> Any:
    return load_validator_module()


def write_notebook(path: Path, source: str) -> Path:
    """Write a single-code-cell notebook to `path`."""
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "source": [source],
                "metadata": {},
                "outputs": [],
                "execution_count": None,
            }
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path.write_text(json.dumps(notebook), encoding="utf-8")
    return path


def test_missing_uvx_falls_back_instead_of_reporting_secrets(
    validator_module: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing detect-secrets must not mark a clean notebook as containing secrets.

    detect-secrets is invoked through `sh -c`, so an absent `uvx` fails inside the
    shell rather than raising FileNotFoundError. Without an explicit check the
    fallback never runs and every notebook is reported as dirty.
    """
    notebook = write_notebook(tmp_path / "clean.ipynb", "print('hello')\n")
    # A PATH without uvx, as on any machine that does not have uv installed.
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    validator = validator_module.NotebookValidator(str(notebook))
    validator.check_hardcoded_secrets()

    assert validator.issues == []
    assert validator.get_exit_code() == 0
    assert any("basic secret detection" in w for w in validator.warnings)


def test_fallback_still_detects_a_hardcoded_key(
    validator_module: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Falling back must not mean detecting nothing."""
    placeholder = "sk-" + "ant-" + "EXAMPLENOTAREALKEY0000000000"
    notebook = write_notebook(
        tmp_path / "dirty.ipynb", f'client = Anthropic(api_key="{placeholder}")\n'
    )
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    validator = validator_module.NotebookValidator(str(notebook))
    validator.check_hardcoded_secrets()

    assert any("Anthropic API key" in issue for issue in validator.issues)
    assert validator.get_exit_code() == 1
