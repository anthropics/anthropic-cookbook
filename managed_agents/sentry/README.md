# Sentry × Claude Managed Agents has moved

This example now lives in the Claude Quickstarts repo:

**[claude-quickstarts/managed-agents/sentry](https://github.com/anthropics/claude-quickstarts/tree/main/managed-agents/sentry)**

It is a runnable app rather than a notebook, and runnable apps belong in [claude-quickstarts](https://github.com/anthropics/claude-quickstarts). This repo keeps the notebook demos, including [`sre_incident_responder.ipynb`](../sre_incident_responder.ipynb).

## If you set up the old version

The scheduled triage runs the same way. Two things changed in the move:

- The vault, environment, and agent are defined in `agents/sentry-triage/*.yaml` and created with `./agents/setup.sh` and the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart). `setup_agent.py`, `update_agent.py`, and `agent_config.py` are gone. To change the agent, edit the YAML and re-run `./agents/setup.sh`, which also re-pins the deployment to the new version.
- The `COOKBOOK_MODEL` override is gone. Set `model` in `agents/sentry-triage/agent.yaml`.

The last version of the code that lived here is at [`a97b9a2`](https://github.com/anthropics/claude-cookbooks/tree/a97b9a2dc300635f0c26b5e05d0b54bbe0279ee5/managed_agents/sentry).
