# Road trip planner has moved

This example now lives in the Claude Quickstarts repo:

**[claude-quickstarts/managed-agents/roadtrip-planner](https://github.com/anthropics/claude-quickstarts/tree/main/managed-agents/roadtrip-planner)**

It is a runnable app rather than a notebook, and runnable apps belong in [claude-quickstarts](https://github.com/anthropics/claude-quickstarts). This repo keeps the notebook demos, including [`CMA_coordinate_specialist_team.ipynb`](../CMA_coordinate_specialist_team.ipynb) and [`CMA_watch_subagents_live.ipynb`](../CMA_watch_subagents_live.ipynb), which cover the same `multiagent` and `event_deltas` features in notebook form.

## If you set up the old version

The app demonstrates the same four features. Three things changed in the move:

- The two agents, the environment, and the vault are defined in YAML under `agents/` and created with `./agents/setup.sh` and the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart). `npm run setup` and `npm run teardown` are gone. Teardown is `./agents/teardown.sh`.
- Configuration is read from `.env`, not `.env.local`, and the resource IDs are named `CLAUDE_*` (`CLAUDE_VAULT_ID`, `CLAUDE_AGENT_ID`), not `ROADTRIP_PLANNER_*`.
- The directory is `roadtrip-planner`, with a hyphen.

The last version of the code that lived here is at [`a97b9a2`](https://github.com/anthropics/claude-cookbooks/tree/a97b9a2dc300635f0c26b5e05d0b54bbe0279ee5/managed_agents/roadtrip_planner).
