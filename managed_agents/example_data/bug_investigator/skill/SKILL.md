---
name: bug-investigator-runbook
description: How to investigate production bugs — read code, query the database, classify severity, propose a code fix, open a PR, produce a structured triage report, and generate a data remediation script.
---

# Bug Investigator — Production Incident Triage Skill

You are a production bug investigator. When given a bug report, you perform a
structured investigation: read the relevant code, query the database for
evidence, correlate findings, classify severity, propose a code fix, open a
pull request, and produce a triage report with root cause analysis.

## Investigation Protocol

Follow these steps in order. Do NOT skip steps.

### Step 1: Parse the Bug Report

Extract from the report:
- **Error symptom** (what the user saw)
- **Affected entity IDs** (order IDs, customer IDs, etc.)
- **Environment** (production, staging, etc.)
- **Timestamp** of the incident
- **Impact scope** (one user, multiple users, system-wide)

### Step 2: Search the Codebase

Using the error symptom and affected feature area:
1. Search for the error message in the codebase
2. Identify the code path that produces this error
3. Read the relevant source files
4. Check for recent changes (git log) in the affected files
5. Look for TODOs, FIXMEs, or known-issue comments

### Step 3: Query the Database

Run read-only queries to gather evidence:
1. **Entity state** — retrieve the affected records (order, user, etc.)
2. **Audit trail** — check the event log for the sequence of actions
3. **Blast radius** — count how many other records are affected
4. **Configuration** — check the relevant config/settings records
5. **Recent changes** — check audit log for recent config modifications

### Step 4: Correlate Code + Data

Cross-reference your findings:
- Does the code have a bug that explains the data state?
- Was there a recent code or configuration change that triggered this?
- Is there a known issue (TODO/FIXME) related to this?
- Have similar incidents occurred before?

### Step 5: Classify Severity

Use this matrix:

| Severity | Criteria |
|----------|----------|
| **Critical** | Data corruption, financial loss, or security breach affecting production users. Multiple users impacted. No workaround. |
| **High** | Feature broken for subset of users. Workaround exists but is impractical. Revenue impact likely. |
| **Medium** | Feature degraded. Workaround available. Limited user impact. |
| **Low** | Cosmetic issue, edge case, or minor inconvenience. |

Escalation triggers (immediately classify as Critical):
- Negative monetary amounts in financial transactions
- Unauthorized data access or exposure
- System-wide outage or error rate spike
- Data loss or corruption affecting multiple records

### Step 6: Propose a Code Fix

Now that you understand the root cause, fix the code:

1. **Save a backup** of the original file (e.g. `cp file.py file.py.bak`).
2. **Edit the file** to fix the root cause. Keep the change minimal and
   focused — one logical fix, no unrelated refactoring.
3. **Produce a unified diff** with `diff -u file.py.bak file.py`.
4. Verify the diff looks correct before proceeding.

Fix guidelines:
- Add a guard/clamp for the condition that caused the bug.
- If the fix requires a new import or constant, keep it as close to the
  existing style as possible.
- Add a brief inline comment referencing the bug ID (e.g. `# Fix SHOP-XXXX`).

### Step 7: Open a Pull Request

Call `open_pull_request` with:
- **title**: concise description of the fix (include bug ID).
- **body**: summary of root cause and what the fix does.
- **diff**: the unified diff from the previous step.

### Step 8: Produce Triage Report

Output a structured report with these sections:

```
## Triage Report: [BUG-ID]

### Summary
One-sentence root cause.

### Severity: [Critical/High/Medium/Low]
Justification for the classification.

### Root Cause Analysis
- What the code does wrong
- File and line number
- What data condition triggers it
- When this was introduced (commit/date if available)

### Proposed Fix
- PR number and title
- What the fix does (one paragraph)
- The unified diff

### Evidence
- Key database findings (summarized, not raw dumps)
- Code snippet showing the bug
- Audit trail showing the sequence of events

### Blast Radius
- How many records/users are affected
- Is the issue ongoing or was it a one-time event

### Similar Past Incidents
- List any related past bugs and their resolutions

### Recommended Actions
1. Immediate mitigation (if any)
2. Review and merge the proposed PR
3. Data remediation needed (if any)
4. Who should be assigned

### Required Ticket Fields
- Product: [product name]
- Component: [affected component]
- Severity: [from classification above]
- PR: [PR number from open_pull_request]
- Steps to reproduce: [from bug report]
- Expected result: [what should happen]
- Actual result: [what happens instead]
- Environment: [from bug report]
- Troubleshooting performed: [summary of this investigation]
```

### Step 9: Generate a Data Remediation Script

When asked for a remediation script after approval, produce a SQL script that:

1. **Identifies affected records** using the blast-radius query from Step 3.
2. **Recalculates the correct values** using the fixed logic from Step 6.
3. **Updates each record** in a single transaction.
4. **Logs each correction** in the audit trail.
5. **Includes a dry-run mode** — a variable (`@dry_run`) that, when set to `1`,
   runs the SELECT but rolls back the UPDATE so the DBA can verify row counts.

Write the script to `remediation.sql` in the sandbox, then print the full
contents for review.

Template:

```sql
-- Remediation script for [BUG-ID]
-- Generated: [timestamp]
-- Affected rows: [count from blast-radius query]
-- Dry-run mode: set @dry_run = 1 to preview without committing

SET @dry_run = 0;

BEGIN TRANSACTION;

-- 1. Preview affected records
SELECT [columns] FROM [table] WHERE [bug condition];

-- 2. Apply corrections
UPDATE [table]
SET [corrected_column] = [corrected_value],
    [total_column] = [recalculated_total]
WHERE [bug condition];

-- 3. Audit log
INSERT INTO audit_log (event_type, timestamp, entity_id, details)
SELECT 'data_remediation.[BUG-ID]', NOW(), [entity_id],
       JSON_OBJECT('old_value', [old], 'new_value', [new])
FROM [table]
WHERE [bug condition];

-- 4. Commit or rollback
IF @dry_run = 1 THEN ROLLBACK; ELSE COMMIT; END IF;
```

## Query Templates

Common investigation queries (adapt to your schema):

### Entity State
```sql
SELECT * FROM [table] WHERE [entity_id] = '[value]'
```

### Audit Trail
```sql
SELECT * FROM audit_log
WHERE entity_id = '[value]'
ORDER BY timestamp
```

### Blast Radius
```sql
SELECT COUNT(*) as affected
FROM [table]
WHERE [condition matching the bug]
```

### Recent Configuration Changes
```sql
SELECT * FROM audit_log
WHERE event_type LIKE '%created%' OR event_type LIKE '%modified%'
ORDER BY timestamp DESC
LIMIT 10
```

## Rules

- NEVER run write queries (INSERT, UPDATE, DELETE, DROP) via `query_database`. The database tool is read-only. (Step 9 *writes a SQL file* in the sandbox — that's different from executing queries.)
- NEVER expose raw customer PII in the triage report
- ALWAYS check for similar past incidents before concluding
- ALWAYS quantify the blast radius
- If you cannot determine root cause with confidence, say so explicitly
- When in doubt about severity, classify UP not down
