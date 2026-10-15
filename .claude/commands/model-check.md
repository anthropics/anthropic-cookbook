---
allowed-tools: Bash(gh pr comment:*),Bash(gh pr diff:*),Bash(gh pr view:*)
description: Validate Claude model usage against current public models
---

**IMPORTANT**: Only review the files explicitly listed in the prompt above. Do not search for or review additional files.

Review the specified changed files for Claude model usage.

First, fetch the current list of allowed models from:
https://platform.claude.com/docs/en/about-claude/models/overview.md

Then check:
1. All model references are from the current public models list (currently `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-fable-5-1`, `claude-haiku-4-5`; trust the fetched page if it differs)
2. Distinguish two kinds of older model and say which one you found:
   - **Superseded** (still served, but a newer model exists in the same family, e.g. `claude-opus-5`, `claude-opus-4-8`, `claude-sonnet-5`, `claude-sonnet-4-6`, `claude-fable-5`): recommend updating to the latest in that family, unless the file pins it for a documented reason (pricing tables, recorded eval/benchmark results, model-specific billing behaviour), in which case note the pin and move on
   - **Retired or deprecated** (the model-deprecations page lists it as Retired or Deprecated, e.g. any `claude-3-*` ID, `claude-opus-4-0`, `claude-opus-4-1`, `claude-sonnet-4-0`, `claude-sonnet-4-5`): flag as must-fix, since requests to it fail now or will after the retirement date; check https://platform.claude.com/docs/en/about-claude/model-deprecations.md when unsure which bucket a model is in
3. Flag any internal/non-public model names
4. Suggest the non-dated alias (e.g. `claude-sonnet-5-5`), never dated IDs like `claude-sonnet-4-5-20250929`

Provide clear, actionable feedback on any issues found.

**IMPORTANT: Post your findings as a comment on the pull request using the command: `gh pr comment $PR_NUMBER --body "your findings"`**