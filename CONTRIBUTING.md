# Contributing to Anthropic Cookbook

Thank you for your interest in contributing to the Anthropic Cookbook! This guide will help you get started with development and ensure your contributions meet our quality standards.

## Development Setup

### Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended) or pip

### Quick Start

1. **Install uv** (recommended package manager):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
   
   Or with Homebrew:
   ```bash
   brew install uv
   ```

2. **Clone the repository**:
   ```bash
   git clone https://github.com/anthropics/anthropic-cookbook.git
   cd anthropic-cookbook
   ```

3. **Set up the development environment**:
   ```bash
   # Create virtual environment and install dependencies
   uv sync --all-extras
   
   # Or with pip:
   pip install -e ".[dev]"
   ```

4. **Install pre-commit hooks**:
   ```bash
   uv run pre-commit install
   # Or: pre-commit install
   ```

5. **Set up your API key**:
   ```bash
   cp .env.example .env
   # Edit .env and add your Anthropic API key
   ```

## Quality Standards

This repository uses automated tools to maintain code quality:

### The Notebook Validation Stack

- **[nbconvert](https://nbconvert.readthedocs.io/)**: Notebook execution for testing
- **[ruff](https://docs.astral.sh/ruff/)**: Fast Python linter and formatter with native Jupyter support
- **Claude AI Review**: Intelligent code review using Claude

**Note**: Notebook outputs are intentionally kept in this repository as they demonstrate expected results for users.

### Claude Code Slash Commands

This repository includes slash commands that work in both Claude Code (for local development) and GitHub Actions CI. These commands are automatically available when you work in this repository with Claude Code.

**Available Commands**:
- `/link-review` - Validate links in markdown and notebooks
- `/model-check` - Verify Claude model usage is current
- `/notebook-review` - Comprehensive notebook quality check

**Usage in Claude Code**:
```bash
# Run the same validations that CI will run
/notebook-review skills/my-notebook.ipynb
/model-check
/link-review README.md
```

These commands use the exact same validation logic as our CI pipeline, helping you catch issues before pushing. The command definitions are stored in `.claude/commands/` for both local and CI use.

### Before Committing

1. **Run quality checks**:
   ```bash
   uv run ruff check skills/ --fix
   uv run ruff format skills/
   
   uv run python scripts/validate_notebooks.py
   ```

3. **Test notebook execution** (optional, requires API key):
   ```bash
   uv run jupyter nbconvert --to notebook \
     --execute skills/classification/guide.ipynb \
     --ExecutePreprocessor.kernel_name=python3 \
     --output test_output.ipynb
   ```

### Pre-commit Hooks

Pre-commit hooks will automatically run before each commit to ensure code quality:

- Format code with ruff
- Validate notebook structure

If a hook fails, fix the issues and try committing again.

## Contribution Guidelines

### Notebook Best Practices

1. **Use environment variables for API keys**:
   ```python
   import os
   api_key = os.environ.get("ANTHROPIC_API_KEY")
   ```

2. **Use current Claude models**:
   - Use model aliases (e.g., `claude-3-5-haiku-latest`) for better maintainability
   - Check current models at: https://docs.anthropic.com/en/docs/about-claude/models/overview
   - Claude will automatically validate model usage in PR reviews

3. **Keep notebooks focused**:
   - One concept per notebook
   - Clear explanations and comments
   - Include expected outputs as markdown cells

4. **Test your notebooks**:
   - Ensure they run from top to bottom without errors
   - Use minimal tokens for example API calls
   - Include error handling

### Git Workflow

1. **Create a feature branch**:
   ```bash
   git checkout -b <your-name>/<feature-description>
   # Example: git checkout -b alice/add-rag-example
   ```

2. **Use conventional commits**:
   ```bash
   # Format: <type>(<scope>): <subject>
   
   # Types:
   feat     # New feature
   fix      # Bug fix
   docs     # Documentation
   style    # Formatting
   refactor # Code restructuring
   test     # Tests
   chore    # Maintenance
   ci       # CI/CD changes
   
   # Examples:
   git commit -m "feat(skills): add text-to-sql notebook"
   git commit -m "fix(api): use environment variable for API key"
   git commit -m "docs(readme): update installation instructions"
   ```

3. **Keep commits atomic**:
   - One logical change per commit
   - Write clear, descriptive messages
   - Reference issues when applicable

4. **Push and create PR**:
   ```bash
   git push -u origin your-branch-name
   gh pr create  # Or use GitHub web interface
   ```

### Pull Request Guidelines

1. **PR Title**: Use conventional commit format
2. **Description**: Include:
   - What changes you made
   - Why you made them
   - How to test them
   - Related issue numbers
3. **Keep PRs focused**: One feature/fix per PR
4. **Respond to feedback**: Address review comments promptly

## Testing

### Local Testing

Run the validation suite:

```bash
# Check all notebooks
uv run python scripts/validate_notebooks.py

# Run pre-commit on all files
uv run pre-commit run --all-files
```

### CI/CD

Our GitHub Actions workflows will automatically:

- Validate notebook structure
- Lint code with ruff
- Test notebook execution (for maintainers)
- Check links
- Claude reviews code and model usage

External contributors will have limited API testing to conserve resources.

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/anthropics/anthropic-cookbook/issues)
- **Discussions**: [GitHub Discussions](https://github.com/anthropics/anthropic-cookbook/discussions)
- **Discord**: [Anthropic Discord](https://www.anthropic.com/discord)

## Security

- Never commit API keys or secrets
- Use environment variables for sensitive data
- Report security issues privately to security@anthropic.com

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT License).