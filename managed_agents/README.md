# Claude Managed Agents cookbooks

Claude Managed Agents is Anthropic's hosted runtime for stateful, tool-using
agents. You define an agent and a sandboxed environment once, then run
them in sessions that persist files, tool state, and conversation
across turns. These tutorials show it end to end.

## MongoDB on Managed Agents

Want to give an agent a real database — for retrieval, graph traversal, and as
its system of record?
**[`CMA_with_mongodb_atlas.ipynb`](CMA_with_mongodb_atlas.ipynb)**
is the consolidated cookbook: three ways to connect MongoDB to a CMA agent (and
where the credential lives on each path), the four retrieval patterns
(vector / full-text / hybrid / graph) as liftable building blocks, and an
end-to-end human-in-the-loop fraud-review agent with Atlas as the system of
record and audit backbone.

## Applied cookbooks

- **[data_analyst_agent.ipynb](data_analyst_agent.ipynb)** builds an
  analyst that turns a CSV into a narrative HTML report using pandas
  and plotly. You'll configure an environment and agent, mount a
  dataset, stream the run, and retrieve the generated artifacts.
- **[slack_data_bot.ipynb](slack_data_bot.ipynb)** wraps that agent in
  a Slack bot. Mention it with a CSV to get the report in-thread;
  replies continue the same session.
- **[sre_incident_responder.ipynb](sre_incident_responder.ipynb)** puts
  Managed Agents on the on-call path: a pager alert starts a session,
  the agent investigates and opens a PR, then pauses for human
  approval before merging. You'll wire the alert webhook, attach a
  Skill and custom tools, and review the full run in the Console.

## Guided tutorials

End-to-end tutorials that teach the Managed Agents API surface
through realistic workflows. There's no strict reading order,
but `CMA_iterate_fix_failing_tests.ipynb` is a good entry point,
it introduces every API shape the others build on.

| Notebook | What it teaches |
| --- | --- |
| [`CMA_iterate_fix_failing_tests.ipynb`](CMA_iterate_fix_failing_tests.ipynb) | Do → observe → fix loop on a failing test suite. The entry-point notebook: introduces agent / environment / session, file mounts, and the streaming event loop through the lens of getting a buggy package to green. |
| [`CMA_orchestrate_issue_to_pr.ipynb`](CMA_orchestrate_issue_to_pr.ipynb) | Issue → fix → PR → CI → review → merge through a mock `gh` CLI. Multi-turn steering, mid-chain recovery from a CI failure and a review comment. Sidebar shows how to swap the file mount for a `github_repository` resource against a real repo. |
| [`CMA_explore_unfamiliar_codebase.ipynb`](CMA_explore_unfamiliar_codebase.ipynb) | Grounding in an unfamiliar codebase, with a planted stale-doc trap. Sidebar shows how to add resources to a running session via `sessions.resources.add`. |
| [`CMA_gate_human_in_the_loop.ipynb`](CMA_gate_human_in_the_loop.ipynb) | Human-in-the-loop expense approval via custom-tool `decide()` / `escalate()`. Covers the custom-tool round-trip pattern, the `requires_action` idle bounce, and parallel-tool-call dedupe. |
| [`CMA_with_mongodb_atlas.ipynb`](CMA_with_mongodb_atlas.ipynb) | **MongoDB Atlas** end to end: three connection paths (host-side custom tool, self-hosted sandbox, self-hosted MCP), the four retrieval patterns (vector / full-text / RRF hybrid / `$graphLookup`), and a human-in-the-loop fraud-review agent that records decisions and an append-only audit trail in the same cluster. Pauses on risky cases via the `requires_action` gate; shows an auto-resolving gate for CI and the webhook handoff for production. |
| [`CMA_prompt_versioning_and_rollback.ipynb`](CMA_prompt_versioning_and_rollback.ipynb) | Server-side prompt versioning: create v1, evaluate against a labelled test set, ship v2, detect a regression, roll back by pinning sessions to version 1. Covers `agents.update`, version pinning on `sessions.create`, and where the review gate moves when prompts are not code. |
| [`CMA_operate_in_production.ipynb`](CMA_operate_in_production.ipynb) | Production setup: MCP toolsets, vaults for per-end-user credentials, the `session.status_idled` and `session.budget_reached` webhook patterns for HITL and cost supervision without long-lived connections, `inference_geo` pinning for residency, and the resource lifecycle CRUD verbs. |
| [`CMA_remember_user_preferences.ipynb`](CMA_remember_user_preferences.ipynb) | Memory stores: a shopping agent that learns a customer's preferences in one session and recalls them in the next. Covers `memory_stores.create`, the `resources` attachment with per-attachment `instructions`, inspecting and seeding memories from your own application, and combining a per-customer read-write store with a brand-wide read-only store. |
| [`CMA_coordinate_specialist_team.ipynb`](CMA_coordinate_specialist_team.ipynb) | Heterogeneous team via the `multiagent` coordinator config: a coordinator runs three specialists (web-search researcher, file-reading librarian, rules-based pricer) with scoped toolsets to assemble a sales proposal. Covers the `multiagent` field, the `thread_created` / `thread_message_received` event types, why per-role tool scoping matters, and an `advisor` roster entry the coordinator consults before writing. |
| [`CMA_watch_subagents_live.ipynb`](CMA_watch_subagents_live.ipynb) | A curriculum-planning team you can watch in real time. Covers per-thread `event_deltas` so subagent text streams live, `initial_events` on session create, per-agent model `effort` as a cost lever, and versionless `agents.update`. Builds on the coordinate-specialist-team shapes. |
| [`CMA_plan_big_execute_small.ipynb`](CMA_plan_big_execute_small.ipynb) | Coordinator-pattern economics: a frontier coordinator delegates the token-heavy web reading to cheap parallel workers, measured against a rigor-matched solo-frontier control with per-thread `usage.list_cost` metering and a session `budget` as the fan-out guardrail. |
| [`CMA_verify_with_outcome_grader.ipynb`](CMA_verify_with_outcome_grader.ipynb) | Build a grade-and-revise loop with Outcomes: a writer drafts a cited research brief, a stateless grader fetches every URL and checks every quote against a rubric, and feedback drives revisions until the brief passes. Covers `user.define_outcome`, the `span.outcome_evaluation_*` events, and how to write a rubric the grader can act on. |
| [`CMA_consult_an_advisor.ipynb`](CMA_consult_an_advisor.ipynb) | A mid-tier working agent that consults a stronger model mid-turn via an `advisor` roster entry. Covers the `{"type": "advisor"}` entry in `multiagent.agents`, the `anthropic.advisor` thread lifecycle on the primary stream, per-consultation cost from the advisor thread's `usage`, and the redacted delivery arm. |
| [`CMA_cap_session_spend.ipynb`](CMA_cap_session_spend.ipynb) | Enforced spend ceiling on one session. Covers the `budget` field on `sessions.create`, the `session.usage` snapshot events and `usage.list_cost`, the `budget_reached` pause, and raising, lowering, and removing the cap with `sessions.update`. |
| [`CMA_use_skills_from_a_repo.ipynb`](CMA_use_skills_from_a_repo.ipynb) | Skills discovered from a mounted repository's root `.claude/skills/` at session start, with no `skills` field on the agent. Covers the layout the scanner expects, the read-then-follow protocol, and the lifecycle rules (skill cap, single scan, lazy nested discovery). |
| [`CMA_pin_inference_geo.ipynb`](CMA_pin_inference_geo.ipynb) | Data residency on the agent definition: `model.inference_geo` pinning, where the pin is enforced, its interplay with the workspace `allowed_inference_geos` policy, and a one-session geography override with `agent_with_overrides`. |

