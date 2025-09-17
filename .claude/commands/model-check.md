---
allowed-tools: Bash(gh pr comment:*),Bash(gh pr diff:*),Bash(gh pr view:*)
description: Validate Claude model usage against current public models
---

Review the changed files for Claude model usage.

First, fetch the current list of allowed models from:
https://docs.claude.com/en/docs/about-claude/models/overview.md

Then check:
1. All model references are from the current public models list
2. Flag any deprecated models (older Sonnet 3.5, Opus 3 versions)
3. Flag any internal/non-public model names
4. Suggest using aliases ending in -latest for better maintainability

Provide clear, actionable feedback on any issues found.

**IMPORTANT: Post your findings as a comment on the pull request using the command: `gh pr comment $PR_NUMBER --body "your findings"`**