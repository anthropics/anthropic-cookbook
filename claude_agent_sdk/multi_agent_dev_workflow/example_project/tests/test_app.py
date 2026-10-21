"""Existing tests for the TODO app. QA agent will add to these."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app import TodoStore


def test_create_todo():
    store = TodoStore()
    todo = store.create("Buy milk")
    assert todo.title == "Buy milk"
    assert todo.completed is False
    assert todo.id is not None


def test_get_todo():
    store = TodoStore()
    created = store.create("Test item")
    fetched = store.get(created.id)
    assert fetched is not None
    assert fetched.title == "Test item"


def test_get_nonexistent_returns_none():
    store = TodoStore()
    assert store.get("nonexistent-id") is None


def test_list_all():
    store = TodoStore()
    store.create("Item 1")
    store.create("Item 2")
    assert len(store.list_all()) == 2


def test_update_todo():
    store = TodoStore()
    todo = store.create("Original")
    updated = store.update(todo.id, title="Modified", completed=True)
    assert updated.title == "Modified"
    assert updated.completed is True


def test_delete_todo():
    store = TodoStore()
    todo = store.create("To delete")
    assert store.delete(todo.id) is True
    assert store.get(todo.id) is None


def test_delete_nonexistent_returns_false():
    store = TodoStore()
    assert store.delete("nonexistent") is False