The streaming event loop is walked through line by line in the
iterate notebook and then factored into
`utilities.stream_until_end_turn` so the other notebooks can
import it instead of repeating the `match ev.type:` block. The
gate notebook and the MongoDB cookbook are the exceptions: they keep
the loop inline because custom-tool agents need to handle
`requires_action` idle bounces in addition to `end_turn`, which
the helper doesn't cover.

## Getting started

Set `ANTHROPIC_API_KEY` in your environment, then open
`data_analyst_agent.ipynb` in Jupyter and run the cells top to
bottom. Each notebook installs its own dependencies and prompts
for any credentials it needs. The orchestrate-to-PR sidebar in
`CMA_orchestrate_issue_to_pr.ipynb`, the vault-backed MCP example
in `CMA_operate_in_production.ipynb`, and
`CMA_use_skills_from_a_repo.ipynb` additionally need `GITHUB_TOKEN`
set (a fine-grained PAT with public-repo read is enough). The
MongoDB cookbook in `CMA_with_mongodb_atlas.ipynb` additionally
needs `MONGO_URI` set to an Atlas SRV connection string (an M0
free cluster works); a provider key — `MDB_ATLAS_API_KEY` or
`VOYAGE_API_KEY` — is optional and only enables the
live-embedding and reranker paths.

All cookbook fixture data — input CSVs and supporting assets for
the applied cookbooks, plus the planted-trap fixtures the guided
tutorials read from — lives under `example_data/`. See
[`example_data/OVERVIEW.md`](example_data/OVERVIEW.md) for the
directory map.

## Runnable apps

This directory holds notebooks. Full apps built on Managed Agents, such as
the Slack and Linear bots, the Sentry triage agent, the road trip planner,
the MCP server, and the self-hosted sandbox variants that used to live here,
are in
[claude-quickstarts/managed-agents](https://github.com/anthropics/claude-quickstarts/tree/main/managed-agents).
