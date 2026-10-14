#!/usr/bin/env python3
"""Scheduled repository review with a resumable, schema-validated session.

Requires claude-agent-sdk 0.2.140 or later. One review per invocation, run
from the reviewer's own service directory with the repository to review as
the argument:

    cd /srv/reviewer && . ./reviewer.env && .venv/bin/python scheduled_review.py /path/to/your/repo

The first invocation reviews cold and persists its session id, review id, and
finding ids to .last_review_session beside this script. Every later
invocation resumes that session with the follow-up schema, so the reply
points back at the previous review, lists resolved findings, and reports
anything new. The RESUME-LINK line checks the reply against the persisted
state field by field. Delete the session file to force a fresh baseline.
Pointing the script at a different repository starts a fresh baseline
automatically.

Alerts fire on any run that prints no completion line and exits non-zero,
and on a RESUME-LINK-BROKEN line, which a completed run prints when the
resumed link did not hold. Cron itself keeps no exit statuses, so the
documented crontab entry ends with a tail that writes the status into the
log as a REVIEW-RUN-EXIT line. Both failure classes end without the
completion line:

* A run that ends on a terminal error result, usually an exceeded max_turns or
  max_budget_usd, raises the typed ResultError this script catches. The script
  prints REVIEW-RUN-INCOMPLETE and exits 1. A resumed run that fails
  mid-execution, most often because the saved session no longer resumes, also
  clears the session file and prints SESSION-FILE-CLEARED, so the next cycle
  rebuilds the baseline cold without intervention.
* A run that produces no terminal result at all, such as a killed process or a
  connection that never opens, raises its own exception type and exits
  non-zero with a traceback.

Exit codes: 0 when the review completed, 1 when it did not, 2 on usage errors.
Usage errors also print a stage=usage failure line on stdout, so a
mis-deployed crontab leaves a greppable line in the redirected log.

Companion to scheduled_repository_reviewer.ipynb, which walks through every
choice here, including when to start fresh instead of resuming. A
repository inside the service directory is refused as a usage error: the
script denies itself the service directory's files, so that review would
complete while reading nothing.
"""

import asyncio
import json
import sys
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookContext,
    HookMatcher,
    ResultError,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

SERVICE_DIR = Path(__file__).resolve().parent
SESSION_FILE = SERVICE_DIR / ".last_review_session"

READ_ONLY_TOOLS = ["Read", "Glob", "Grep"]
MODEL = "claude-sonnet-5"
FIRST_RUN_BUDGET_USD = 2.00
FOLLOW_UP_BUDGET_USD = 0.50
# Sized with headroom for a real repository. Tune against the cost_usd
# figure in each run's summary line.
FIRST_RUN_MAX_TURNS = 40
FOLLOW_UP_MAX_TURNS = 20
TEXT_LOG_CHARS = 400


def clip(text: Any) -> str:
    """Flatten text onto one bounded log line, marking the cut when one happens.

    Findings arrive as free text and land in a log other tools grep. Dropping
    unprintable characters and collapsing whitespace keeps each field on one
    log line of its own.
    """
    printable = "".join(char if char.isprintable() else " " for char in str(text))
    flat = " ".join(printable.split())
    return flat if len(flat) <= TEXT_LOG_CHARS else flat[:TEXT_LOG_CHARS] + "..."


REVIEWER_SYSTEM_PROMPT = (
    "You are a repository review agent running on a schedule with nobody "
    "watching. Inspect the files with your read-only tools, keep the review "
    "short, and answer with the JSON object the caller's schema describes."
)


class Verdict(StrEnum):
    """The two verdicts a scheduled review may report."""

    OK = "ok"
    CONCERNS = "concerns"


VERDICT_VALUES = [verdict.value for verdict in Verdict]

FINDING_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "file": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["id", "file", "summary"],
}

FIRST_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "review_id": {"type": "string"},
        "verdict": {"type": "string", "enum": VERDICT_VALUES},
        "findings": {"type": "array", "items": FINDING_SCHEMA},
    },
    "required": ["review_id", "verdict", "findings"],
}

# What a resumed run adds: the same review object plus its link back to the
# previous one. Merging the first schema keeps the shared half in one place.
CONTINUITY_PROPERTIES = {
    "previous_review_id": {"type": "string"},
    "previous_finding_ids": {"type": "array", "items": {"type": "string"}},
    "resolved": {"type": "array", "items": {"type": "string"}},
}

FOLLOW_UP_REVIEW_SCHEMA = FIRST_REVIEW_SCHEMA | {
    "properties": FIRST_REVIEW_SCHEMA["properties"] | CONTINUITY_PROPERTIES,
    "required": [*FIRST_REVIEW_SCHEMA["required"], *CONTINUITY_PROPERTIES.keys()],
}


