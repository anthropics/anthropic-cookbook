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

- **[papermill](https://papermill.readthedocs.io/)**: Parameterized notebook execution for testing
- **[nbqa](https://nbqa.readthedocs.io/)**: Applies Python quality tools to notebooks
- **[nbstripout](https://github.com/kynan/nbstripout)**: Keeps notebooks clean in git (removes outputs)
- **[ruff](https://docs.astral.sh/ruff/)**: Fast Python linter and formatter

### Before Committing

1. **Clean notebook outputs**:
   ```bash
   uv run nbstripout skills/**/*.ipynb
   ```

2. **Run quality checks**:
   ```bash
   # Lint and format
   uv run nbqa ruff skills/ --fix
   
   # Validate notebook structure
   uv run python scripts/validate_notebooks.py
   
   # Check model usage
   uv run python scripts/check_models.py
   ```

3. **Test notebook execution** (optional, requires API key):
   ```bash
   uv run papermill skills/classification/guide.ipynb test.ipynb \
     -p model "claude-3-5-haiku-latest" \
     -p test_mode true \
     -p max_tokens 10
   ```

### Pre-commit Hooks

Pre-commit hooks will automatically run before each commit to ensure code quality:

- Strip notebook outputs
- Format code with ruff
- Validate notebook structure
- Check for hardcoded API keys
- Validate Claude model usage

If a hook fails, fix the issues and try committing again.

## Contribution Guidelines

### Notebook Best Practices

1. **Use environment variables for API keys**:
   ```python
   import os
   api_key = os.environ.get("ANTHROPIC_API_KEY")
   ```

2. **Use current Claude models**:
   - For examples: `claude-3-5-haiku-latest` (fast and cheap)
   - For powerful tasks: `claude-opus-4-1`
   - Check allowed models in `scripts/allowed_models.py`

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

# Check model usage
uv run python scripts/check_models.py

# Run pre-commit on all files
uv run pre-commit run --all-files
```

### CI/CD

Our GitHub Actions workflows will automatically:

- Validate notebook structure
- Check for hardcoded secrets
- Lint code with ruff
- Test notebook execution (for maintainers)
- Check links
- Validate Claude model usage

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