---
name: review
description: Run security + QA review on existing code changes
---

# /review — Security and Quality Review

Run a security review and QA validation on recent code changes without going through the full implementation flow.

## Input

The user wants to review: $ARGUMENTS

If no specific files are mentioned, review all uncommitted changes (`git diff`).

## Workflow

1. **Security Review**: Invoke the security agent to review the changed code for vulnerabilities.
2. **QA Validation**: Invoke the QA agent to run existing tests and verify nothing is broken.

## Steps

### Step 1: Identify Changes
Run `git diff --name-only` to identify what files changed. If the user specified files, use those instead.

### Step 2: Security Review
Use the Agent tool with the **security** agent. Pass it:
- The list of changed files
- Ask for a post-implementation code review

### Step 3: QA Validation
Use the Agent tool with the **qa** agent. Pass it:
- The list of changed files
- Ask it to run the existing test suite and report any failures

### Step 4: Report
Combine findings from both agents into a single summary for the user.
