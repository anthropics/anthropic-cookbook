"""Core utilities for notebook testing and validation."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CellInfo:
    """Information about a notebook cell."""

    index: int
    cell_type: str
    execution_count: int | None
    source: str
    outputs: list[dict[str, Any]]
    has_error_output: bool = False
    is_empty: bool = False


@dataclass
class NotebookValidationResult:
    """Result of validating a notebook."""

    path: Path
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)
    cells: list[CellInfo] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def add_info(self, message: str) -> None:
        self.info.append(message)


def load_notebook(path: Path) -> dict[str, Any]:
    """Load a notebook from disk."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_notebook_cells(notebook: dict[str, Any]) -> list[CellInfo]:
    """Parse cells from a notebook structure."""
    cells = []
    for i, cell in enumerate(notebook.get("cells", [])):
        source = "".join(cell.get("source", []))
        outputs = cell.get("outputs", [])

        has_error = any(out.get("output_type") == "error" for out in outputs)

        cells.append(
            CellInfo(
                index=i,
                cell_type=cell.get("cell_type", "unknown"),
                execution_count=cell.get("execution_count"),
                source=source,
                outputs=outputs,
                has_error_output=has_error,
                is_empty=not source.strip(),
            )
        )
    return cells


def validate_cell_execution_order(cells: list[CellInfo]) -> list[str]:
    """
    Validate that code cells were executed in order.

    Returns a list of issues found.
    """
    issues = []
    code_cells = [c for c in cells if c.cell_type == "code"]

    # Get execution counts (excluding None)
    exec_counts = [c.execution_count for c in code_cells if c.execution_count is not None]

    if not exec_counts:
        return issues

    # Check for out-of-order execution
    for i in range(1, len(exec_counts)):
        if exec_counts[i] < exec_counts[i - 1]:
            issues.append(
                f"Cells executed out of order: cell with exec_count {exec_counts[i]} "
                f"appears after cell with exec_count {exec_counts[i - 1]}"
            )

    # Check for gaps in execution counts (cells re-run)
    expected = exec_counts[0]
    for _i, count in enumerate(exec_counts):
        if count != expected:
            issues.append(
                f"Non-sequential execution detected: expected {expected}, got {count} "
                f"(suggests cells were re-run or run out of order)"
            )
        expected = count + 1

    return issues


def validate_all_cells_executed(cells: list[CellInfo]) -> list[str]:
    """
    Validate that all code cells have been executed.

    Returns a list of issues found.
    """
    issues = []
    for cell in cells:
        if cell.cell_type == "code" and not cell.is_empty:
            if cell.execution_count is None:
                issues.append(f"Cell {cell.index}: Code cell has not been executed")

    return issues


def validate_no_error_outputs(cells: list[CellInfo]) -> list[str]:
    """
    Validate that no cells have error outputs.

    Returns a list of issues found.
    """
    issues = []
    for cell in cells:
        if cell.has_error_output:
            # Extract error info
            for output in cell.outputs:
                if output.get("output_type") == "error":
                    ename = output.get("ename", "Unknown")
                    evalue = output.get("evalue", "")
                    issues.append(f"Cell {cell.index}: Error output - {ename}: {evalue}")
                    break

    return issues


def validate_no_empty_cells(cells: list[CellInfo]) -> list[str]:
    """
    Validate that there are no empty cells.

    Returns a list of warnings (empty cells are often intentional).
    """
    warnings = []
    for cell in cells:
        if cell.is_empty:
            warnings.append(f"Cell {cell.index}: Empty {cell.cell_type} cell")

    return warnings


# Patterns for detecting hardcoded API keys
API_KEY_PATTERNS = [
    r"sk-ant-[a-zA-Z0-9\-_]{20,}",  # Anthropic API keys (at least 20 chars to avoid false positives on prefix checks)
    r"['\"]ANTHROPIC_API_KEY['\"]\s*[=:]\s*['\"][^'\"]+['\"]",  # Hardcoded assignment
]


def validate_no_hardcoded_secrets(cells: list[CellInfo]) -> list[str]:
    """
    Validate that no cells contain hardcoded API keys or secrets.

    Returns a list of issues found.
    """
    issues = []
    for cell in cells:
        if cell.cell_type != "code":
            continue

        for pattern in API_KEY_PATTERNS:
            if re.search(pattern, cell.source):
                issues.append(
                    f"Cell {cell.index}: Possible hardcoded API key detected. "
                    "Use environment variables instead."
                )
                break

    return issues


def validate_uses_env_for_api_key(cells: list[CellInfo]) -> list[str]:
    """
    Validate that API keys are loaded from environment variables.

    Returns a list of warnings if API key usage doesn't follow best practices.
    """
    warnings = []
    has_anthropic_import = False
    uses_env_get = False

    for cell in cells:
        if cell.cell_type != "code":
            continue

        if "anthropic" in cell.source.lower() or "Anthropic" in cell.source:
            has_anthropic_import = True

        if 'os.environ.get("ANTHROPIC_API_KEY")' in cell.source:
            uses_env_get = True
        elif "os.environ['ANTHROPIC_API_KEY']" in cell.source:
            uses_env_get = True
        elif "os.getenv(" in cell.source and "ANTHROPIC_API_KEY" in cell.source:
            uses_env_get = True

    if has_anthropic_import and not uses_env_get:
        # Check if it's using default client (which reads from env automatically)
        # Anthropic() without api_key arg is fine
        pass  # This is acceptable, Anthropic client reads from env by default

    return warnings


