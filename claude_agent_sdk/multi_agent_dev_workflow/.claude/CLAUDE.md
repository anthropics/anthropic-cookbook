# Multi-Agent Dev Workflow

This project uses a multi-agent development workflow where specialized AI agents collaborate through an orchestrator to implement features with built-in quality gates.

## Architecture

```
User → /implement "feature" → Coordinator → Architect → Security → Developer → Security → QA → Done
```

## Agents

| Agent | Role | Model | Boundary |
|-------|------|-------|----------|
| coordinator | Orchestrates workflow, enforces gates | opus | Never writes code/tests/designs |
| architect | Designs systems, produces design docs | opus | Never writes application code |
| developer | Implements code from design docs | sonnet | Never writes tests |
| security | Reviews designs and code for vulns | sonnet | Never writes code, only reports findings |
| qa | Writes and runs tests | sonnet | Never modifies application code |

## Workflow Rules

### Quality Gates
Every feature passes through these gates in order:
1. Design review (architect produces, security validates)
2. Implementation (developer builds from approved design)
3. Code review (security reviews implementation)
4. Testing (QA writes tests, all tests must pass)

### Failure Handling
- If a gate fails, the coordinator routes the fix to the appropriate agent
- After fix, only the failed gate is re-run (not the entire workflow)
- After 3 failed attempts on the same gate, escalate to the user

### Agent Boundaries (ENFORCED)
- Agents stay in their lane. A developer does not write tests. QA does not fix bugs.
- All coordination goes through the coordinator. Agents do not invoke each other directly.
- The coordinator never does an agent's job — it delegates and validates.

## State

Workflow progress is tracked in `.claude/workflow-state.json`. This enables resumability — if a session ends mid-workflow, the next session can pick up where it left off.

## Commands

- `/implement "feature description"` — Run the full implementation pipeline
- `/review` — Run security + QA review on current changes
