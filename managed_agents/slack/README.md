# Slack × Claude Managed Agents has moved

This example now lives in the Claude Quickstarts repo:

**[claude-quickstarts/managed-agents/slack](https://github.com/anthropics/claude-quickstarts/tree/main/managed-agents/slack)**

It is a runnable app rather than a notebook, and runnable apps belong in [claude-quickstarts](https://github.com/anthropics/claude-quickstarts). This repo keeps the notebook demos, including [`slack_data_bot.ipynb`](../slack_data_bot.ipynb).

## If you set up the old version

The app behaves the same. Three things changed in the move:

- The agent and environment are defined in `agents/slack-assistant/*.yaml` and created with `./agents/setup.sh` and the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart). `bun run setup` is gone.
- The Anthropic webhook route is `/managed-agents/webhook`, not `/cma-webhook`. Update the endpoint URL in Claude Console → Manage → Webhooks.
- Configuration is read from `.env`, not `.env.local`.

The last version of the code that lived here is at [`a97b9a2`](https://github.com/anthropics/claude-cookbooks/tree/a97b9a2dc300635f0c26b5e05d0b54bbe0279ee5/managed_agents/slack).
