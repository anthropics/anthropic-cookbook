"""Minimal TODO API — the example project for the multi-agent workflow demo.

This is intentionally simple. The point is to demonstrate the workflow pattern,
not the application. Any project can use this workflow by dropping the .claude/
directory into its root.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


@dataclass
class Todo:
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    completed: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class TodoStore:
    """In-memory store. Replace with a real database in production."""

    def __init__(self):
        self._todos: dict[str, Todo] = {}

    def create(self, title: str) -> Todo:
        todo = Todo(title=title)
        self._todos[todo.id] = todo
        return todo

    def get(self, todo_id: str) -> Todo | None:
        return self._todos.get(todo_id)

    def list_all(self) -> list[Todo]:
        return list(self._todos.values())

    def update(self, todo_id: str, **kwargs) -> Todo | None:
        todo = self._todos.get(todo_id)
        if not todo:
            return None
        for key, value in kwargs.items():
            if hasattr(todo, key):
                setattr(todo, key, value)
        return todo

    def delete(self, todo_id: str) -> bool:
        return self._todos.pop(todo_id, None) is not None


store = TodoStore()