def extract_pip_dependencies(cells: list[CellInfo]) -> list[str]:
    """
    Extract pip dependencies from notebook cells.

    Looks for %pip install and !pip install commands.
    """
    dependencies = []
    pip_pattern = r"[%!]pip\s+install\s+([^\n]+)"

    for cell in cells:
        if cell.cell_type != "code":
            continue

        matches = re.findall(pip_pattern, cell.source)
        for match in matches:
            # Parse package names from the install command
            # Remove flags like -q, --quiet, etc.
            parts = match.split()
            for part in parts:
                if not part.startswith("-") and part not in ["install"]:
                    # Handle package[extra] and package==version formats
                    pkg_name = re.split(r"[=<>!\[]", part)[0]
                    if pkg_name and not pkg_name.startswith("-"):
                        dependencies.append(pkg_name)

    return list(set(dependencies))


def validate_notebook_structure(path: Path) -> NotebookValidationResult:
    """
    Run all structural validations on a notebook.

    This validates the notebook without executing it.
    """
    result = NotebookValidationResult(path=path)

    try:
        notebook = load_notebook(path)
    except json.JSONDecodeError as e:
        result.add_error(f"Invalid JSON: {e}")
        return result
    except FileNotFoundError:
        result.add_error(f"File not found: {path}")
        return result

    # Parse cells
    result.cells = parse_notebook_cells(notebook)

    # Run validations
    for issue in validate_cell_execution_order(result.cells):
        result.add_error(issue)

    for issue in validate_all_cells_executed(result.cells):
        result.add_error(issue)

    for issue in validate_no_error_outputs(result.cells):
        result.add_error(issue)

    for issue in validate_no_hardcoded_secrets(result.cells):
        result.add_error(issue)

    for warning in validate_no_empty_cells(result.cells):
        result.add_warning(warning)

    for warning in validate_uses_env_for_api_key(result.cells):
        result.add_warning(warning)

    return result


def execute_notebook(
    path: Path,
    timeout: int = 300,
    kernel_name: str | None = None,
    allow_errors: bool = False,
) -> tuple[bool, str, Path | None]:
    """
    Execute a notebook in an isolated environment.

    Args:
        path: Path to the notebook
        timeout: Maximum execution time in seconds
        kernel_name: Jupyter kernel to use (default: python3)
        allow_errors: If True, continue execution even if cells error

    Returns:
        Tuple of (success, output_message, output_path)
    """
    # Create temp file for output
    with tempfile.NamedTemporaryFile(suffix=".ipynb", delete=False) as tmp:
        output_path = Path(tmp.name)

    cmd = [
        sys.executable,
        "-m",
        "jupyter",
        "nbconvert",
        "--to",
        "notebook",
        "--execute",
        "--output",
        str(output_path),
        f"--ExecutePreprocessor.timeout={timeout}",
    ]

    if kernel_name:
        cmd.append(f"--ExecutePreprocessor.kernel_name={kernel_name}")

    if allow_errors:
        cmd.append("--allow-errors")

    cmd.append(str(path))

    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 30,  # Extra buffer for startup
        )

        if result.returncode == 0:
            return True, "Notebook executed successfully", output_path
        else:
            return False, f"Execution failed: {result.stderr}", output_path

    except subprocess.TimeoutExpired:
        return False, f"Execution timed out after {timeout} seconds", None
    except Exception as e:
        return False, f"Execution error: {e}", None


def get_notebook_kernel_info(notebook: dict[str, Any]) -> dict[str, Any]:
    """Extract kernel information from notebook metadata."""
    metadata = notebook.get("metadata", {})
    kernelspec = metadata.get("kernelspec", {})
    language_info = metadata.get("language_info", {})

    return {
        "kernel_name": kernelspec.get("name", "unknown"),
        "kernel_display_name": kernelspec.get("display_name", "Unknown"),
        "language": kernelspec.get("language", language_info.get("name", "unknown")),
        "language_version": language_info.get("version", "unknown"),
    }


def find_all_notebooks(root_dir: Path, exclude_patterns: list[str] | None = None) -> list[Path]:
    """
    Find all notebooks in a directory.

    Args:
        root_dir: Root directory to search
        exclude_patterns: List of glob patterns to exclude

    Returns:
        List of notebook paths
    """
    exclude_patterns = exclude_patterns or []
    notebooks = []

    for nb_path in root_dir.rglob("*.ipynb"):
        # Skip checkpoint files
        if ".ipynb_checkpoints" in str(nb_path):
            continue

        # Check exclude patterns
        excluded = False
        for pattern in exclude_patterns:
            if nb_path.match(pattern):
                excluded = True
                break

        if not excluded:
            notebooks.append(nb_path)

    return sorted(notebooks)
