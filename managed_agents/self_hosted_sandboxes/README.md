# Self-hosted sandboxes has moved

These examples now live in the Claude Quickstarts repo:

**[claude-quickstarts/managed-agents/self-hosted-sandboxes](https://github.com/anthropics/claude-quickstarts/tree/main/managed-agents/self-hosted-sandboxes)**

They are runnable apps rather than notebooks, and runnable apps belong in [claude-quickstarts](https://github.com/anthropics/claude-quickstarts). This repo keeps the notebook demos.

## If you set up the old version

The shape is the same: a self-hosted environment is a work queue, and your own compute claims sessions from it. Six things changed in the move:

- Two directories were renamed. `cf/` is `cloudflare-containers/` and `cf-worker/` is `cloudflare-worker/`. `daytona/`, `modal/`, and `vercel/` kept their names. The quickstart adds `docker-memory/` and `archil/`.
- The agent and the environment are files, created with [`ant apply`](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/apply). The five webhook-started providers share one pair, in `webhook-demo/`. You no longer create the environment by hand in the Console. You still mint its environment key there.
- `docs/usage-guide.md` and `docs/upgrade-guide.md` are gone. Each provider's README is its own runbook: set up, deploy, register the webhook, test.
- The sandbox no longer holds the environment key on Daytona, Modal, or Vercel. Each sandbox gets a per-session secret, and a work item that arrives without one is refused. `cloudflare-containers/` still has to pass the key into the container, so it refuses all work until you set `ALLOW_ENVIRONMENT_KEY_IN_SANDBOX`. Its README says when that trade is acceptable.
- The SDK floor moved from 0.97 to 0.124 for both `@anthropic-ai/sdk` and `anthropic`, which is where per-session secrets arrived.
- The `docker/` image here bundled `pymongo` for the MongoDB Atlas cookbook. That image stayed in this repo and moved to [`mongodb_on_cma/self_hosted_sandbox/`](../mongodb_on_cma/self_hosted_sandbox/), next to the rest of that notebook's support code. The quickstart's `docker/` is the general-purpose version without it.

The last version of the code that lived here is at [`a4b0d89`](https://github.com/anthropics/claude-cookbooks/tree/a4b0d89061bc65769fea7947c080b3b11d938515/managed_agents/self_hosted_sandboxes).
