---
name: implement
description: Run the full multi-agent implementation workflow for a feature
---

# /implement — Multi-Agent Implementation Flow

You are about to orchestrate a full implementation workflow. Follow these steps exactly.

## Input

The user has provided a feature request: $ARGUMENTS

## Workflow

Invoke the **coordinator** agent to manage this workflow. Pass it the feature request and let it orchestrate the specialist agents (architect, security, developer, qa) through the implementation pipeline.

The coordinator will:
1. Route the feature to the architect for design
2. Send the design to security for review
3. Pass the approved design to the developer for implementation
4. Send the code back to security for code review
5. Have QA write and run tests
6. Report completion

## Invocation

Use the Agent tool with the coordinator agent. Pass it this context:

```
Feature request: $ARGUMENTS

Execute the full implementation workflow as defined in your instructions.
Read the existing codebase first to understand the current state.
Update .claude/workflow-state.json at each step.
Report back when complete or if blocked.
```

## Important

- Do NOT implement the feature yourself. The coordinator delegates to specialists.
- If the coordinator reports a blocker after 3 fix cycles, surface it to the user.
- The workflow is complete when the coordinator reports step 6 (complete).
