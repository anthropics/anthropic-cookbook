# CMA Bridge on Cloudflare Workers

One deployable bridge between any chat surface and Claude [Managed Agents](https://platform.claude.com/docs/en/managed-agents/overview). The Anthropic side is partner-agnostic — add an inbound source by dropping a ~40-line adapter into `src/adapters/`.

```
Partner @mention ─▶ adapter.inbound ─▶ kickoff({metadata: {adapter, ...}}) ─▶ 200
                                                │
                           Claude runs to idle on Anthropic infra
                                                │
/cma-webhook ◀── session.status_idled ◀─────────┘
      └─▶ retrieve → adapters[metadata.adapter].postReply(metadata, text)
```

Ships with a **Slack** adapter. Stateless (KV for dedupe only), free-tier friendly.

## Quickstart

```bash
cd managed_agents/cloudflare-bridge
npm install
claude
```

Then ask: **"walk me through deploying this."** Claude reads [`skill.md`](./skill.md) and drives the config — agent provisioning, `wrangler` secrets + KV, Slack app, Anthropic webhook, `wrangler deploy`.

## Files

| | |
|---|---|
| `src/index.ts` | Worker entry, routing |
| `src/cma.ts` | **Shared**: `kickoff()` + `handleCmaWebhook()` — unwrap, KV dedupe, retrieve-then-filter, dispatch |
| `src/adapters/slack.ts` | Slack sig verify, `url_verification`, `chat.postMessage` |
| `src/adapters/types.ts` | `Adapter` interface — implement this to add a partner |
| `setup/create-agent.ts` | One-time: `agents.create` + `environments.create` (runs locally) |
| `wrangler.toml` | `nodejs_compat`, KV binding |

Requires `@anthropic-ai/sdk` ≥ 0.95.1.
