"""Pytest configuration and fixtures for notebook testing."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.notebook_tests.utils import (
    find_all_notebooks,
    load_notebook,
    parse_notebook_cells,
    validate_notebook_structure,
)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command-line options for notebook testing."""
    parser.addoption(
        "--notebook",
        action="store",
        default=None,
        help="Run tests for a specific notebook path",
    )
    parser.addoption(
        "--notebook-dir",
        action="store",
        default=None,
        help="Run tests for all notebooks in a directory",
    )
    parser.addoption(
        "--execute-notebooks",
        action="store_true",
        default=False,
        help="Actually execute notebooks (requires API keys, slower)",
    )
    parser.addoption(
        "--notebook-timeout",
        action="store",
        default=300,
        type=int,
        help="Timeout in seconds for notebook execution (default: 300)",
    )
    parser.addoption(
        "--skip-third-party",
        action="store_true",
        default=False,
        help="Skip notebooks in third_party directory",
    )
    parser.addoption(
        "--registry-only",
        action="store_true",
        default=False,
        help="Only test notebooks listed in registry.yaml",
    )


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def load_registry() -> list[dict[str, Any]]:
    """Load the notebook registry."""
    registry_path = get_project_root() / "registry.yaml"
    if not registry_path.exists():
        return []

    with open(registry_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data or []


def get_notebooks_to_test(config: pytest.Config) -> list[Path]:
    """Determine which notebooks to test based on config options."""
    root = get_project_root()
    notebooks = []

    # Specific notebook
    if config.getoption("--notebook"):
        nb_path = Path(config.getoption("--notebook"))
        if not nb_path.is_absolute():
            nb_path = root / nb_path
        if nb_path.exists():
            return [nb_path]
        return []

    # Specific directory
    if config.getoption("--notebook-dir"):
        nb_dir = Path(config.getoption("--notebook-dir"))
        if not nb_dir.is_absolute():
            nb_dir = root / nb_dir
        return find_all_notebooks(nb_dir)

    # Registry only
    if config.getoption("--registry-only"):
        registry = load_registry()
        for entry in registry:
            nb_path = root / entry.get("path", "")
            if nb_path.exists():
                notebooks.append(nb_path)
        return notebooks

    # All notebooks
    exclude_patterns = [".ipynb_checkpoints/*"]
    if config.getoption("--skip-third-party"):
        exclude_patterns.append("third_party/*")

    return find_all_notebooks(root, exclude_patterns)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Generate parameterized tests for notebooks."""
    if "notebook_path" in metafunc.fixturenames:
        notebooks = get_notebooks_to_test(metafunc.config)
        if notebooks:
            # Use relative paths for cleaner test names
            root = get_project_root()
            ids = [str(nb.relative_to(root)) for nb in notebooks]
            metafunc.parametrize("notebook_path", notebooks, ids=ids)


@pytest.fixture
def project_root() -> Path:
    """Fixture providing the project root directory."""
    return get_project_root()


@pytest.fixture
def notebook_data(notebook_path: Path) -> dict[str, Any]:
    """Fixture providing loaded notebook data."""
    return load_notebook(notebook_path)


@pytest.fixture
def notebook_cells(notebook_data: dict[str, Any]) -> list:
    """Fixture providing parsed notebook cells."""
    return parse_notebook_cells(notebook_data)


@pytest.fixture
def validation_result(notebook_path: Path):
    """Fixture providing validation result for a notebook."""
    return validate_notebook_structure(notebook_path)


@pytest.fixture
def execute_notebooks(request: pytest.FixtureRequest) -> bool:
    """Fixture indicating whether to execute notebooks."""
    return request.config.getoption("--execute-notebooks")


@pytest.fixture
def notebook_timeout(request: pytest.FixtureRequest) -> int:
    """Fixture providing the notebook execution timeout."""
    return request.config.getoption("--notebook-timeout")


@pytest.fixture
def has_api_key() -> bool:
    """Fixture indicating whether the Anthropic API key is available."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


@pytest.fixture
def registry() -> list[dict[str, Any]]:
    """Fixture providing the notebook registry."""
    return load_registry()