@dataclass
class RunOutcome:
    """What one scheduled run reported back."""

    session_id: str | None = None
    subtype: str = "no_result"
    num_turns: int = 0
    total_cost_usd: float | None = None
    denials: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    tools_attempted: list[str] = field(default_factory=list)


def cold_prompt(review_id: str) -> str:
    """The prompt for a review with no prior session to build on."""
    return (
        f"Scheduled review {review_id} of the repository in the current "
        "directory. Read the source files and report correctness or security "
        "problems you can point at a specific file and function. Give each "
        "finding a summary of one or two sentences and an id of the form "
        "F1, F2, and so on. Use the verdict "
        '"concerns" when you report at least one finding and "ok" when the '
        f"repository looks clean. Echo {review_id} back as review_id."
    )


def follow_up_prompt(review_id: str) -> str:
    """The prompt for a review that resumes the previous run's session."""
    return (
        f"Scheduled review {review_id} of the same repository, one cycle "
        "later. List the repository's files again, then read the source files "
        "as they stand now. Answer from the most recent review you did in "
        "this conversation: put its review id in previous_review_id and the ids of "
        "the findings it reported in previous_finding_ids. Report the findings "
        "that still apply, keeping the ids you gave them earlier, list in "
        "resolved the ids of previous findings that no longer apply, and "
        "report anything newly wrong as a new finding with a summary of one "
        f"or two sentences. Echo {review_id} back as review_id."
    )


def deny_reads_outside_repo(repo: Path):
    """Deny any Read, Grep, or Glob call whose path resolves outside repo.

    The hook confines Grep and Glob deterministically instead of relying
    on Read-rule coverage of those tools. Candidate paths resolve
    symlinks, so a Read through an in-repository link is denied when it
    lands outside. Absolute Glob patterns, patterns carrying a `..` segment, and
    patterns carrying brace syntax the segment check can't reason about are
    denied rather than trusted to stay inside their search root.
    """

    def denial(reason: str) -> dict[str, Any]:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }

    async def deny(
        input_data: dict[str, Any], tool_use_id: str | None, context: HookContext
    ) -> dict[str, Any]:
        tool_input = input_data.get("tool_input") or {}
        raw = tool_input.get("file_path") or tool_input.get("path")
        if raw:
            candidate = Path(raw).expanduser()
            if not candidate.is_absolute():
                candidate = repo / candidate
            candidate = candidate.resolve()
            if not candidate.is_relative_to(repo):
                return denial(f"path outside the repository under review: {candidate}")
        if input_data.get("tool_name") == "Glob":
            pattern = tool_input.get("pattern")
            if isinstance(pattern, str) and (
                pattern.startswith(("/", "~")) or "{" in pattern or ".." in pattern.split("/")
            ):
                return denial(f"glob pattern may leave the repository under review: {pattern}")
        return {}

    return deny


def review_options(
    repo: Path,
    schema: dict[str, Any],
    max_turns: int,
    resume_session_id: str | None = None,
    service_dir: Path | None = None,
) -> ClaudeAgentOptions:
    """Build the options for one scheduled review pass."""
    options = ClaudeAgentOptions(
        # The agent works inside the reviewed repository.
        cwd=str(repo),
        system_prompt=REVIEWER_SYSTEM_PROMPT,
        tools=READ_ONLY_TOOLS,
        # The //-anchored form is deliberate: with a single leading slash
        # the rule anchors at the settings source, not the filesystem
        # root, matches nothing, and every read is denied under dontAsk.
        # repo is absolute, so the rendered rule keeps the double slash.
        allowed_tools=[f"Read(/{repo}/**)", "Glob", "Grep"],
        permission_mode="dontAsk",
        model=MODEL,
        # Keep machine- and account-configured MCP servers out of the
        # session.
        strict_mcp_config=True,
        max_turns=max_turns,
        max_budget_usd=FOLLOW_UP_BUDGET_USD if resume_session_id else FIRST_RUN_BUDGET_USD,
        hooks={
            "PreToolUse": [
                HookMatcher(matcher="Read|Grep|Glob", hooks=[deny_reads_outside_repo(repo)])
            ]
        },
        # Same behavior on a laptop and on the box that runs the cron job.
        setting_sources=[],
        output_format={"type": "json_schema", "schema": schema},
        # None on a cold run, and the persisted session id on a follow-up.
        resume=resume_session_id,
    )
    if service_dir is not None:
        # A second, independent layer beside the hook, which already
        # denies these reads: block the Read tool on the service
        # directory, where the env and session files live.
        options.disallowed_tools = [f"Read(/{service_dir}/**)"]
    return options


