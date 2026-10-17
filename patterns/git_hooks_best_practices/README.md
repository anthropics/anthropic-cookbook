# Git Hooks Best Practices with Claude Code

This cookbook demonstrates how to prevent Claude Code from bypassing your git hooks using the `--no-verify` flag.

## Overview

Git hooks are essential for maintaining code quality (linting, testing, formatting, etc.). However, Claude Code can bypass these hooks by using `git commit --no-verify`, which defeats the purpose of these quality checks.

## Problem

When you ask Claude Code to commit changes, it might use `git commit --no-verify` to avoid pre-commit hook failures. This allows code that doesn't meet your quality standards to be committed.

## Solution

Use [`block-no-verify`](https://www.npmjs.com/package/block-no-verify) to prevent bypassing git hooks. This package monitors git commands and blocks execution when the `--no-verify` or `-n` flag is detected.

## Installation

### Step 1: Install block-no-verify

```bash
npm install -g block-no-verify
```

Or use it via npx (no installation required):

```bash
npx block-no-verify
```

### Step 2: Configure Claude Code Hooks

Create or edit `.claude/settings.json` in your project root:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "npx block-no-verify"
          }
        ]
      }
    ]
  }
}
```

## How It Works

1. **PreToolUse Hook**: Before Claude Code executes any bash command, it runs `npx block-no-verify`
2. **Monitoring**: `block-no-verify` monitors the git command about to be executed
3. **Blocking**: If `--no-verify` or `-n` flag is detected, the command is blocked
4. **Protection**: Claude Code must run git commands normally, ensuring your hooks are executed

## Supported Git Commands

`block-no-verify` protects these git commands:
- `commit`
- `push`
- `merge`
- `cherry-pick`
- `rebase`
- `am`

## Example Usage

### Without block-no-verify

```bash
# Claude Code might run:
git commit --no-verify -m "Add new feature"
# Result: Hooks bypassed, untested code committed ❌
```

### With block-no-verify

```bash
# Claude Code tries to run:
git commit --no-verify -m "Add new feature"
# Result: Command blocked, must run without --no-verify ✅

# Instead, Claude Code runs:
git commit -m "Add new feature"
# Result: All hooks executed, code quality maintained ✅
```

## Testing

Test your setup by asking Claude Code to commit changes:

```
Please commit these changes with the message "Add user authentication"
```

Claude Code should run:
```bash
git commit -m "Add user authentication"
```

And NOT:
```bash
git commit --no-verify -m "Add user authentication"
```

## Benefits

- ✅ Enforces code quality checks (linting, testing, formatting)
- ✅ Prevents bypass of pre-commit hooks
- ✅ No changes needed to existing git hooks setup
- ✅ Works with all hook systems (husky, pre-commit, etc.)
- ✅ Lightweight (MIT licensed, minimal dependency)

## Configuration Options

### Alternative: Project-Local Installation

If you prefer not to use npx:

```bash
npm install block-no-verify
```

Then update `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "npx block-no-verify"
          }
        ]
      }
    ]
  }
}
```

### Combining with Other Hooks

You can combine `block-no-verify` with other hooks in the PreToolUse stage:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "npx block-no-verify"
          },
          {
            "type": "command",
            "command": "echo 'Running git command...'"
          }
        ]
      }
    ]
  }
}
```

## Troubleshooting

### Q: What if Claude Code needs to bypass hooks for a valid reason?

If you intentionally need to bypass hooks (e.g., for a fix-up commit during rebase), you can temporarily disable the Claude Code hook by renaming `.claude/settings.json` or removing the specific hook configuration.

### Q: Does this work with all Claude Code commands?

Yes, this works with any Claude Code command that uses git (commit, push, merge operations, etc.).

### Q: Can I still use --no-verify manually?

Yes! When you run git commands manually in your terminal, `block-no-verify` won't interfere. It only protects against automated git commands run by Claude Code.

## References

- [block-no-verify npm package](https://www.npmjs.com/package/block-no-verify)
- [block-no-verify GitHub repository](https://github.com/tupe12334/block-no-verify)
- [Claude Code Hooks Documentation](https://docs.anthropic.com/en/docs/claude-code/overview)
- [Git Hooks Documentation](https://git-scm.com/book/en/v2/Git-Hooks)

## Summary

Using `block-no-verify` with Claude Code ensures that:

1. All automated commits respect your git hooks
2. Code quality standards are maintained
3. Linting, testing, and formatting checks are never bypassed
4. Your codebase remains clean and consistent

This is especially important for teams relying on pre-commit hooks for code quality enforcement.
