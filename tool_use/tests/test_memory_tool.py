"""
Unit tests for the memory tool handler.

Tests security validation, command execution, and error handling.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from memory_tool import MemoryToolHandler


class TestMemoryToolHandler(unittest.TestCase):
    """Test suite for MemoryToolHandler."""

    def setUp(self):
        """Create temporary directory for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.handler = MemoryToolHandler(base_path=self.test_dir)

    def tearDown(self):
        """Clean up temporary directory after each test."""
        shutil.rmtree(self.test_dir)

    # Security Tests

    def test_path_validation_requires_memories_prefix(self):
        """Test that paths must start with /memories."""
        result = self.handler.execute(command="view", path="/etc/passwd")
        self.assertIn("error", result)
        self.assertIn("must start with /memories", result["error"])

    def test_path_validation_prevents_traversal_dotdot(self):
        """Test that .. traversal is blocked."""
        result = self.handler.execute(command="view", path="/memories/../../../etc/passwd")
        self.assertIn("error", result)
        self.assertIn("escape", result["error"].lower())

    def test_path_validation_prevents_traversal_encoded(self):
        """Test that URL-encoded traversal is blocked."""
        result = self.handler.execute(command="view", path="/memories/%2e%2e/%2e%2e/etc/passwd")
        # The path will be processed and should fail validation
        self.assertIn("error", result)

    def test_path_validation_allows_valid_paths(self):
        """Test that valid memory paths are accepted."""
        result = self.handler.execute(command="create", path="/memories/test.txt", file_text="test")
        self.assertIn("success", result)

    # View Command Tests

    def test_view_empty_directory(self):
        """Test viewing an empty /memories directory."""
        result = self.handler.execute(command="view", path="/memories")
        self.assertIn("success", result)
        self.assertIn("empty", result["success"].lower())

    def test_view_directory_with_files(self):
        """Test viewing a directory with files."""
        # Create some test files
        self.handler.execute(command="create", path="/memories/file1.txt", file_text="content1")
        self.handler.execute(command="create", path="/memories/file2.txt", file_text="content2")

        result = self.handler.execute(command="view", path="/memories")
        self.assertIn("success", result)
        self.assertIn("file1.txt", result["success"])
        self.assertIn("file2.txt", result["success"])

    def test_view_file_with_line_numbers(self):
        """Test viewing a file with line numbers."""
        content = "line 1\nline 2\nline 3"
        self.handler.execute(command="create", path="/memories/test.txt", file_text=content)

        result = self.handler.execute(command="view", path="/memories/test.txt")
        self.assertIn("success", result)
        self.assertIn("   1: line 1", result["success"])
        self.assertIn("   2: line 2", result["success"])
        self.assertIn("   3: line 3", result["success"])

    def test_view_file_with_range(self):
        """Test viewing specific line range."""
        content = "line 1\nline 2\nline 3\nline 4"
        self.handler.execute(command="create", path="/memories/test.txt", file_text=content)

        result = self.handler.execute(command="view", path="/memories/test.txt", view_range=[2, 3])
        self.assertIn("success", result)
        self.assertIn("   2: line 2", result["success"])
        self.assertIn("   3: line 3", result["success"])
        self.assertNotIn("line 1", result["success"])
        self.assertNotIn("line 4", result["success"])

    def test_view_nonexistent_path(self):
        """Test viewing a nonexistent path."""
        result = self.handler.execute(command="view", path="/memories/notfound.txt")
        self.assertIn("error", result)
        self.assertIn("not found", result["error"].lower())

    # Create Command Tests

    def test_create_file(self):
        """Test creating a file."""
        result = self.handler.execute(
            command="create", path="/memories/test.txt", file_text="Hello, World!"
        )
        self.assertIn("success", result)

        # Verify file exists
        file_path = Path(self.test_dir) / "memories" / "test.txt"
        self.assertTrue(file_path.exists())
        self.assertEqual(file_path.read_text(), "Hello, World!")

    def test_create_file_in_subdirectory(self):
        """Test creating a file in a subdirectory (auto-creates dirs)."""
        result = self.handler.execute(
            command="create",
            path="/memories/subdir/test.txt",
            file_text="Nested content",
        )
        self.assertIn("success", result)

        file_path = Path(self.test_dir) / "memories" / "subdir" / "test.txt"
        self.assertTrue(file_path.exists())

    def test_create_requires_file_extension(self):
        """Test that create only allows text file extensions."""
        result = self.handler.execute(command="create", path="/memories/noext", file_text="content")
        self.assertIn("error", result)
        self.assertIn("text files are supported", result["error"])

    def test_create_overwrites_existing_file(self):
        """Test that create overwrites existing files."""
        self.handler.execute(command="create", path="/memories/test.txt", file_text="original")
        result = self.handler.execute(
            command="create", path="/memories/test.txt", file_text="updated"
        )
        self.assertIn("success", result)

        file_path = Path(self.test_dir) / "memories" / "test.txt"
        self.assertEqual(file_path.read_text(), "updated")

    # String Replace Command Tests

    def test_str_replace_success(self):
        """Test successful string replacement."""
        self.handler.execute(
            command="create",
            path="/memories/test.txt",
            file_text="Hello World",
        )

        result = self.handler.execute(
            command="str_replace",
            path="/memories/test.txt",
            old_str="World",
            new_str="Universe",
        )
        self.assertIn("success", result)

        file_path = Path(self.test_dir) / "memories" / "test.txt"
        self.assertEqual(file_path.read_text(), "Hello Universe")

    def test_str_replace_string_not_found(self):
        """Test replacement when string doesn't exist."""
        self.handler.execute(command="create", path="/memories/test.txt", file_text="Hello World")

        result = self.handler.execute(
            command="str_replace",
            path="/memories/test.txt",
            old_str="Missing",
            new_str="Text",
        )
        self.assertIn("error", result)
        self.assertIn("not found", result["error"].lower())

    def test_str_replace_multiple_occurrences(self):
        """Test that replacement fails with multiple occurrences."""
        self.handler.execute(
            command="create",
            path="/memories/test.txt",
            file_text="Hello World Hello World",
        )

        result = self.handler.execute(
            command="str_replace",
            path="/memories/test.txt",
            old_str="Hello",
            new_str="Hi",
        )
        self.assertIn("error", result)
        self.assertIn("appears 2 times", result["error"])

    def test_str_replace_file_not_found(self):
        """Test replacement on nonexistent file."""
        result = self.handler.execute(
            command="str_replace",
            path="/memories/notfound.txt",
            old_str="old",
            new_str="new",
        )
        self.assertIn("error", result)
        self.assertIn("not found", result["error"].lower())

    # Insert Command Tests

    def test_insert_at_beginning(self):
        """Test inserting at line 0 (beginning)."""
        self.handler.execute(
            command="create", path="/memories/test.txt", file_text="line 1\nline 2"
        )

        result = self.handler.execute(
            command="insert",
            path="/memories/test.txt",
            insert_line=0,
            insert_text="new line",
        )
        self.assertIn("success", result)

        file_path = Path(self.test_dir) / "memories" / "test.txt"
        self.assertEqual(file_path.read_text(), "new line\nline 1\nline 2\n")

    def test_insert_in_middle(self):
        """Test inserting in the middle."""
        self.handler.execute(
            command="create", path="/memories/test.txt", file_text="line 1\nline 2"
        )

        result = self.handler.execute(
            command="insert",
            path="/memories/test.txt",
            insert_line=1,
            insert_text="inserted",
        )
        self.assertIn("success", result)

        file_path = Path(self.test_dir) / "memories" / "test.txt"
        self.assertEqual(file_path.read_text(), "line 1\ninserted\nline 2\n")

    def test_insert_at_end(self):
        """Test inserting at the end."""
        self.handler.execute(
            command="create", path="/memories/test.txt", file_text="line 1\nline 2"
        )

        result = self.handler.execute(
            command="insert",
            path="/memories/test.txt",
            insert_line=2,
            insert_text="last line",
        )
        self.assertIn("success", result)

    def test_insert_invalid_line(self):
        """Test insert with invalid line number."""
        self.handler.execute(command="create", path="/memories/test.txt", file_text="line 1")

        result = self.handler.execute(
            command="insert",
            path="/memories/test.txt",
            insert_line=99,
            insert_text="text",
        )
        self.assertIn("error", result)
        self.assertIn("invalid", result["error"].lower())

    # Delete Command Tests

    def test_delete_file(self):
        """Test deleting a file."""
        self.handler.execute(command="create", path="/memories/test.txt", file_text="content")

        result = self.handler.execute(command="delete", path="/memories/test.txt")
        self.assertIn("success", result)

        file_path = Path(self.test_dir) / "memories" / "test.txt"
        self.assertFalse(file_path.exists())

    def test_delete_directory(self):
        """Test deleting a directory."""
        self.handler.execute(
            command="create", path="/memories/subdir/test.txt", file_text="content"
        )

        result = self.handler.execute(command="delete", path="/memories/subdir")
        self.assertIn("success", result)

        dir_path = Path(self.test_dir) / "memories" / "subdir"
        self.assertFalse(dir_path.exists())

    def test_delete_cannot_delete_root(self):
        """Test that root /memories directory cannot be deleted."""
        result = self.handler.execute(command="delete", path="/memories")
        self.assertIn("error", result)
        self.assertIn("cannot delete", result["error"].lower())

    def test_delete_cannot_delete_root_via_aliases(self):
        """Root deletion must be blocked regardless of how the path is spelled."""
        self.handler.execute(command="create", path="/memories/keep.txt", file_text="content")
        root_path = Path(self.test_dir) / "memories"

        for alias in ("/memories/", "/memories/.", "/memories/sub/.."):
            result = self.handler.execute(command="delete", path=alias)
            self.assertIn("error", result, f"{alias} should be rejected")
            self.assertIn("cannot delete", result["error"].lower())
            # The memory store and its contents must remain intact.
            self.assertTrue(root_path.exists())
            self.assertTrue((root_path / "keep.txt").exists())

    def test_delete_nonexistent_path(self):
        """Test deleting a nonexistent path."""
        result = self.handler.execute(command="delete", path="/memories/notfound.txt")
        self.assertIn("error", result)
        self.assertIn("not found", result["error"].lower())

    # Rename Command Tests

    def test_rename_file(self):
        """Test renaming a file."""
        self.handler.execute(command="create", path="/memories/old.txt", file_text="content")

        result = self.handler.execute(
            command="rename", old_path="/memories/old.txt", new_path="/memories/new.txt"
        )
        self.assertIn("success", result)

        old_path = Path(self.test_dir) / "memories" / "old.txt"
        new_path = Path(self.test_dir) / "memories" / "new.txt"
        self.assertFalse(old_path.exists())
        self.assertTrue(new_path.exists())

    def test_rename_to_subdirectory(self):
        """Test moving a file to a subdirectory."""
        self.handler.execute(command="create", path="/memories/file.txt", file_text="content")

        result = self.handler.execute(
            command="rename",
            old_path="/memories/file.txt",
            new_path="/memories/subdir/file.txt",
        )
        self.assertIn("success", result)

        new_path = Path(self.test_dir) / "memories" / "subdir" / "file.txt"
        self.assertTrue(new_path.exists())

    def test_rename_source_not_found(self):
        """Test rename when source doesn't exist."""
        result = self.handler.execute(
            command="rename",
            old_path="/memories/notfound.txt",
            new_path="/memories/new.txt",
        )
        self.assertIn("error", result)
        self.assertIn("not found", result["error"].lower())

    def test_rename_destination_exists(self):
        """Test rename when destination already exists."""
        self.handler.execute(command="create", path="/memories/file1.txt", file_text="content1")
        self.handler.execute(command="create", path="/memories/file2.txt", file_text="content2")

        result = self.handler.execute(
            command="rename",
            old_path="/memories/file1.txt",
            new_path="/memories/file2.txt",
        )
        self.assertIn("error", result)
        self.assertIn("already exists", result["error"].lower())

    # Error Handling Tests

    def test_unknown_command(self):
        """Test handling of unknown command."""
        result = self.handler.execute(command="invalid", path="/memories")
        self.assertIn("error", result)
        self.assertIn("unknown command", result["error"].lower())

    def test_missing_required_parameters(self):
        """Test error handling for missing parameters."""
        result = self.handler.execute(command="view")
        self.assertIn("error", result)

    # Utility Tests

    def test_clear_all_memory(self):
        """Test clearing all memory."""
        # Create some files
        self.handler.execute(command="create", path="/memories/file1.txt", file_text="content1")
        self.handler.execute(command="create", path="/memories/file2.txt", file_text="content2")

        result = self.handler.clear_all_memory()
        self.assertIn("success", result)

        # Verify directory exists but is empty
        memory_root = Path(self.test_dir) / "memories"
        self.assertTrue(memory_root.exists())
        self.assertEqual(len(list(memory_root.iterdir())), 0)


if __name__ == "__main__":
    unittest.main()
