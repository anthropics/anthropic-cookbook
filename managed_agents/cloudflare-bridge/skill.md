# Setup tips & tricks — CMA Bridge on Cloudflare Workers

Things that aren't obvious from the docs and tend to cost debugging time.

---

## Mental model

### The Anthropic side is partner-agnostic

`cma.ts` never mentions Slack. It stamps `metadata.adapter = "<name>"` on session create; when the idle webhook arrives it reads that key back and dispatches to `adapters[name].postReply()`. Adding a partner = one adapter file, zero changes elsewhere.

### Workers are stateless per request

No in-memory `Set` survives across invocations. Dedupe (Anthropic `event.id`, Slack `event_id`) uses a KV namespace with a 1h TTL. Background work (`kickoff`, `postReply`) runs via `ctx.waitUntil()` so the isolate stays alive after the `Response` returns.

### The webhook is a doorbell, not a delivery

Anthropic's `session.status_idled` payload is `{type, id}` — nothing else. You follow up with `sessions.retrieve(id)` (metadata) and `sessions.events.list(id)` (output). Push the signal, pull the data.

---

## Deploy checklist

1. **Install + typecheck**
   ```bash
   npm install
   npx tsc --noEmit
   ```
2. **Provision the agent** (local, one-time — needs `ANTHROPIC_API_KEY` in your shell)
   ```bash
   bun run setup   # prints CLAUDE_AGENT_ID / CLAUDE_ENVIRONMENT_ID
   ```
3. **KV namespace** → paste the returned `id` into `wrangler.toml`
   ```bash
   npx wrangler kv namespace create DEDUPE
   ```
4. **Secrets** (one `put` per var; values are prompted, never echoed)
   ```bash
   for s in ANTHROPIC_API_KEY ANTHROPIC_WEBHOOK_SIGNING_KEY CLAUDE_AGENT_ID CLAUDE_ENVIRONMENT_ID SLACK_SIGNING_SECRET SLACK_BOT_TOKEN; do
     npx wrangler secret put $s
   done
   ```
5. **Deploy**
   ```bash
   npx wrangler deploy   # → https://cma-bridge.<you>.workers.dev
   ```
6. **Anthropic Console → Manage → Webhooks**: add `https://cma-bridge.<you>.workers.dev/cma-webhook`, subscribe `session.status_idled` + `session.status_terminated`. **Same workspace as your API key.**
7. **Slack app** (see `managed_agents/slack/skill.md` for the full Slack-side walkthrough): Event Subscriptions URL = `https://cma-bridge.<you>.workers.dev/slack/events`.

---

## Gotchas

### `nodejs_compat` is load-bearing

`node:crypto` (Slack HMAC) and `process.env` only exist on Workers with `compatibility_flags = ["nodejs_compat"]` and a recent `compatibility_date`. Don't remove it.

### `@slack/web-api` doesn't run on Workers

It pulls in `axios` + `node:zlib`. The adapter uses raw `fetch('https://slack.com/api/chat.postMessage')` instead — same wire format, 10 lines.

### `ctx.waitUntil` or it didn't happen

Returning a `Response` ends the request. Any promise not wrapped in `ctx.waitUntil()` may be killed mid-flight. `kickoff()`, `postReply()`, and KV writes all use it.

### Anthropic webhooks are workspace-scoped

Fires for **every** session in the Anthropic workspace. `cma.ts` retrieves-then-filters on `metadata.adapter` before doing work; sessions without it (or 404/403 on retrieve) are ignored. For production, use a dedicated workspace.

### KV is eventually consistent

A retry that lands on a different Cloudflare edge within ~1s of the first delivery may not see the dedupe key yet. Worst case is a duplicate `chat.postMessage` — acceptable for this use case. If not, use a Durable Object instead.

### Local dev

`npx wrangler dev` runs the Worker locally with a simulated KV. Put secrets in `.dev.vars` (gitignored):
```
ANTHROPIC_API_KEY=sk-ant-...
...
```
Then use ngrok/cloudflared to expose `localhost:8787` for the Slack `url_verification` step.

---

## Debugging

| Symptom | Check |
|---|---|
| `wrangler deploy` fails bundling | `nodejs_compat` flag missing, or a dep pulled in something Workers can't polyfill |
| Slack says "URL didn't respond" | Worker not deployed yet, or `url_verification` branch returning wrong content-type |
| Kickoff logs but no reply | `npx wrangler tail` → look for `/cma-webhook` hits. None = Anthropic workspace mismatch. 401 = signing key mismatch. |
| `invalid_auth` from Slack | `SLACK_BOT_TOKEN` is an `xapp-` (App-Level) token, not `xoxb-` (Bot OAuth) |
| Duplicate replies | Expected occasionally (KV eventual consistency); switch to Durable Object if it matters |
