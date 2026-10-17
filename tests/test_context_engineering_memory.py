"""Exercise the notebook's memory handler without executing API-backed cells."""

import ast
import json
import tempfile
import unittest
from pathlib import Path


def load_notebook_handler(notebook_path):
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        if "class MemoryToolHandler:" not in source:
            continue
        tree = ast.parse(source)
        classes = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "MemoryToolHandler"
        ]
        if len(classes) != 1:
            raise AssertionError("Expected one notebook MemoryToolHandler class")
        module = ast.Module(body=classes, type_ignores=[])
        namespace = {"Path": Path, "tempfile": tempfile}
        # Execute only the local class definition, never the notebook's API calls.
        exec(compile(module, str(notebook_path), "exec"), namespace)  # noqa: S102
        return namespace["MemoryToolHandler"]
    raise AssertionError("Notebook MemoryToolHandler class not found")


def filesystem_snapshot(root):
    return {
        str(path.relative_to(root)): None if path.is_dir() else path.read_bytes()
        for path in root.rglob("*")
    }


class TestNotebookMemoryTool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        notebook_path = (
            Path(__file__).resolve().parents[1]
            / "tool_use/context_engineering/context_engineering_tools.ipynb"
        )
        cls.handler_class = load_notebook_handler(notebook_path)

    def test_shared_prefix_sibling_operations_are_rejected(self):
        escaped = "/memories/../memories_backup/victim.txt"
        operations = [
            {"command": "view", "path": escaped},
            {"command": "create", "path": escaped, "file_text": "changed"},
            {
                "command": "str_replace",
                "path": escaped,
                "old_str": "secret",
                "new_str": "changed",
            },
            {"command": "insert", "path": escaped, "insert_line": 0, "insert_text": "changed"},
            {"command": "delete", "path": escaped},
            {"command": "rename", "old_path": escaped, "new_path": "/memories/imported.txt"},
            {
                "command": "rename",
                "old_path": "/memories/owned.txt",
                "new_path": "/memories/../memories_backup/exported.txt",
            },
        ]
        for operation in operations:
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                handler = self.handler_class(str(root / "memories"))
                (root / "memories_backup").mkdir()
                (root / "memories_backup/victim.txt").write_text("secret", encoding="utf-8")
                (root / "memories/owned.txt").write_text("owned", encoding="utf-8")
                before = filesystem_snapshot(root)

                result = handler.handle(operation)

                self.assertTrue(result.startswith("Error: path escapes memory directory:"), result)
                self.assertEqual(filesystem_snapshot(root), before)

    def test_similar_user_directories_are_isolated(self):
        for other_user in ("user_12", "user_123"):
            for command in ("view", "delete"):
                with (
                    self.subTest(other_user=other_user, command=command),
                    tempfile.TemporaryDirectory() as directory,
                ):
                    root = Path(directory)
                    handler = self.handler_class(str(root / "user_1"))
                    (root / other_user).mkdir()
                    (root / other_user / "notes.txt").write_text("private", encoding="utf-8")
                    before = filesystem_snapshot(root)

                    result = handler.handle(
                        {"command": command, "path": f"/memories/../{other_user}/notes.txt"}
                    )

                    self.assertTrue(
                        result.startswith("Error: path escapes memory directory:"), result
                    )
                    self.assertEqual(filesystem_snapshot(root), before)

    def test_create_does_not_create_nonexistent_sibling(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            handler = self.handler_class(str(root / "memories"))
            target = root / "memories_evil/nested/created.txt"
            self.assertFalse(target.parent.parent.exists())
            before = filesystem_snapshot(root)

            result = handler.handle(
                {
                    "command": "create",
                    "path": "/memories/../memories_evil/nested/created.txt",
                    "file_text": "escaped",
                }
            )

            self.assertTrue(result.startswith("Error: path escapes memory directory:"), result)
            self.assertFalse(target.parent.parent.exists())
            self.assertEqual(filesystem_snapshot(root), before)

    def test_non_prefix_parent_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            handler = self.handler_class(str(root / "users/memories"))
            (root / "etc").mkdir()
            # A controlled fixture, never the host's real /etc/passwd.
            (root / "etc/passwd").write_text("outside", encoding="utf-8")
            before = filesystem_snapshot(root)

            result = handler.handle({"command": "view", "path": "/memories/../../etc/passwd"})

            self.assertTrue(result.startswith("Error: path escapes memory directory:"), result)
            self.assertEqual(filesystem_snapshot(root), before)

    def test_valid_operations_and_normalized_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "memories"
            handler = self.handler_class(str(base))
            steps = [
                ({"command": "view", "path": "/memories"}, "(empty directory)"),
                (
                    {"command": "create", "path": "/memories/nested/note.txt", "file_text": "one"},
                    "Created /memories/nested/note.txt",
                ),
                ({"command": "view", "path": "/memories/"}, "nested/"),
                ({"command": "view", "path": "/memories/nested/note.txt"}, "   1\tone"),
                (
                    {
                        "command": "str_replace",
                        "path": "/memories/nested/note.txt",
                        "old_str": "one",
                        "new_str": "two",
                    },
                    "Replaced in /memories/nested/note.txt",
                ),
                (
                    {
                        "command": "insert",
                        "path": "/memories/nested/note.txt",
                        "insert_line": 1,
                        "insert_text": "three",
                    },
                    "Inserted at line 1 in /memories/nested/note.txt",
                ),
                (
                    {
                        "command": "rename",
                        "old_path": "/memories/nested/note.txt",
                        "new_path": "/memories/nested/../renamed.txt",
                    },
                    "Renamed /memories/nested/note.txt → /memories/nested/../renamed.txt",
                ),
                ({"command": "view", "path": "/memories/renamed.txt"}, "   1\ttwo\n   2\tthree"),
                (
                    {"command": "delete", "path": "/memories/renamed.txt"},
                    "Deleted /memories/renamed.txt",
                ),
                ({"command": "delete", "path": "/memories/nested"}, "Deleted /memories/nested"),
                ({"command": "view", "path": "/memories"}, "(empty directory)"),
            ]
            for operation, expected in steps:
                with self.subTest(operation=operation):
                    self.assertEqual(handler.handle(operation), expected)
            self.assertEqual(filesystem_snapshot(base), {})


if __name__ == "__main__":
    unittest.main()
