# Managed Agents MCP server has moved

This example now lives in the Claude Quickstarts repo:

**[claude-quickstarts/managed-agents/mcp-server-typescript](https://github.com/anthropics/claude-quickstarts/tree/main/managed-agents/mcp-server-typescript)**

It is a runnable app rather than a notebook, and runnable apps belong in [claude-quickstarts](https://github.com/anthropics/claude-quickstarts). This repo keeps the notebook demos.

## If you set up the old version

The nine tools and both transports work the same way. Five things changed in the move:

- The directory is `mcp-server-typescript`, not `cma-mcp`. If you registered the stdio server with an absolute path, register it again from the new location.
- The bearer token variable is `MANAGED_AGENTS_MCP_TOKEN`, not `CMA_MCP_TOKEN`. It has to be at least 32 characters, or the HTTP server refuses to start.
- The HTTP server binds `127.0.0.1` by default. The old one listened on every interface. To serve it from another address, set `HOST` and list the public hostname in `ALLOWED_HOSTS`. Requests with any other `Host` header are refused.
- `ALLOWED_AGENT_IDS` is new. Unset, the token reaches every agent in the workspace, as before. Set it to a comma-separated list to limit the server to those agents.
- The environment is defined in `environment.yaml` and created with the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart). The inline `--config` command is gone.

The last version of the code that lived here is at [`6b671ef`](https://github.com/anthropics/claude-cookbooks/tree/6b671ef60ada2a8d3b0c07cadb424172da5135f5/managed_agents/cma-mcp).
