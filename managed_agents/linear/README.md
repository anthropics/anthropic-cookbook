# Linear × Claude Managed Agents has moved

This example now lives in the Claude Quickstarts repo:

**[claude-quickstarts/managed-agents/linear](https://github.com/anthropics/claude-quickstarts/tree/main/managed-agents/linear)**

It is a runnable app rather than a notebook, and runnable apps belong in [claude-quickstarts](https://github.com/anthropics/claude-quickstarts). This repo keeps the notebook demos.

## If you set up the old version

The bridge works the same way. Four things changed in the move:

- The agent and environment are defined in `agents/linear-assistant/*.yaml` and created with `./agents/setup.sh` and the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart). `bun run setup` is gone.
- The Anthropic webhook route is `/managed-agents/webhook`, not `/cma-webhook`. Update the endpoint URL in Claude Console → Manage → Webhooks.
- Configuration is read from `.env`, not `.env.local`.
- The first Linear workspace to install the agent owns the bridge. Installs from any other workspace are refused unless you list them in `LINEAR_ALLOWED_ORG_IDS`. The old version let any workspace that could reach the server install it.

The last version of the code that lived here is at [`a97b9a2`](https://github.com/anthropics/claude-cookbooks/tree/a97b9a2dc300635f0c26b5e05d0b54bbe0279ee5/managed_agents/linear).
