#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "nbconvert",
# ]
# ///
"""
Automated validation checks for Anthropic Cookbook notebooks.
Run this before manual review to catch common issues.

Usage:
    python validate_notebook.py <notebook.ipynb>

Exit codes:
    0 - No issues found
    1 - Critical issues found (must fix)
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


class NotebookValidator:
    def __init__(self, notebook_path: str):
        self.notebook_path = Path(notebook_path)
        self.issues: list[str] = []
        self.warnings: list[str] = []
        self.markdown_output: Path | None = None

        if not self.notebook_path.exists():
            raise FileNotFoundError(f"Notebook not found: {notebook_path}")

        with open(self.notebook_path, encoding="utf-8") as f:
            self.nb = json.load(f)

        self.cells = self.nb.get("cells", [])

    def get_cell_source(self, cell: dict) -> str:
        """Get cell source as a single string."""
        source = cell.get("source", [])
        if isinstance(source, list):
            return "".join(source)
        return source

    def convert_to_markdown(self) -> Path:
        """
        Convert notebook to markdown for easier review.
        Returns path to the markdown file in a temp directory.
        Includes code cells but excludes outputs to save context.
        Uses uv to run jupyter nbconvert with dependencies.
        """
        # Create temp directory within skill folder
        skill_dir = Path(__file__).parent
        temp_dir = skill_dir / "tmp"
        temp_dir.mkdir(exist_ok=True)

        # Generate output filename
        output_file = temp_dir / f"{self.notebook_path.stem}_review.md"

        # Use uv to run jupyter nbconvert with nbconvert dependency
        # Include code but exclude outputs for cleaner review
        cmd = [
            "uv",
            "run",
            "--with",
            "nbconvert",
            "jupyter",
            "nbconvert",
            "--to",
            "markdown",
            "--output",
            str(output_file.absolute()),
            "--no-prompt",  # Remove input/output prompts
            "--TemplateExporter.exclude_output=True",  # Exclude cell outputs
            str(self.notebook_path.absolute()),
        ]

        subprocess.run(cmd, capture_output=True, text=True, check=True)  # noqa: S603

        self.markdown_output = output_file
        return output_file

    def check_hardcoded_secrets(self):
        """Check for hardcoded API keys and secrets using detect-secrets."""
        # The command below is run through `sh -c`, so a missing `uvx` fails inside
        # the shell rather than raising FileNotFoundError here. Check for it up front,
        # otherwise the `except FileNotFoundError` fallback below is unreachable and a
        # machine without uv reports every notebook as containing secrets.
        if shutil.which("uvx") is None:
            self.warnings.append(
                "detect-secrets not available (uvx not found) - using basic secret "
                "detection. Install uv: https://github.com/astral-sh/uv"
            )
            self._check_hardcoded_secrets_fallback()
            return

        try:
            # Run detect-secrets on the notebook file
            # Use absolute path to ensure it works regardless of cwd
            notebook_abs = self.notebook_path.absolute()

            # Find project root (look for .git or go up until we find it)
            project_root = notebook_abs.parent
            while project_root.parent != project_root:
                if (project_root / ".git").exists():
                    break
                project_root = project_root.parent

            # Check for baseline in multiple locations
            baseline_paths = [
                project_root / "scripts" / "detect-secrets" / ".secrets.baseline",
                project_root / ".secrets.baseline",
            ]
            baseline_path = None
            for path in baseline_paths:
                if path.exists():
                    baseline_path = path
                    break

            plugins_path = project_root / "scripts" / "detect-secrets" / "plugins.py"

            # Build command with baseline if it exists
            if baseline_path:
                cmd = [
                    "sh",
                    "-c",
                    f"echo '{notebook_abs}' | tr '\\n' '\\0' | xargs -0 uvx --from detect-secrets detect-secrets-hook --baseline {baseline_path} --plugin {plugins_path} --verbose",
                ]
            else:
                cmd = [
                    "sh",
                    "-c",
                    f"echo '{notebook_abs}' | tr '\\n' '\\0' | xargs -0 uvx --from detect-secrets detect-secrets-hook",
                ]

            result = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                cwd=project_root,  # Run from repo root for scripts/detect-secrets access
            )

            # 127 is the shell's "command not found"; the tool never ran, so there is
            # nothing to report about the notebook itself.
            if result.returncode == 127:
                self.warnings.append(
                    "detect-secrets could not be run - using basic secret detection."
                )
                self._check_hardcoded_secrets_fallback()
                return

            # detect-secrets returns non-zero exit code if secrets found
            if result.returncode != 0:
                # Check both stdout and stderr for output (detect-secrets uses stdout)
                output = result.stdout.strip() or result.stderr.strip()

                if output:
                    # Extract secret locations from output
                    secret_lines = [
                        line
                        for line in output.split("\n")
                        if "Location:" in line or "Secret Type:" in line
                    ]

                    if secret_lines:
                        self.issues.append(
                            "Contains potential hardcoded secrets (see details below)"
                        )
                        # Print the full detect-secrets output for review
                        print(f"\n{'=' * 60}")
                        print("DETECT-SECRETS OUTPUT:")
                        print(f"{'=' * 60}")
                        print(output)
                        print(f"{'=' * 60}\n")
                    else:
                        self.issues.append(
                            f"Contains potential secrets. "
                            f"Run 'detect-secrets-hook {self.notebook_path}' for details."
                        )
                else:
                    self.issues.append(
                        f"Potential secrets detected. "
                        f"Run 'detect-secrets-hook {self.notebook_path}' for details."
                    )

        except FileNotFoundError:
            # Fall back to basic pattern matching if detect-secrets not available
            self.warnings.append(
                "detect-secrets not found - using basic secret detection. "
                "Install with: pip install detect-secrets"
            )
            self._check_hardcoded_secrets_fallback()
        except Exception as e:
            self.warnings.append(f"Error running detect-secrets: {e}")
            self._check_hardcoded_secrets_fallback()

    def _check_hardcoded_secrets_fallback(self):
        """Fallback basic secret detection if detect-secrets unavailable."""
        patterns = {
            "Anthropic API key": r"sk-ant-[a-zA-Z0-9-]+",
            "OpenAI API key": r"sk-[a-zA-Z0-9]{32,}",
            "Generic secret": r'(secret|password|token)\s*=\s*["\'][^"\']{20,}["\']',
        }

        for i, cell in enumerate(self.cells):
            source = self.get_cell_source(cell)
            for secret_type, pattern in patterns.items():
                if re.search(pattern, source, re.IGNORECASE):
                    self.issues.append(f"Cell {i}: Contains hardcoded {secret_type}")

    def check_introduction(self):
        """Check for proper introduction."""
        if not self.cells:
            self.issues.append("Notebook is empty")
            return

        first_cell = self.cells[0]
        if first_cell.get("cell_type") != "markdown":
            self.issues.append("First cell is not markdown (should be introduction)")
            return

        intro_text = self.get_cell_source(first_cell)

        # Check for minimum length
        if len(intro_text) < 200:
            self.warnings.append(
                "Introduction seems too short (< 200 chars). Should include "
                "problem statement, audience, and what will be accomplished"
            )

        # Check for key elements
        has_prerequisites = bool(
            re.search(r"prerequisite|requirement|need|require", intro_text, re.IGNORECASE)
        )
        if not has_prerequisites:
            self.warnings.append("Introduction doesn't mention prerequisites")

    def check_pip_install_output(self):
        """Check that pip install outputs are suppressed."""
        for i, cell in enumerate(self.cells):
            if cell.get("cell_type") != "code":
                continue

            source = self.get_cell_source(cell)
            has_pip_install = "pip install" in source
            has_capture = "%%capture" in source or "%pip install" in source

            if has_pip_install and not has_capture:
                self.warnings.append(
                    f"Cell {i}: pip install without output suppression (use %%capture or %pip)"
                )

    def check_code_explanations(self):
        """Check that code blocks have explanatory text before them."""
        prev_cell_type = None

        for i, cell in enumerate(self.cells):
            cell_type = cell.get("cell_type")

            if cell_type == "code" and prev_cell_type == "code":
                # Two code cells in a row - might be missing explanation
                source = self.get_cell_source(cell)
                # Skip if it's just a simple continuation (e.g., print statement)
                if source.strip() and not source.strip().startswith("#"):
                    self.warnings.append(
                        f"Cell {i}: Code cell without preceding markdown "
                        "explanation (two code cells in a row)"
                    )

            prev_cell_type = cell_type

    def check_verbose_output(self):
        """Check for verbose debug output."""
        verbose_patterns = [
            r'print\(["\']debug',
            r"\.debug\(",
            r"verbose\s*=\s*True",
        ]

        for i, cell in enumerate(self.cells):
            if cell.get("cell_type") != "code":
                continue

            source = self.get_cell_source(cell)
            for pattern in verbose_patterns:
                if re.search(pattern, source, re.IGNORECASE):
                    self.warnings.append(f"Cell {i}: Contains verbose debug output")

    def check_variable_names(self):
        """Check for poor variable naming."""
        poor_names = [r"\bx\d*\b", r"\btemp\d*\b", r"\bresult\d*\b", r"\bdata\d*\b"]

        for i, cell in enumerate(self.cells):
            if cell.get("cell_type") != "code":
                continue

            source = self.get_cell_source(cell)
            for pattern in poor_names:
                matches = re.findall(pattern, source)
                if matches:
                    self.warnings.append(
                        f"Cell {i}: Contains unclear variable names: {', '.join(set(matches))}"
                    )
                    break  # Only warn once per cell

    def check_model_constant(self):
        """Check that model name is defined as a constant at the top."""
        model_constant_pattern = r'(MODEL|model|MODEL_NAME|model_name)\s*=\s*["\']claude-'

        # Check first 5 code cells for model constant definition
        code_cells_checked = 0
        found_constant = False

        for cell in self.cells:
            if cell.get("cell_type") != "code":
                continue

            code_cells_checked += 1
            if code_cells_checked > 5:
                break

            source = self.get_cell_source(cell)
            if re.search(model_constant_pattern, source):
                found_constant = True
                break

        if not found_constant:
            # Check if there are any model references at all
            has_model_refs = False
            for cell in self.cells:
                if cell.get("cell_type") != "code":
                    continue
                source = self.get_cell_source(cell)
                if re.search(r'["\']claude-', source):
                    has_model_refs = True
                    break

            if has_model_refs:
                self.warnings.append(
                    "Model name should be defined as a constant at the top of the notebook "
                    "(e.g., MODEL = 'claude-sonnet-4-6') to make future updates easier"
                )

    def check_deprecated_patterns(self):
        """Check for deprecated API patterns and invalid models."""
        # Valid models
        valid_models = [
            "claude-fable-5",
            "claude-sonnet-5",
            "claude-opus-4-8",
            "claude-sonnet-4-6",
            "claude-haiku-4-5",
            "claude-opus-4-6",
        ]

        # Pattern to match model strings
        model_pattern = r'["\']claude-([a-z0-9\.-]+)["\']'

        # Deprecated models that should be migrated
        deprecated_models = {
            "claude-opus-4-1": "claude-opus-4-6",
        }

        deprecated_patterns = {
            r"\.completion\(": "Using old completion API (use messages API)",
        }

        for i, cell in enumerate(self.cells):
            if cell.get("cell_type") != "code":
                continue

            source = self.get_cell_source(cell)

            # Check for dated API model IDs (exclude Bedrock IDs which require dates)
            dated_pattern = r'["\']claude-\w+-[\d.]+-\d{8}["\']'
            dated_matches = re.findall(dated_pattern, source)
            for match in dated_matches:
                # Skip Bedrock model IDs (anthropic.claude-*) which require dates
                if f"anthropic.{match.strip(chr(34)).strip(chr(39))}" not in source:
                    self.issues.append(
                        f"Cell {i}: Dated model ID {match} found. "
                        "Use non-dated aliases instead (e.g., claude-sonnet-4-6)"
                    )

            # Check for invalid or deprecated models
            model_matches = re.findall(model_pattern, source)
            for match in model_matches:
                full_model = f"claude-{match}"
                if full_model in deprecated_models:
                    self.warnings.append(
                        f"Cell {i}: Deprecated model '{full_model}'. "
                        f"Please update to '{deprecated_models[full_model]}'"
                    )
                elif full_model not in valid_models:
                    self.issues.append(
                        f"Cell {i}: Invalid model '{full_model}'. "
                        f"Valid models are: {', '.join(valid_models)}"
                    )

            # Check for other deprecated patterns
            for pattern, message in deprecated_patterns.items():
                if re.search(pattern, source):
                    self.warnings.append(f"Cell {i}: {message}")

    def check_conclusion(self):
        """Check for a conclusion section."""
        if len(self.cells) < 3:
            return  # Too short to require conclusion

        # Check last few cells for conclusion-like content
        last_markdown = None
        for cell in reversed(self.cells[-5:]):
            if cell.get("cell_type") == "markdown":
                last_markdown = self.get_cell_source(cell)
                break

        if not last_markdown:
            self.warnings.append("No conclusion or summary section found")
        elif len(last_markdown) < 100:
            self.warnings.append("Conclusion section seems too brief")

    def run_all_checks(self):
        """Run all validation checks."""
        self.check_hardcoded_secrets()
        self.check_introduction()
        self.check_pip_install_output()
        self.check_code_explanations()
        self.check_verbose_output()
        self.check_variable_names()
        self.check_model_constant()
        self.check_deprecated_patterns()
        self.check_conclusion()

    def print_report(self):
        """Print validation report."""
        print(f"\n{'=' * 60}")
        print(f"Validation Report: {self.notebook_path.name}")
        print(f"{'=' * 60}\n")

        if self.markdown_output and self.markdown_output.exists():
            print(f"📄 Markdown review file: {self.markdown_output}")
            print("   (More readable format for detailed review)\n")

        if self.issues:
            print("CRITICAL ISSUES (must fix):")
            for issue in self.issues:
                print(f"  ❌ {issue}")
            print()

        if self.warnings:
            print("WARNINGS (should review):")
            for warning in self.warnings:
                print(f"  ⚠️  {warning}")
            print()

        if not self.issues and not self.warnings:
            print("✅ No automated issues found!\n")
            print("Note: This doesn't replace manual review for:")
            print("  - Content quality and narrative flow")
            print("  - Technical accuracy of explanations")
            print("  - Appropriateness of examples")
            print("  - Overall pedagogical effectiveness")

        print(f"\n{'=' * 60}")
        print(f"Summary: {len(self.issues)} critical issues, {len(self.warnings)} warnings")
        print(f"{'=' * 60}\n")

    def get_exit_code(self) -> int:
        """Return appropriate exit code."""
        return 1 if self.issues else 0


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run --with nbconvert validate_notebook.py <notebook.ipynb>")
        print("\nValidates a Jupyter notebook against Anthropic Cookbook standards.")
        print("Returns exit code 1 if critical issues found, 0 otherwise.")
        print("\nRequires: uv (https://github.com/astral-sh/uv)")
        sys.exit(1)

    notebook_path = sys.argv[1]

    try:
        validator = NotebookValidator(notebook_path)

        # Convert to markdown for easier review
        print("Converting notebook to markdown for review...")
        validator.convert_to_markdown()

        # Run validation checks
        validator.run_all_checks()
        validator.print_report()
        sys.exit(validator.get_exit_code())

    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: {notebook_path} is not a valid JSON file")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
