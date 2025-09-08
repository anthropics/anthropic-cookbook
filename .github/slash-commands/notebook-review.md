---
description: Comprehensive review of Jupyter notebooks and Python scripts
---

Review the changes to Jupyter notebooks and Python scripts in this PR. Please check for:

## Model Usage
Verify all Claude model references against the current list at:
https://docs.anthropic.com/en/docs/about-claude/models/overview.md
- Flag any deprecated models (older Sonnet 3.5, Opus 3 versions)
- Flag any internal/non-public model names
- Suggest current alternatives when issues found
- Recommend aliases ending in -latest for stability

## Code Quality
- Python code follows PEP 8 conventions
- Proper error handling
- Clear variable names and documentation
- No hardcoded API keys (use os.getenv("ANTHROPIC_API_KEY"))

## Notebook Structure
- Clear introduction explaining what the notebook demonstrates and why it's useful
- Configuration instructions (how to set up API keys, install dependencies, etc.)
- Connecting explanations between cells that help users understand the flow
- Clear markdown explanations between code cells
- Logical flow from simple to complex
- Outputs preserved for educational value
- Dependencies properly imported

## Security
- Check for any hardcoded API keys or secrets (not just Anthropic keys)
- Ensure all sensitive credentials use environment variables (os.environ, getenv, etc.)
- Flag any potential secret patterns (tokens, passwords, private keys)
- Note: Educational examples showing "what not to do" are acceptable if clearly marked
- Safe handling of user inputs
- Appropriate use of environment variables

Provide a clear summary with:
- ✅ What looks good
- ⚠️ Suggestions for improvement
- ❌ Critical issues that must be fixed

Format your response as a helpful PR review comment.