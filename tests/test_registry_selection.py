"""Regression tests for selecting notebooks from the list-form registry."""

from unittest.mock import Mock

import pytest
import yaml

from tests import conftest as notebook_config


def test_load_registry_reads_top_level_list(tmp_path, monkeypatch):
    entries = [{"title": "Registered cookbook", "path": "registered.ipynb"}]
    (tmp_path / "registry.yaml").write_text(yaml.safe_dump(entries), encoding="utf-8")
    monkeypatch.setattr(notebook_config, "get_project_root", lambda: tmp_path)

    assert notebook_config.load_registry() == entries


@pytest.mark.parametrize("content", [None, "", "[]\n"])
def test_load_registry_without_entries(tmp_path, monkeypatch, content):
    if content is not None:
        (tmp_path / "registry.yaml").write_text(content, encoding="utf-8")
    monkeypatch.setattr(notebook_config, "get_project_root", lambda: tmp_path)

    assert notebook_config.load_registry() == []


def test_registry_only_selects_existing_registered_notebooks(tmp_path, monkeypatch):
    registered = tmp_path / "registered.ipynb"
    registered.touch()
    (tmp_path / "unregistered.ipynb").touch()
    entries = [
        {"path": "registered.ipynb"},
        {"path": "missing.ipynb"},
    ]
    (tmp_path / "registry.yaml").write_text(yaml.safe_dump(entries), encoding="utf-8")
    monkeypatch.setattr(notebook_config, "get_project_root", lambda: tmp_path)
    config = Mock()
    config.getoption.side_effect = lambda option: option == "--registry-only"

    assert notebook_config.get_notebooks_to_test(config) == [registered]
