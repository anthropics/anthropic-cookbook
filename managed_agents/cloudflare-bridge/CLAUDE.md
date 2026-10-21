# CMA Bridge on Cloudflare Workers

General deployable bridge: partner webhook → CMA session (with `metadata.adapter` + routing info) → `session.status_idled` webhook → `adapters[metadata.adapter].postReply()`. Ships with a Slack adapter.

## When the user asks to deploy, set up, extend, or debug this

1. **Invoke `/claude-api` first.** That skill loads the full Managed Agents API reference. Use it as the source of truth for any SDK call — don't guess field names.
2. **Read `./skill.md`** and walk the user through it step by step — `wrangler` secrets + KV, Slack app, Anthropic webhook, `wrangler deploy`.
3. **Adding a partner?** Implement `Adapter` in `src/adapters/<name>.ts` (`inbound` verifies sig + calls `kickoff()`; `postReply` posts back), register it in `src/adapters/index.ts`. Nothing in `cma.ts` changes.
4. **After the base bridge works, offer extensions** (edit `setup/create-agent.ts` / `src/cma.ts`):
   - **GitHub repo** — `resources: [{type: "github_repository", ...}]` on `sessions.create`
   - **MCP tools + vault** — `mcp_servers` + `mcp_toolset` on the agent; `vault_ids` on the session
   - **Outcomes** — `user.define_outcome` event instead of `user.message`
   - **Multiagent** — `multiagent: {type: "coordinator", agents: [...]}` on the agent
   - **Memory store** — `resources: [{type: "memory_store", ...}]`

   Pull exact shapes from the `/claude-api` skill's `shared/managed-agents-*.md` docs.

Commands: `npx wrangler dev` (local), `npx wrangler deploy` (ship), `bun run setup` (one-time agent provisioning — runs locally, not on the Worker).
