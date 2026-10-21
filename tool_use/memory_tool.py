"""
Production-ready memory tool handler for Claude's memory_20250818 tool.

This implementation provides secure, client-side execution of memory operations
with path validation, error handling, and comprehensive security measures.
"""

import shutil
from pathlib import Path
from typing import Any


class MemoryToolHandler:
    """
    Handles execution of Claude's memory tool commands.

    The memory tool enables Claude to read, write, and manage files in a memory
    system through a standardized tool interface. This handler provides client-side
    implementation with security controls.

    Attributes:
        base_path: Root directory for memory storage
        memory_root: The /memories directory within base_path
    """

    def __init__(self, base_path: str = "./memory_storage"):
        """
        Initialize the memory tool handler.

        Args:
            base_path: Root directory for all memory operations
        """
        self.base_path = Path(base_path).resolve()
        self.memory_root = self.base_path / "memories"
        self.memory_root.mkdir(parents=True, exist_ok=True)

    def _validate_path(self, path: str) -> Path:
        """
        Validate and resolve memory paths to prevent directory traversal attacks.

        Args:
            path: The path to validate (must start with /memories)

        Returns:
            Resolved absolute Path object within memory_root

        Raises:
            ValueError: If path is invalid or attempts to escape memory directory
        """
        if not path.startswith("/memories"):
            raise ValueError(
                f"Path must start with /memories, got: {path}. "
                "All memory operations must be confined to the /memories directory."
            )

        # Remove /memories prefix and any leading slashes
        relative_path = path[len("/memories") :].lstrip("/")

        # Resolve to absolute path within memory_root
        if relative_path:
            full_path = (self.memory_root / relative_path).resolve()
        else:
            full_path = self.memory_root.resolve()

        # Verify the resolved path is still within memory_root
        try:
            full_path.relative_to(self.memory_root.resolve())
        except ValueError as e:
            raise ValueError(
                f"Path '{path}' would escape /memories directory. "
                "Directory traversal attempts are not allowed."
            ) from e

        return full_path

    def execute(self, **params: Any) -> dict[str, str]:
        """
        Execute a memory tool command.

        Args:
            **params: Command parameters from Claude's tool use

        Returns:
            Dict with either 'success' or 'error' key

        Supported commands:
            - view: Show directory contents or file contents
            - create: Create or overwrite a file
            - str_replace: Replace text in a file
            - insert: Insert text at a specific line
            - delete: Delete a file or directory
            - rename: Rename or move a file/directory
        """
        command = params.get("command")

        try:
            if command == "view":
                return self._view(params)
            elif command == "create":
                return self._create(params)
            elif command == "str_replace":
                return self._str_replace(params)
            elif command == "insert":
                return self._insert(params)
            elif command == "delete":
                return self._delete(params)
            elif command == "rename":
                return self._rename(params)
            else:
                return {
                    "error": f"Unknown command: '{command}'. "
                    "Valid commands are: view, create, str_replace, insert, delete, rename"
                }
        except ValueError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"Unexpected error executing {command}: {e}"}

    def _view(self, params: dict[str, Any]) -> dict[str, str]:
        """View directory contents or file contents."""
        path = params.get("path")
        view_range = params.get("view_range")

        if not path:
            return {"error": "Missing required parameter: path"}

        full_path = self._validate_path(path)

        # Handle directory listing
        if full_path.is_dir():
            try:
                items = []
                for item in sorted(full_path.iterdir()):
                    if item.name.startswith("."):
                        continue
                    items.append(f"{item.name}/" if item.is_dir() else item.name)

                if not items:
                    return {"success": f"Directory: {path}\n(empty)"}

                return {
                    "success": f"Directory: {path}\n" + "\n".join([f"- {item}" for item in items])
                }
            except Exception as e:
                return {"error": f"Cannot read directory {path}: {e}"}

        # Handle file reading
        elif full_path.is_file():
            try:
                content = full_path.read_text(encoding="utf-8")
                lines = content.splitlines()

                # Apply view range if specified
                if view_range:
                    start_line = max(1, view_range[0]) - 1  # Convert to 0-indexed
                    end_line = len(lines) if view_range[1] == -1 else view_range[1]
                    lines = lines[start_line:end_line]
                    start_num = start_line + 1
                else:
                    start_num = 1

                # Format with line numbers
                numbered_lines = [f"{i + start_num:4d}: {line}" for i, line in enumerate(lines)]
                return {"success": "\n".join(numbered_lines)}

            except UnicodeDecodeError:
                return {"error": f"Cannot read {path}: File is not valid UTF-8 text"}
            except Exception as e:
                return {"error": f"Cannot read file {path}: {e}"}

        else:
            return {"error": f"Path not found: {path}"}

    def _create(self, params: dict[str, Any]) -> dict[str, str]:
        """Create or overwrite a file."""
        path = params.get("path")
        file_text = params.get("file_text", "")

        if not path:
            return {"error": "Missing required parameter: path"}

        full_path = self._validate_path(path)

        # Don't allow creating directories directly
        if not path.endswith((".txt", ".md", ".json", ".py", ".yaml", ".yml")):
            return {
                "error": f"Cannot create {path}: Only text files are supported. "
                "Use file extensions: .txt, .md, .json, .py, .yaml, .yml"
            }

        try:
            # Create parent directories if needed
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the file
            full_path.write_text(file_text, encoding="utf-8")
            return {"success": f"File created successfully at {path}"}

        except Exception as e:
            return {"error": f"Cannot create file {path}: {e}"}

    def _str_replace(self, params: dict[str, Any]) -> dict[str, str]:
        """Replace text in a file."""
        path = params.get("path")
        old_str = params.get("old_str")
        new_str = params.get("new_str", "")

        if not path or old_str is None:
            return {"error": "Missing required parameters: path, old_str"}

        full_path = self._validate_path(path)

        if not full_path.is_file():
            return {"error": f"File not found: {path}"}

        try:
            content = full_path.read_text(encoding="utf-8")

            # Check if old_str exists
            count = content.count(old_str)
            if count == 0:
                return {
                    "error": f"String not found in {path}. The exact text must exist in the file."
                }
            elif count > 1:
                return {
                    "error": f"String appears {count} times in {path}. "
                    "The string must be unique. Use more specific context."
                }

            # Perform replacement
            new_content = content.replace(old_str, new_str, 1)
            full_path.write_text(new_content, encoding="utf-8")

            return {"success": f"File {path} has been edited successfully"}

        except Exception as e:
            return {"error": f"Cannot edit file {path}: {e}"}

    def _insert(self, params: dict[str, Any]) -> dict[str, str]:
        """Insert text at a specific line."""
        path = params.get("path")
        insert_line = params.get("insert_line")
        insert_text = params.get("insert_text", "")

        if not path or insert_line is None:
            return {"error": "Missing required parameters: path, insert_line"}

        full_path = self._validate_path(path)

        if not full_path.is_file():
            return {"error": f"File not found: {path}"}

        try:
            lines = full_path.read_text(encoding="utf-8").splitlines()

            # Convert from 1-based to 0-based indexing
            insert_line = insert_line - 1

            # Validate insert_line
            if insert_line < 0 or insert_line > len(lines):
                return {
                    "error": f"Invalid insert_line {insert_line + 1}. "
                    f"Must be between 1 and {len(lines) + 1}"
                }

            # Insert the text
            lines.insert(insert_line, insert_text.rstrip("\n"))

            # Write back
            full_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            return {"success": f"Text inserted at line {insert_line} in {path}"}

        except Exception as e:
            return {"error": f"Cannot insert into {path}: {e}"}

    def _delete(self, params: dict[str, Any]) -> dict[str, str]:
        """Delete a file or directory."""
        path = params.get("path")

        if not path:
            return {"error": "Missing required parameter: path"}

        # Prevent deletion of root memories directory
        if path == "/memories":
            return {"error": "Cannot delete the /memories directory itself"}

        full_path = self._validate_path(path)

        # Verify the path is within /memories to prevent accidental deletion outside the memory directory
        # This provides an additional safety check beyond _validate_path
        try:
            full_path.relative_to(self.memory_root.resolve())
        except ValueError:
            return {
                "error": f"Invalid operation: Path '{path}' is not within /memories directory. "
                "Only paths within /memories can be deleted."
            }

        if not full_path.exists():
            return {"error": f"Path not found: {path}"}

        try:
            if full_path.is_file():
                full_path.unlink()
                return {"success": f"File deleted: {path}"}
            elif full_path.is_dir():
                shutil.rmtree(full_path)
                return {"success": f"Directory deleted: {path}"}

        except Exception as e:
            return {"error": f"Cannot delete {path}: {e}"}

    def _rename(self, params: dict[str, Any]) -> dict[str, str]:
        """Rename or move a file/directory."""
        old_path = params.get("old_path")
        new_path = params.get("new_path")

        if not old_path or not new_path:
            return {"error": "Missing required parameters: old_path, new_path"}

        old_full_path = self._validate_path(old_path)
        new_full_path = self._validate_path(new_path)

        if not old_full_path.exists():
            return {"error": f"Source path not found: {old_path}"}

        if new_full_path.exists():
            return {
                "error": f"Destination already exists: {new_path}. "
                "Cannot overwrite existing files/directories."
            }

        try:
            # Create parent directories if needed
            new_full_path.parent.mkdir(parents=True, exist_ok=True)

            # Perform rename/move
            old_full_path.rename(new_full_path)

            return {"success": f"Renamed {old_path} to {new_path}"}

        except Exception as e:
            return {"error": f"Cannot rename {old_path} to {new_path}: {e}"}

    def clear_all_memory(self) -> dict[str, str]:
        """
        Clear all memory files (useful for testing or starting fresh).

        ⚠️ WARNING: This method is for demonstration and testing purposes only.
        In production, you should carefully consider whether you need to delete
        all memory files, as this will permanently remove all learned patterns
        and stored knowledge. Consider using selective deletion instead.

        Returns:
            Dict with success message
        """
        try:
            if self.memory_root.exists():
                shutil.rmtree(self.memory_root)
            self.memory_root.mkdir(parents=True, exist_ok=True)
            return {"success": "All memory cleared successfully"}
        except Exception as e:
            return {"error": f"Cannot clear memory: {e}"}
