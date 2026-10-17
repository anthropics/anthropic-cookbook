"""
Notebook testing scaffold for Anthropic Cookbook.

This module provides comprehensive tests for Jupyter notebooks including:
- Structure validation (valid JSON, proper notebook format)
- Cell execution order validation
- All cells executed validation
- Error output detection
- Security checks (no hardcoded API keys)
- Dependency detection
- Optional: Full notebook execution in isolated environment
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from tests.notebook_tests.utils import (
    CellInfo,
    execute_notebook,
    extract_pip_dependencies,
    get_notebook_kernel_info,
    validate_all_cells_executed,
    validate_cell_execution_order,
    validate_no_error_outputs,
    validate_no_hardcoded_secrets,
)


class TestNotebookStructure:
    """Tests for notebook structure and format validity."""

    def test_valid_json(self, notebook_path: Path) -> None:
        """Test that the notebook is valid JSON."""
        try:
            with open(notebook_path, encoding="utf-8") as f:
                json.load(f)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON in {notebook_path}: {e}")

    def test_has_cells(self, notebook_data: dict[str, Any]) -> None:
        """Test that the notebook has at least one cell."""
        cells = notebook_data.get("cells", [])
        assert len(cells) > 0, "Notebook has no cells"

    def test_has_code_cells(self, notebook_data: dict[str, Any]) -> None:
        """Test that the notebook has at least one code cell."""
        cells = notebook_data.get("cells", [])
        code_cells = [c for c in cells if c.get("cell_type") == "code"]
        assert len(code_cells) > 0, "Notebook has no code cells"

    def test_valid_cell_types(self, notebook_data: dict[str, Any]) -> None:
        """Test that all cells have valid cell types."""
        valid_types = {"code", "markdown", "raw"}
        cells = notebook_data.get("cells", [])

        for i, cell in enumerate(cells):
            cell_type = cell.get("cell_type")
            assert cell_type in valid_types, f"Cell {i} has invalid type: {cell_type}"

    def test_has_kernel_spec(self, notebook_data: dict[str, Any]) -> None:
        """Test that the notebook has kernel specification."""
        metadata = notebook_data.get("metadata", {})
        kernelspec = metadata.get("kernelspec", {})

        assert kernelspec, "Notebook missing kernelspec in metadata"
        assert kernelspec.get("name"), "Kernel name not specified"

    def test_python_kernel(self, notebook_data: dict[str, Any]) -> None:
        """Test that the notebook uses a Python kernel."""
        kernel_info = get_notebook_kernel_info(notebook_data)
        language = kernel_info.get("language", "").lower()

        assert language == "python", f"Expected Python kernel, got: {language}"


class TestCellExecution:
    """Tests for cell execution status and order."""

    def test_all_cells_executed(self, notebook_cells: list[CellInfo]) -> None:
        """Test that all code cells have been executed."""
        issues = validate_all_cells_executed(notebook_cells)

        if issues:
            pytest.fail(
                f"Found {len(issues)} unexecuted cell(s):\n" + "\n".join(f"  - {i}" for i in issues)
            )

    def test_cells_executed_in_order(self, notebook_cells: list[CellInfo]) -> None:
        """Test that cells were executed in sequential order."""
        issues = validate_cell_execution_order(notebook_cells)

        if issues:
            pytest.fail("Cell execution order issues:\n" + "\n".join(f"  - {i}" for i in issues))

    def test_execution_counts_start_from_one(self, notebook_cells: list[CellInfo]) -> None:
        """Test that execution counts start from 1 (fresh kernel)."""
        code_cells = [c for c in notebook_cells if c.cell_type == "code"]
        exec_counts = [c.execution_count for c in code_cells if c.execution_count is not None]

        if exec_counts:
            min_count = min(exec_counts)
            assert min_count == 1, (
                f"Execution counts should start from 1, but minimum is {min_count}. "
                "This suggests the notebook wasn't run from a fresh kernel."
            )


class TestCellOutputs:
    """Tests for cell outputs and errors."""

    def test_no_error_outputs(self, notebook_cells: list[CellInfo]) -> None:
        """Test that no cells have error outputs."""
        issues = validate_no_error_outputs(notebook_cells)

        if issues:
            pytest.fail("Found error outputs:\n" + "\n".join(f"  - {i}" for i in issues))

    def test_no_empty_code_cells(self, notebook_cells: list[CellInfo]) -> None:
        """Test that there are no empty code cells (warning only)."""
        empty_code_cells = [c for c in notebook_cells if c.cell_type == "code" and c.is_empty]

        if empty_code_cells:
            indices = [str(c.index) for c in empty_code_cells]
            pytest.skip(
                f"Found {len(empty_code_cells)} empty code cell(s) at indices: {', '.join(indices)}"
            )


class TestSecurity:
    """Tests for security best practices."""

    def test_no_hardcoded_api_keys(self, notebook_cells: list[CellInfo]) -> None:
        """Test that no cells contain hardcoded API keys."""
        issues = validate_no_hardcoded_secrets(notebook_cells)

        if issues:
            pytest.fail(
                "Security issue - hardcoded API keys detected:\n"
                + "\n".join(f"  - {i}" for i in issues)
            )

    def test_api_key_from_environment(self, notebook_cells: list[CellInfo]) -> None:
        """Test that API keys are loaded from environment variables."""
        # Check if notebook uses Anthropic
        uses_anthropic = False
        for cell in notebook_cells:
            if cell.cell_type == "code" and "anthropic" in cell.source.lower():
                uses_anthropic = True
                break

        if not uses_anthropic:
            pytest.skip("Notebook doesn't use Anthropic API")

        # Check for hardcoded api_key parameter
        for cell in notebook_cells:
            if cell.cell_type != "code":
                continue
            source = cell.source
            # Check for api_key="..." pattern (hardcoded)
            if 'api_key="sk-' in source or "api_key='sk-" in source:
                pytest.fail(
                    f"Cell {cell.index}: Hardcoded API key in Anthropic client constructor. "
                    "Use environment variables instead."
                )


class TestDependencies:
    """Tests for dependency declarations."""

    def test_pip_installs_at_top(self, notebook_cells: list[CellInfo]) -> None:
        """Test that pip install commands appear early in the notebook."""
        code_cells = [c for c in notebook_cells if c.cell_type == "code"]

        pip_install_indices = []
        for i, cell in enumerate(code_cells):
            if "%pip install" in cell.source or "!pip install" in cell.source:
                pip_install_indices.append(i)

        if not pip_install_indices:
            pytest.skip("No pip install commands found")

        # All pip installs should be in the first 3 code cells
        for idx in pip_install_indices:
            if idx > 2:
                pytest.skip(
                    f"pip install found at code cell {idx}. "
                    "Consider moving dependency installation to the beginning of the notebook."
                )

    def test_dependencies_documented(self, notebook_cells: list[CellInfo]) -> None:
        """Test that dependencies are documented (pip install or markdown mention)."""
        deps = extract_pip_dependencies(notebook_cells)

        if not deps:
            # Check if there's a requirements mention in markdown
            for cell in notebook_cells:
                if cell.cell_type == "markdown":
                    if (
                        "requirements" in cell.source.lower()
                        or "dependencies" in cell.source.lower()
                    ):
                        return

            # No deps and no mention - likely a simple notebook, skip
            pytest.skip("No explicit dependencies found")


class TestNotebookExecution:
    """Tests that actually execute notebooks (optional, slow)."""

    @pytest.mark.slow
    def test_notebook_executes_successfully(
        self,
        notebook_path: Path,
        execute_notebooks: bool,
        notebook_timeout: int,
        has_api_key: bool,
    ) -> None:
        """Test that the notebook executes without errors."""
        if not execute_notebooks:
            pytest.skip("Use --execute-notebooks to run execution tests")

        if not has_api_key:
            pytest.skip("ANTHROPIC_API_KEY not set, skipping execution test")

        success, message, output_path = execute_notebook(
            notebook_path,
            timeout=notebook_timeout,
            allow_errors=False,
        )

        # Clean up output file
        if output_path and output_path.exists():
            output_path.unlink()

        assert success, f"Notebook execution failed: {message}"


class TestNotebookMetadata:
    """Tests for notebook metadata quality."""

    def test_has_title(self, notebook_cells: list[CellInfo]) -> None:
        """Test that the notebook starts with a title (markdown heading)."""
        if not notebook_cells:
            pytest.skip("No cells in notebook")

        first_cell = notebook_cells[0]
        if first_cell.cell_type != "markdown":
            pytest.skip("First cell is not markdown")

        # Check for heading
        source = first_cell.source.strip()
        if not source.startswith("#"):
            pytest.skip("First markdown cell doesn't start with a heading")

    def test_nbformat_version(self, notebook_data: dict[str, Any]) -> None:
        """Test that notebook uses a supported nbformat version."""
        nbformat = notebook_data.get("nbformat", 0)
        assert nbformat >= 4, f"Notebook uses old nbformat {nbformat}, expected 4+"


class TestModelUsage:
    """Tests for Claude model usage."""

    # Current supported models (first-party aliases). Everything else a notebook names in
    # code must be listed in ALLOWED_LEGACY_MODELS with a reason.
    CURRENT_MODELS = {
        "claude-opus-5-5",
        "claude-sonnet-5-5",
        "claude-fable-5-1",
        "claude-haiku-4-5",
    }

    # Bedrock base IDs for the current models (see CLAUDE.md). Regional prefixes such as
    # `global.` and context-window suffixes such as `:200k` are stripped before comparing.
    # Haiku 4.5 is listed in both forms: the dated `-v1:0` ID used with InvokeModel and the
    # alias used with the Messages-API endpoint.
    CURRENT_BEDROCK_MODELS = {
        "anthropic.claude-opus-5-5",
        "anthropic.claude-sonnet-5-5",
        "anthropic.claude-fable-5-1",
        "anthropic.claude-haiku-4-5",
        "anthropic.claude-haiku-4-5-20251001-v1:0",
    }

    # Older IDs that specific notebooks pin on purpose because the content is tied to that
    # model (pricing math, recorded eval results, model-specific billing behaviour). Keyed by
    # notebook path (relative to the repo root) so a legacy ID allowed in one notebook is still
    # flagged everywhere else; keep in sync with PINNED_LEGACY_NOTEBOOKS in
    # scripts/validate_all_notebooks.py (model tables are also mirrored in
    # .claude/skills/cookbook-audit/validate_notebook.py).
    ALLOWED_LEGACY_MODELS: dict[str, set[str]] = {
        # Pricing math and recorded cost/latency results for the Fable 5 / Opus 5 / Sonnet 5
        # generation; needs a full re-run to move.
        "cost_optimization/cost_optimization.ipynb": {
            "claude-fable-5",
            "claude-opus-5",
            "claude-sonnet-5",
        },
        # GRADER_MODEL that produced the published benchmark numbers (eval methodology).
        "evals/agentic_search/reproduce_agentic_search_benchmarks.ipynb": {"claude-opus-4-6"},
        # The Fable 5 -> Opus 4.8 classifier-fallback and billing behaviour it documents is
        # specific to these two models.
        "fable_5_fallback_billing/guide.ipynb": {"claude-fable-5", "claude-opus-4-8"},
        # Recorded chart-reading benchmark results and costs are for Fable 5 / Sonnet 5.
        "multimodal/crop_tool.ipynb": {"claude-fable-5", "claude-sonnet-5"},
    }

    # Whole model IDs in code cells: first-party `claude-<family>-...` and legacy
    # `claude-3[-x]-<family>-...` IDs, optionally carrying a Bedrock `[region.]anthropic.`
    # prefix. The boundaries keep `claude-opus-5` from matching inside `claude-opus-5-5` and
    # skip templated IDs such as `claude-opus-{version}`; requiring a family name skips
    # look-alikes such as a `claude-3-rag` index name.
    CLAUDE_MODEL_PATTERN = re.compile(
        r"(?<![\w.-])"
        r"(?:(?:[a-z]{2,6}\.)?anthropic\.)?"
        r"claude-(?:3(?:-[57])?-)?(?:opus|sonnet|haiku|fable|mythos)(?:[-:][a-z0-9]+)+"
        r"(?![\w-])"
    )

    @classmethod
    def _is_allowed_model(cls, model_id: str, allowed_legacy: set[str]) -> bool:
        if "anthropic." in model_id:
            base = model_id[model_id.index("anthropic.") :]  # drop regional prefix
            base = re.sub(r":\d+k$", "", base)  # drop context-window suffix (e.g. :200k)
            return base in cls.CURRENT_BEDROCK_MODELS
        return model_id in cls.CURRENT_MODELS or model_id in allowed_legacy

    def test_no_deprecated_models(
        self, notebook_path: Path, project_root: Path, notebook_cells: list[CellInfo]
    ) -> None:
        """Test that code cells only name current Claude models (or an allowed legacy pin)."""
        rel_path = notebook_path.resolve().relative_to(project_root.resolve()).as_posix()
        allowed_legacy = self.ALLOWED_LEGACY_MODELS.get(rel_path, set())
        issues = []

        for cell in notebook_cells:
            if cell.cell_type != "code":
                continue

            for model_id in sorted(set(self.CLAUDE_MODEL_PATTERN.findall(cell.source))):
                if not self._is_allowed_model(model_id, allowed_legacy):
                    issues.append(f"Cell {cell.index}: Found non-current model '{model_id}'")

        if issues:
            pytest.fail(
                "Deprecated or non-current Claude models detected:\n"
                + "\n".join(f"  - {i}" for i in issues)
                + "\n\nPlease use one of the current models: "
                + ", ".join(sorted(self.CURRENT_MODELS))
                + " (or add a documented, per-notebook exception to"
                " TestModelUsage.ALLOWED_LEGACY_MODELS)."
            )


class TestCookbookAttribution:
    """Tests for the anthropic_cookbook tag on Managed Agents."""

    # Attribution only counts a tag that matches this shape. Anything else is
    # ignored with no error, so a typo would lose attribution unnoticed.
    SLUG_PATTERN = r"[a-z0-9][a-z0-9-]{0,63}"

    def test_agents_carry_cookbook_tag(
        self, notebook_path: Path, notebook_cells: list[CellInfo]
    ) -> None:
        """Test that every agents.create call tags the agent with this cookbook."""
        import ast
        import re

        name = re.sub(r"[^a-z0-9]+", "-", notebook_path.stem.lower()).strip("-")
        expected = f"claude-cookbooks/{name}"

        calls = 0
        issues = []

        for cell in notebook_cells:
            if cell.cell_type != "code" or "agents.create" not in cell.source:
                continue

            # IPython magics and shell escapes are not Python, so blank them out.
            source = re.sub(r"^(\s*)[%!].*$", r"\1pass", cell.source, flags=re.MULTILINE)
            try:
                tree = ast.parse(source)
            except SyntaxError as e:
                issues.append(f"Cell {cell.index}: could not parse the cell ({e.msg})")
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not ast.unparse(node.func).endswith("agents.create"):
                    continue

                calls += 1
                where = f"Cell {cell.index}, line {node.lineno}"
                metadata = next((kw.value for kw in node.keywords if kw.arg == "metadata"), None)
                if metadata is None:
                    issues.append(f"{where}: no metadata argument")
                    continue

                try:
                    value = ast.literal_eval(metadata)
                except ValueError:
                    value = None
                if not isinstance(value, dict):
                    # A variable or a spread can't be checked without running the cell.
                    issues.append(f"{where}: metadata must be a plain dict literal")
                    continue

                tag = value.get("anthropic_cookbook")
                if tag != expected:
                    issues.append(f"{where}: anthropic_cookbook is {tag!r}")

        if calls:
            assert re.fullmatch(self.SLUG_PATTERN, name), f"Notebook name makes a bad slug: {name}"

        if issues:
            pytest.fail(
                f'agents.create calls need metadata={{"anthropic_cookbook": "{expected}"}}:\n'
                + "\n".join(f"  - {i}" for i in issues)
            )