def sequence_of(value: Any) -> list[Any]:
    """Return a list-shaped field's items, or nothing when it isn't one."""
    match value:
        case [*items]:
            return items
        case _:
            return []


def verdict_of(payload: dict[str, Any]) -> Verdict:
    """Read the verdict from the structured reply, falling back to concerns
    when the field is missing or unrecognized."""
    match payload:
        case {"verdict": str(value)} if value in VERDICT_VALUES:
            return Verdict(value)
        case _:
            return Verdict.CONCERNS


def finding_ids(payload: dict[str, Any]) -> list[str]:
    """Collect finding ids from the structured reply."""
    ids: list[str] = []
    for finding in sequence_of(payload.get("findings")):
        match finding:
            case {"id": str(finding_id)}:
                ids.append(finding_id)
    return ids


def string_items(value: Any) -> list[str]:
    """Collect the plain strings from a list-shaped field."""
    return [item for item in sequence_of(value) if isinstance(item, str)]


def read_state() -> dict[str, Any]:
    """Load the previous run's persisted state, falling back to a cold run."""
    try:
        state = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        print("--- session file unreadable, starting cold")
        return {}
    return state if isinstance(state, dict) else {}


async def run_review(
    *,
    repo: Path,
    label: str,
    prompt: str,
    schema: dict[str, Any],
    max_turns: int,
    resume_session_id: str | None = None,
    service_dir: Path | None = None,
) -> RunOutcome:
    """Run one review pass and return its structured result."""
    options = review_options(repo, schema, max_turns, resume_session_id, service_dir)
    outcome = RunOutcome()
    async for message in query(prompt=prompt, options=options):
        match message:
            case AssistantMessage(content=blocks):
                for block in blocks:
                    match block:
                        case TextBlock(text=text):
                            line = text.strip()
                            if line:
                                # Cap what a scheduled log absorbs per block.
                                print(f"[{label}] {clip(line)}")
                        case ToolUseBlock(name=tool_name):
                            outcome.tools_attempted.append(tool_name)
            case ResultMessage() as result:
                outcome.session_id = result.session_id
                outcome.subtype = result.subtype
                outcome.num_turns = result.num_turns
                outcome.total_cost_usd = result.total_cost_usd
                outcome.denials = len(result.permission_denials or [])
                if isinstance(result.structured_output, dict):
                    outcome.payload = result.structured_output
    return outcome


def report(label: str, outcome: RunOutcome) -> Verdict:
    """Print the scheduler-shaped lines for one run and return its verdict."""
    cost = f"{outcome.total_cost_usd:.4f}" if outcome.total_cost_usd is not None else "n/a"
    print(
        f"{label} session={outcome.session_id} subtype={outcome.subtype} "
        f"turns={outcome.num_turns} denials={outcome.denials} "
        f"cost_usd={cost} "
        f"tools_attempted={','.join(dict.fromkeys(outcome.tools_attempted)) or 'none'}"
    )
    verdict = verdict_of(outcome.payload)
    print(f"VERDICT: {verdict}")
    for finding in sequence_of(outcome.payload.get("findings")):
        match finding:
            case {"id": str(finding_id), "file": str(file_path), "summary": str(summary)}:
                print(f"  {clip(finding_id)} {clip(file_path)}: {clip(summary)}")
    return verdict


