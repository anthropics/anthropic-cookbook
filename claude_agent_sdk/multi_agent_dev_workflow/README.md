# Multi-Agent Development Workflow

A reusable pattern for orchestrating specialized AI agents through Claude Code's native filesystem architecture. No SDK code required — just markdown files in your `.claude/` directory.

## Quick Start

```bash
# Copy the .claude/ directory into any project
cp -r .claude/ /path/to/your-project/.claude/

# Open Claude Code in that project
cd /path/to/your-project
claude

# Run the workflow
> /implement "Add user authentication"
```

## What's Inside

| File | Purpose |
|------|---------|
| `.claude/agents/coordinator.md` | Orchestrator — manages the workflow pipeline |
| `.claude/agents/architect.md` | Designs features before code is written |
| `.claude/agents/developer.md` | Implements code from approved designs |
| `.claude/agents/security.md` | Reviews designs and code for vulnerabilities |
| `.claude/agents/qa.md` | Writes and runs tests |
| `.claude/commands/implement.md` | `/implement` slash command |
| `.claude/commands/review.md` | `/review` slash command |
| `.claude/CLAUDE.md` | Project-level workflow rules |

## How It Works

The `/implement` command triggers a 6-step pipeline:

1. **Architect** produces a design document
2. **Security** reviews the design (gate: must pass)
3. **Developer** implements from the design
4. **Security** reviews the code (gate: must pass)
5. **QA** writes tests and runs them (gate: all must pass)
6. **Complete** — feature shipped with design, security clearance, and tests

Failed gates loop back to the responsible agent (max 3 retries before escalating to the user).

## See Also

- [07_The_multi_agent_dev_workflow.ipynb](07_The_multi_agent_dev_workflow.ipynb) — Full guide explaining the pattern, design decisions, and trade-offs
- [example_project/](example_project/) — Minimal TODO app to demo against
