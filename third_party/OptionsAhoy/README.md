# OptionsAhoy <> Claude Cookbooks

[OptionsAhoy](https://optionsahoy.com) (AlphaLatitude Inc.) runs a remote Model Context Protocol (MCP) server with seven deterministic US equity-compensation tax tools: ISO/AMT exercise scheduling, NSO exercise, RSU sell-vs-hold, single-stock concentration analysis, protective put pricing, QSBS qualification, and equity funding plans. The server is free, requires no authentication, and computes against the full federal tax code plus all 50 states and DC.

* The [Equity Compensation Tax Planning Notebook](./equity_compensation_tax_planning.ipynb) connects Claude to the server via the Claude API MCP connector and plans a multi-year ISO exercise schedule.

# Endpoints and docs

- MCP (streamable HTTP, no auth): `POST https://optionsahoy.com/mcp`
- REST (same engine): `POST https://optionsahoy.com/api/v1/<tool-slug>`
- OpenAPI 3.1 spec: https://optionsahoy.com/openapi.json
- Local stdio: `npx -y optionsahoy-mcp`
- Documentation for agents: https://optionsahoy.com/for-agents
- Full tool and schema reference: https://optionsahoy.com/llms-full.txt

OptionsAhoy is a planning calculator, not tax advice. Coverage is US-only.