async def main() -> int:
    if len(sys.argv) != 2:
        print("usage: scheduled_review.py /path/to/repository", file=sys.stderr)
        print("REVIEW-RUN-INCOMPLETE stage=usage reason=missing-argument")
        return 2
    repo = Path(sys.argv[1]).resolve()
    if not repo.is_dir():
        print(f"usage: repository not found: {repo}", file=sys.stderr)
        print("REVIEW-RUN-INCOMPLETE stage=usage reason=repository-not-found")
        return 2
    if repo == SERVICE_DIR or SERVICE_DIR in repo.parents:
        # The service-directory read denial would blind this review.
        print(
            f"usage: repository {repo} sits inside the service directory,"
            " which this script denies itself permission to read",
            file=sys.stderr,
        )
        print("REVIEW-RUN-INCOMPLETE stage=usage reason=repository-inside-service-directory")
        return 2
    if repo in SERVICE_DIR.parents:
        # The reverse nesting puts the env file inside the review's scope.
        print(
            f"usage: the service directory {SERVICE_DIR} sits inside repository {repo};"
            " keep the service directory outside the repository you review",
            file=sys.stderr,
        )
        print("REVIEW-RUN-INCOMPLETE stage=usage reason=service-directory-inside-repository")
        return 2
    state = read_state()
    resume_id = state.get("session_id")
    if not isinstance(resume_id, str) or not resume_id:
        resume_id = None
    if resume_id is not None and state.get("repo") != str(repo):
        print("--- session file reviews a different repository, starting cold")
        resume_id = None
    label = "resumed" if resume_id else "cold"
    review_id = f"review-{uuid.uuid4().hex[:8]}"
    print(f"--- scheduled review ({label}) | resume={resume_id or 'none'}")

    try:
        outcome = await run_review(
            repo=repo,
            service_dir=SERVICE_DIR,
            label=label,
            prompt=follow_up_prompt(review_id) if resume_id else cold_prompt(review_id),
            schema=FOLLOW_UP_REVIEW_SCHEMA if resume_id else FIRST_REVIEW_SCHEMA,
            max_turns=FOLLOW_UP_MAX_TURNS if resume_id else FIRST_RUN_MAX_TURNS,
            resume_session_id=resume_id,
        )
    except ResultError as exc:
        # The CLI reported a terminal error result and the SDK raised it here.
        # Print the failure line and return a non-zero status. The completion
        # line never runs. exc.data carries the raw result payload, so the
        # failure line still reports what the failed run consumed.
        cost = (exc.data or {}).get("total_cost_usd")
        cost_str = f"{cost:.4f}" if isinstance(cost, (int, float)) else "n/a"
        print(
            f"REVIEW-RUN-INCOMPLETE stage={label} subtype={exc.subtype} "
            f"reason={exc.terminal_reason} cost_usd={cost_str}"
        )
        if label == "resumed" and exc.subtype == "error_during_execution":
            # A resumed run failing mid-execution most often means the saved
            # session no longer resumes, so clear the link and let the next
            # cycle rebuild the baseline cold on its own. Bounds failures keep
            # the file: their subtypes are error_max_turns and
            # error_max_budget_usd, and their fix is a config change, not a
            # reset.
            SESSION_FILE.unlink(missing_ok=True)
            print("SESSION-FILE-CLEARED: next run reviews cold")
        return 1

    if outcome.subtype != "success" or outcome.session_id is None or not outcome.payload:
        cost = f"{outcome.total_cost_usd:.4f}" if outcome.total_cost_usd is not None else "n/a"
        print(f"REVIEW-RUN-INCOMPLETE stage={label} subtype={outcome.subtype} cost_usd={cost}")
        return 1
    report(label, outcome)

    # Persist what the next run needs to assert real continuity: the session
    # to resume, and the review id and finding ids the follow-up must recall.
    state_json = json.dumps(
        {
            "repo": str(repo),
            "session_id": outcome.session_id,
            "review_id": review_id,
            "finding_ids": finding_ids(outcome.payload),
        }
    )
    # Write-then-rename: a run killed mid-write must not leave truncated
    # JSON, which would cost an unnecessary cold rebuild.
    try:
        tmp_file = SESSION_FILE.with_name(SESSION_FILE.name + ".tmp")
        tmp_file.write_text(state_json, encoding="utf-8")
        tmp_file.replace(SESSION_FILE)
    except OSError as exc:
        # The review itself completed; only persistence failed. Clear the
        # old link so the next run rebuilds cold rather than resuming a
        # session that predates this review.
        print(
            f"SESSION-STATE-NOT-SAVED: review completed, "
            f"state not persisted ({exc.__class__.__name__})"
        )
        try:
            SESSION_FILE.unlink(missing_ok=True)
            print("SESSION-FILE-CLEARED: next run reviews cold")
        except OSError:
            print("SESSION-FILE-STALE: next run resumes the previous session")
        return 1
    if resume_id is not None:
        prior_ids = string_items(state.get("finding_ids"))
        recalled = string_items(outcome.payload.get("previous_finding_ids"))
        matched = sorted(set(recalled) & set(prior_ids))
        echoed = outcome.payload.get("previous_review_id") == state.get("review_id")
        print(
            f"RESUME-LINK same_session={outcome.session_id == resume_id} "
            f"prior_review_id_echoed={echoed} "
            f"recalled_findings={len(matched)}/{len(set(prior_ids))} "
            f"current_findings={len(set(finding_ids(outcome.payload)))}"
        )
        print(f"resolved={[clip(i) for i in string_items(outcome.payload.get('resolved'))]}")
        if outcome.session_id != resume_id or not echoed or (prior_ids and not matched):
            # Prints on a completed run by design: the exit code stays 0, so
            # wire alerts to this marker rather than to exit status.
            print(
                f"RESUME-LINK-BROKEN same_session={outcome.session_id == resume_id} "
                f"recalled_findings={len(matched)}/{len(set(prior_ids))}"
            )
    print(f"REVIEW-RUN-COMPLETE: {label}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
